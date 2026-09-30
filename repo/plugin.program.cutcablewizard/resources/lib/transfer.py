"""
Resilient download and extraction for build installs.

Downloads
  - Written to "<file>.part" with a small ".part.json" note of the URL.
  - If the connection drops, retries up to 5 times (waiting 2-30s) and
    continues from where it stopped (HTTP Range) instead of starting over.
  - If every retry fails, the partial file is KEPT. Running the same install
    again continues from where it stopped, even after restarting Kodi.
  - A finished, verified file is also kept until the install succeeds, so a
    failure after downloading never means downloading 450 MB again.
  - Out-of-space and "not found / not allowed" errors are not retried.

Extraction
  - Each file that fails to extract is retried once.
  - If extraction still fails, the caller is told which file and why, and can
    offer to retry from the already-downloaded zip.
"""
import os, json, errno, socket, hashlib, zipfile, urllib.request, urllib.error
import xbmc

from resources.lib import updates

RETRY_WAITS = [2, 5, 10, 20, 30]           # seconds between attempts
NO_RETRY_HTTP = {400, 401, 403, 404, 410}


class DownloadCancelled(Exception):
    pass


class DownloadError(Exception):
    pass


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[CutCableWizard][Transfer] {msg}", level)


def _part_paths(dest):
    return dest + '.part', dest + '.part.json'


def _read_meta(meta_path):
    try:
        with open(meta_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_meta(meta_path, data):
    try:
        with open(meta_path, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass


def discard(dest):
    """Removes any partial/finished download for dest."""
    for p in _part_paths(dest):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def _sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, key, headers=None, progress=None, monitor=None):
    """
    Downloads url, resuming if a partial download for the same `key`
    (e.g. "build_id|version") exists. Returns (path, sha256_hex).
    progress(done_bytes, total_bytes, note) -> False to cancel.
    Raises DownloadCancelled or DownloadError.
    """
    part, meta_path = _part_paths(dest)
    monitor = monitor or xbmc.Monitor()
    meta = _read_meta(meta_path)

    # Only resume a download of the same thing; otherwise start fresh
    if meta.get('key') != key:
        discard(dest)
        meta = {'key': key}
    elif meta.get('complete') and os.path.exists(part):
        log(f"Using already downloaded file for {key}")
        if progress:
            progress(1, 1, "Using the file downloaded earlier...")
        return part, _sha256_of(part)
    _write_meta(meta_path, meta)

    offset  = os.path.getsize(part) if os.path.exists(part) else 0
    if offset:
        log(f"Resuming {key} from {offset} bytes")
    attempt = 0
    while True:
        hdrs = dict(headers or {})
        if offset:
            hdrs['Range'] = f'bytes={offset}-'
        req = updates.make_request(url, hdrs)
        try:
            with urllib.request.urlopen(req, context=updates.ssl_context(), timeout=60) as r:
                status = r.getcode()
                length = int(r.headers.get('Content-Length', 0) or 0)
                if offset and status == 206:
                    crange = r.headers.get('Content-Range', '')
                    if not crange.startswith(f'bytes {offset}-'):
                        raise DownloadError("server resumed at the wrong position")
                    total = offset + length
                    mode  = 'ab'
                else:
                    if offset:
                        log("Server did not resume; starting this download again")
                    offset, total, mode = 0, length, 'wb'
                with open(part, mode) as f:
                    while True:
                        chunk = r.read(262144)
                        if not chunk:
                            break
                        f.write(chunk)
                        offset += len(chunk)
                        if progress and not progress(offset, total, None):
                            raise DownloadCancelled()
                if total and offset < total:
                    raise ConnectionError(f"connection closed after {offset} of {total} bytes")
            break                                               # finished
        except DownloadCancelled:
            discard(dest)
            raise
        except urllib.error.HTTPError as e:
            if e.code == 416:                                   # range no longer valid
                discard(dest)
                _write_meta(meta_path, meta)
                offset = 0
            elif e.code in NO_RETRY_HTTP:
                raise
            elif attempt >= len(RETRY_WAITS):
                raise DownloadError(f"server error {e.code} after {attempt} retries") from e
            else:
                _wait(attempt, e, offset, progress, monitor)
                attempt += 1
        except OSError as e:
            if getattr(e, 'errno', None) == errno.ENOSPC:
                discard(dest)
                raise DownloadError("This device ran out of storage while downloading.") from e
            if updates.is_cert_error(e):
                raise
            if attempt >= len(RETRY_WAITS):
                raise DownloadError(
                    "The internet connection kept dropping. What was downloaded has been "
                    "kept - run the install again to continue where it stopped.") from e
            _wait(attempt, e, offset, progress, monitor)
            attempt += 1

    meta['complete'] = True
    _write_meta(meta_path, meta)
    return part, _sha256_of(part)


def _wait(attempt, err, offset, progress, monitor):
    wait = RETRY_WAITS[attempt]
    log(f"Download interrupted ({err}); retry {attempt + 1}/{len(RETRY_WAITS)} in {wait}s "
        f"from {offset} bytes", xbmc.LOGWARNING)
    for remaining in range(wait, 0, -1):
        if progress and not progress(offset, 0,
                                     f"Connection lost - retrying in {remaining}s "
                                     f"(attempt {attempt + 1} of {len(RETRY_WAITS)})..."):
            raise DownloadCancelled()
        if monitor.waitForAbort(1):
            raise DownloadCancelled()


def finish(dest):
    """Call once the install has succeeded: removes the kept download."""
    discard(dest)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
class ExtractError(Exception):
    pass


def extract(zip_path, target, skip_prefixes=(), progress=None):
    """
    Extracts zip_path into target. Each failing file is retried once.
    progress(index, total, name). Raises ExtractError naming the file.
    """
    try:
        zf = zipfile.ZipFile(zip_path, 'r')
    except Exception as e:
        raise ExtractError(f"the downloaded file could not be opened ({e})")
    with zf:
        files = zf.infolist()
        total = len(files)
        for i, info in enumerate(files):
            if skip_prefixes and info.filename.startswith(skip_prefixes):
                continue
            if progress and i % 200 == 0:
                progress(i, total, info.filename)
            for attempt in (1, 2):
                try:
                    zf.extract(info, target)
                    break
                except OSError as e:
                    if getattr(e, 'errno', None) == errno.ENOSPC:
                        raise ExtractError("this device ran out of storage while unpacking. "
                                           "Free up space and try again.")
                    if attempt == 2:
                        raise ExtractError(f"could not unpack {info.filename} ({e})")
                    xbmc.sleep(500)
                except Exception as e:
                    raise ExtractError(f"could not unpack {info.filename} ({e})")
