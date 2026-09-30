"""
Build packaging and publishing for CutCableWizard (admin only).

Packages this device's addons + userdata into a build zip, uploads it to a
GitHub release and records it:
  - Public builds: uploaded to the release named in builds.json (e.g. "Builds"),
    then version / download_url / size_mb / changelog are committed to
    builds.json on GitHub.
  - Admin build: a new release is created in the private admin repo with the
    changelog as its release notes, and the zip is uploaded to it.

Security:
  - Every GitHub call made here uses a VERIFIED TLS connection. If the device
    can't verify GitHub's certificate the publish stops rather than sending
    the token over an unverified connection.
  - The wizard's own settings folder (tokens) is never put in any zip.
  - Public builds leave out the personal-data folders you choose (logins,
    weather location, ...) and have the device name reset.
"""
import os, re, io, json, ssl, time, base64, shutil, zipfile, urllib.request, urllib.parse
import xbmc, xbmcgui, xbmcvfs

from resources.lib import updates

HOME      = updates.HOME
WORK_DIR  = os.path.join(HOME, 'cutcable_build')          # outside addons/userdata
API       = 'https://api.github.com'
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

# Never packaged, for any build
ALWAYS_EXCLUDE = (
    'addons/packages/',
    'addons/temp/',
    'userdata/Thumbnails/',
    f'userdata/addon_data/{updates.ADDON_ID}/',     # admin URL + tokens
)
SKIP_FILE_NAMES = {'kodi.log', 'kodi.old.log', '.DS_Store', 'Thumbs.db'}
KEEP_DATABASES  = re.compile(r'^(Addons\d+|ViewModes\d+)\.db$')  # same as existing builds

# Personal data pre-selected for removal from PUBLIC builds (the first-run
# steps set these up per user). You can change the selection when packaging;
# your choice is remembered per build.
DEFAULT_PERSONAL_ADDON_DATA = [
    'weather.multi', 'script.simkl', 'plugin.video.jellycon',
    'plugin.program.iagl', 'script.trakt',
]

# Already-compressed files are stored, everything else deflated (faster on Fire TV)
STORE_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.zip', '.gz', '.7z', '.xbt',
             '.mp3', '.mp4', '.m4a', '.aac', '.ogg', '.flac', '.mkv', '.whl', '.apk'}

_ASSET_RE = re.compile(r'^(.*?)([-_]?v?)(\d+(?:\.\d+)+)\.zip$', re.I)
_RELEASE_URL_RE = re.compile(
    r'https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/([^/?#]+)')
_RAW_URL_RE = re.compile(r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)')


class PublishError(Exception):
    pass


class Cancelled(Exception):
    pass


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[CutCableWizard][BuildTools] {msg}", level)


# ---------------------------------------------------------------------------
# Naming / versions
# ---------------------------------------------------------------------------
def next_asset_name(current_name, version):
    """cordcutter_plus-build-1.1.0.zip + 1.1.2 -> cordcutter_plus-build-1.1.2.zip"""
    m = _ASSET_RE.match(current_name or '')
    if m:
        return f"{m.group(1)}{m.group(2) or '-'}{version}.zip"
    base = current_name[:-4] if current_name.lower().endswith('.zip') else current_name
    return f"{base}-{version}.zip"


def suggest_next_version(v):
    parts = re.findall(r'\d+', str(v or ''))
    if not parts:
        return '1.0.0'
    parts = [int(p) for p in parts] + [0] * (3 - len(parts))
    parts[-1] += 1
    return '.'.join(str(p) for p in parts)


# ---------------------------------------------------------------------------
# GitHub API (verified TLS only)
# ---------------------------------------------------------------------------
def _ctx():
    return updates.ssl_context()


def gh(method, url, token, data=None, body=None, headers=None, timeout=60):
    """GitHub API call. Returns parsed JSON (or None). Raises PublishError."""
    hdrs = {
        'Authorization':        f'Bearer {token}',
        'Accept':               'application/vnd.github+json',
        'User-Agent':           'CutCableWizard-Publisher',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if data is not None:
        body = json.dumps(data).encode('utf-8')
        hdrs['Content-Type'] = 'application/json'
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, context=_ctx(), timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw.decode('utf-8')) if raw else None
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode('utf-8')).get('message', '')
        except Exception:
            detail = ''
        hint = ''
        if e.code in (401, 403):
            hint = ("\n\nCheck the Publishing Token: it must not be expired and needs "
                    "Contents: Read and write on this repository.")
        elif e.code == 404:
            hint = "\n\nNot found - check the repository/release name and that the token can see this repository."
        raise PublishError(f"GitHub returned {e.code} {e.reason}: {detail}{hint}")
    except ssl.SSLError as e:
        raise PublishError(
            "Could not verify GitHub's security certificate, so nothing was sent.\n\n"
            f"({e})\n\nCheck the device's date and time are correct.")
    except urllib.error.URLError as e:
        if isinstance(getattr(e, 'reason', None), ssl.SSLError):
            raise PublishError(
                "Could not verify GitHub's security certificate, so nothing was sent.\n\n"
                f"({e.reason})\n\nCheck the device's date and time are correct.")
        raise PublishError(f"Network error talking to GitHub: {e.reason}")


def get_release_by_tag(repo, tag, token):
    return gh('GET', f"{API}/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}", token)


class _UploadReader:
    """File reader that reports progress and can be cancelled."""
    def __init__(self, path, progress):
        self.f        = open(path, 'rb')
        self.total    = os.path.getsize(path)
        self.sent     = 0
        self.progress = progress
        self._last    = 0

    def read(self, n=-1):
        chunk = self.f.read(262144)
        self.sent += len(chunk)
        if self.progress and (self.sent - self._last >= 2 * 1048576 or not chunk):
            self._last = self.sent
            if not self.progress(self.sent, self.total):
                raise Cancelled()
        return chunk

    def close(self):
        self.f.close()


def upload_asset(release, zip_path, asset_name, token, progress=None, replace=False):
    """Uploads zip_path to a release. Verifies the stored size. Returns the asset."""
    existing = next((a for a in release.get('assets', []) if a.get('name') == asset_name), None)
    if existing:
        if not replace:
            raise PublishError(f"'{asset_name}' is already in this release.")
        gh('DELETE', existing['url'], token)

    # upload_url looks like https://uploads.github.com/repos/o/r/releases/1/assets{?name,label}
    url    = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(asset_name)
    reader = _UploadReader(zip_path, progress)
    try:
        asset = gh('POST', url, token, body=reader,
                   headers={'Content-Type': 'application/zip',
                            'Content-Length': str(reader.total)},
                   timeout=300)
    finally:
        reader.close()
    if not asset or int(asset.get('size', -1)) != reader.total:
        raise PublishError("The upload finished but GitHub reports a different file size. "
                           "builds.json was not changed.")
    return asset


# ---------------------------------------------------------------------------
# builds.json editing (keeps formatting; only the four fields change)
# ---------------------------------------------------------------------------
def _find_build_block(text, build_id):
    idm = re.search(r'"id"\s*:\s*' + re.escape(json.dumps(build_id)), text)
    if not idm:
        return None
    depth, in_str, esc, start = 0, False, False, -1
    for i, c in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == '{':
            depth += 1
            if depth == 2:
                start = i
        elif c == '}':
            if depth == 2 and start <= idm.start() < i:
                return start, i + 1
            depth -= 1
    return None


def _set_field(block, key, raw):
    pat = re.compile('("' + re.escape(key) + r'"\s*:\s*)("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?|true|false|null)')
    if not pat.search(block):
        return None
    return pat.sub(lambda m: m.group(1) + raw, block, count=1)


def edit_manifest_text(text, build_id, version, url, size_mb, changelog):
    loc = _find_build_block(text, build_id)
    if not loc:
        raise PublishError(f"'{build_id}' was not found in builds.json.")
    block = text[loc[0]:loc[1]]
    nl    = '\r\n' if '\r\n' in text else '\n'
    for key, raw in (('version', json.dumps(version)),
                     ('download_url', json.dumps(url)),
                     ('size_mb', str(int(size_mb)))):
        new = _set_field(block, key, raw)
        if new is None:
            raise PublishError(f"Field '{key}' missing for '{build_id}' in builds.json.")
        block = new
    if changelog:
        raw = json.dumps(changelog, ensure_ascii=False)
        new = _set_field(block, 'changelog', raw)
        if new is None:
            m = re.search(r'(?m)^([ \t]*)"version"\s*:\s*"(?:[^"\\]|\\.)*"', block)
            if not m:
                raise PublishError("Could not add the changelog to builds.json.")
            new = block[:m.end()] + f',{nl}{m.group(1)}"changelog": {raw}' + block[m.end():]
        block = new
    out = text[:loc[0]] + block + text[loc[1]:]

    # Validate
    entry = next(b for b in json.loads(out)['builds'] if b.get('id') == build_id)
    if (entry.get('version') != version or entry.get('download_url') != url or
            int(entry.get('size_mb', -1)) != int(size_mb) or
            (changelog and entry.get('changelog') != changelog)):
        raise PublishError("builds.json did not read back as expected; not saved.")
    return out


def update_manifest_on_github(token, build_id, version, url, size_mb, changelog, name):
    m = _RAW_URL_RE.match(MANIFEST_URL)
    owner, repo, branch, path = m.groups()
    api = f"{API}/repos/{owner}/{repo}/contents/{path}"
    for attempt in range(2):                  # retry once if main moved underneath us
        meta = gh('GET', f"{api}?ref={branch}", token)
        text = base64.b64decode(meta['content']).decode('utf-8')
        new  = edit_manifest_text(text, build_id, version, url, size_mb, changelog)
        try:
            gh('PUT', api, token, data={
                'message': f"Publish {name} v{version}",
                'content': base64.b64encode(new.encode('utf-8')).decode('ascii'),
                'sha':     meta['sha'],
                'branch':  branch,
            })
            return
        except PublishError as e:
            if attempt == 0 and '409' in str(e):
                continue
            raise


# ---------------------------------------------------------------------------
# Packaging
# ---------------------------------------------------------------------------
def list_addon_data():
    """[(folder_name, size_bytes)] for userdata/addon_data, largest first."""
    base = os.path.join(HOME, 'userdata', 'addon_data')
    out  = []
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if not os.path.isdir(full) or name == updates.ADDON_ID:
            continue
        size = 0
        for root, _dirs, files in os.walk(full):
            for f in files:
                try:
                    size += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        out.append((name, size))
    return out


def collect(excluded_addon_data):
    """Walks addons/ and userdata/. Returns (dirs, files[(abs, rel, size)], total_bytes)."""
    excluded_prefixes = ALWAYS_EXCLUDE + tuple(
        f'userdata/addon_data/{n}/' for n in excluded_addon_data)
    dirs, files, total = [], [], 0
    for top in ('addons', 'userdata'):
        base = os.path.join(HOME, top)
        if not os.path.isdir(base):
            continue
        for root, dnames, fnames in os.walk(base):
            rel_root = os.path.relpath(root, HOME).replace(os.sep, '/') + '/'
            # prune excluded directories
            keep = []
            for d in sorted(dnames):
                rel_d = rel_root + d + '/'
                if d == '__pycache__' or rel_d.startswith(excluded_prefixes):
                    continue
                if rel_root == 'userdata/Database/':
                    continue                           # no sub-folders of Database
                keep.append(d)
            dnames[:] = keep
            if rel_root.startswith(excluded_prefixes):
                continue
            dirs.append(rel_root)
            for f in sorted(fnames):
                full = os.path.join(root, f)
                rel  = rel_root + f
                if f in SKIP_FILE_NAMES or f.endswith('.pyc') or os.path.islink(full):
                    continue
                if rel_root == 'userdata/Database/' and not KEEP_DATABASES.match(f):
                    continue
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                files.append((full, rel, size))
                total += size
    return dirs, files, total


def _reset_device_name(xml_bytes):
    text = xml_bytes.decode('utf-8', errors='replace')
    text = re.sub(r'<setting id="services\.devicename"[^>]*>.*?</setting>',
                  '<setting id="services.devicename" default="true">Kodi</setting>',
                  text, flags=re.S)
    return text.encode('utf-8')


def make_zip(zip_path, dirs, files, total, public, progress=None):
    """Writes the build zip. progress(done_bytes, total_bytes, label) -> False to cancel."""
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    done, skipped = 0, []
    try:
        with zipfile.ZipFile(zip_path, 'w', allowZip64=True) as zf:
            for d in dirs:
                info = zipfile.ZipInfo(d)
                info.external_attr = (0o40775 << 16) | 0x10
                zf.writestr(info, b'')
            last = 0
            for full, rel, size in files:
                ext   = os.path.splitext(rel)[1].lower()
                ctype = zipfile.ZIP_STORED if ext in STORE_EXT else zipfile.ZIP_DEFLATED
                try:
                    if public and rel == 'userdata/guisettings.xml':
                        with open(full, 'rb') as f:
                            data = _reset_device_name(f.read())
                        zf.writestr(zipfile.ZipInfo.from_file(full, rel), data,
                                    compress_type=ctype)
                    else:
                        zf.write(full, rel, compress_type=ctype, compresslevel=6)
                except FileNotFoundError:
                    skipped.append(rel)             # removed while packaging
                done += size
                if progress and (done - last >= 4 * 1048576 or done == total):
                    last = done
                    if not progress(done, total, rel):
                        raise Cancelled()
        with zipfile.ZipFile(zip_path, 'r') as zf:     # sanity check
            names = set(zf.namelist())
        missing = [rel for _, rel, _ in files if rel not in names and rel not in skipped]
        if missing:
            raise PublishError(f"The zip is missing {len(missing)} files (e.g. {missing[0]}).")
    except BaseException:
        try:
            os.remove(zip_path)
        except OSError:
            pass
        raise
    if skipped:
        log(f"Skipped {len(skipped)} files that disappeared while packaging: {skipped[:5]}")
    return os.path.getsize(zip_path)


# ---------------------------------------------------------------------------
# Interactive flow
# ---------------------------------------------------------------------------
def _input(heading, default=''):
    return xbmcgui.Dialog().input(heading, defaultt=default).strip()


def _fmt_mb(n):
    return f"{n / 1048576.0:.0f} MB"


def _choose_exclusions(build_id, public):
    remembered = (updates.get_config_value('build_excludes') or {}).get(build_id)
    folders    = list_addon_data()
    if not folders:
        return []
    if remembered is None:
        remembered = DEFAULT_PERSONAL_ADDON_DATA if public else []
    labels    = [f"{name}  ({_fmt_mb(size)})" for name, size in folders]
    preselect = [i for i, (name, _) in enumerate(folders) if name in remembered]
    heading   = ("Leave OUT these addon settings (logins, personal data)"
                 if public else "Leave OUT these addon settings (optional)")
    sel = xbmcgui.Dialog().multiselect(heading, labels, preselect=preselect)
    if sel is None:
        raise Cancelled()
    chosen = [folders[i][0] for i in sel]
    excludes = updates.get_config_value('build_excludes') or {}
    excludes[build_id] = chosen
    updates.set_config_value('build_excludes', excludes)
    return chosen


def _targets(manifest):
    """Builds that can be published from here: builds.json entries + Admin."""
    targets = []
    for b in (manifest or {}).get('builds', []):
        m = _RELEASE_URL_RE.match(b.get('download_url', ''))
        if not m:
            continue
        owner, repo, tag, fname = m.groups()
        targets.append({'id': b['id'], 'name': b['name'], 'version': b.get('version', ''),
                        'repo': f"{owner}/{repo}", 'tag': tag, 'file': fname,
                        'public': True, 'changelog': b.get('changelog', '')})
    admin_url, admin_token = updates.load_admin_settings()
    if admin_url and admin_token:
        m = _RELEASE_URL_RE.match(admin_url)
        if m:
            owner, repo, tag, fname = m.groups()
            latest = None
            try:
                latest = updates.find_latest_admin_release(admin_url, admin_token)
            except Exception as e:
                log(f"Admin release lookup failed: {e}", xbmc.LOGWARNING)
            cur_file = (latest['download_url'].rsplit('/', 1)[-1] if latest else fname)
            targets.append({'id': updates.ADMIN_BUILD_ID, 'name': updates.ADMIN_BUILD_NAME,
                            'version': latest['version'] if latest else (updates._asset_key(fname)[1] or '1.0'),
                            'repo': f"{owner}/{repo}", 'tag': None, 'file': cur_file,
                            'public': False, 'changelog': ''})
    return targets


def package_and_publish(manifest):
    dialog = xbmcgui.Dialog()

    admin_url, admin_token = updates.load_admin_settings()
    if not (admin_url and admin_token):
        dialog.ok("Package & Publish", "Set the Admin Build URL and Access Token first.")
        return

    token = updates.load_publish_token()
    if not token:
        dialog.ok("Package & Publish",
                  "A Publishing Token is needed to upload builds.\n\n"
                  "Add it under Admin Settings > Publishing Token.")
        return

    targets = _targets(manifest)
    if not targets:
        dialog.ok("Package & Publish", "Could not load the build list. Check the internet connection.")
        return

    installed_id, installed_ver = updates.get_installed_info()
    labels = [f"{t['name']}  |  v{t['version']}" + ("  [COLOR yellow](installed)[/COLOR]"
              if t['id'] == installed_id else "") for t in targets]
    sel = dialog.select("Which build is this device?", labels)
    if sel < 0:
        return
    t = targets[sel]

    if installed_id and installed_id != t['id'] and not dialog.yesno(
            "Different Build Installed",
            f"This device has [B]{next((x['name'] for x in targets if x['id'] == installed_id), installed_id)}[/B] installed, "
            f"but you chose [B]{t['name']}[/B].\n\n"
            "The zip will contain whatever is on this device now. Continue?"):
        return

    # ── Version and changelog ────────────────────────────────────────────
    version = _input(f"{t['name']}: new version (current v{t['version']})",
                     suggest_next_version(t['version']))
    if not version:
        return
    if not re.fullmatch(r'\d+(\.\d+)+', version):
        dialog.ok("Package & Publish", f"'{version}' isn't a version number like 1.2.0.")
        return
    if not updates.is_newer(version, t['version']) and not dialog.yesno(
            "Version Not Newer",
            f"v{version} is not newer than v{t['version']}, so devices won't be prompted "
            "to update.\n\nPublish anyway?"):
        return

    changelog = _input(f"What's new in v{version}?  (use  |  to start a new line)")
    changelog = '\n'.join(p.strip() for p in changelog.split('|') if p.strip())
    if not changelog and not dialog.yesno(
            "No Changelog", "No changelog entered. Publish without one?"):
        return

    asset_name = next_asset_name(t['file'], version)

    # ── Check GitHub before spending time zipping ────────────────────────
    dp = xbmcgui.DialogProgress()
    dp.create("Package & Publish", "Checking GitHub...")
    try:
        if t['public']:
            release = get_release_by_tag(t['repo'], t['tag'], token)
            if release.get('draft'):
                raise PublishError(f"Release '{t['tag']}' is a draft; publish it on GitHub first.")
            replace = False
            if any(a.get('name') == asset_name for a in release.get('assets', [])):
                dp.close()
                if not dialog.yesno("File Already Uploaded",
                                    f"[B]{asset_name}[/B] is already in the '{t['tag']}' release.\n\n"
                                    "Replace it?"):
                    return
                replace = True
                dp.create("Package & Publish", "Checking GitHub...")
            # confirm builds.json is reachable/editable before zipping
            m = _RAW_URL_RE.match(MANIFEST_URL)
            gh('GET', f"{API}/repos/{m.group(1)}/{m.group(2)}/contents/{m.group(4)}?ref={m.group(3)}", token)
        else:
            gh('GET', f"{API}/repos/{t['repo']}", token)
            replace = False
    except PublishError as e:
        dp.close()
        dialog.ok("GitHub Check Failed", str(e))
        return
    dp.close()

    # ── What to leave out ────────────────────────────────────────────────
    try:
        excluded = _choose_exclusions(t['id'], t['public'])
    except Cancelled:
        return

    dirs, files, total = collect(excluded)
    free = shutil.disk_usage(HOME).free
    need = int(total * 0.85) + 100 * 1048576
    if free < need and not dialog.yesno(
            "Low Storage",
            f"The build is about {_fmt_mb(total)} before compression and this device has "
            f"{_fmt_mb(free)} free.\n\nPackaging may run out of space. Try anyway?"):
        return

    summary = (f"[B]{t['name']} v{version}[/B]\n"
               f"File: {asset_name}\n"
               f"Contents: {len(files)} files, {_fmt_mb(total)} before compression\n"
               + (f"Left out: {', '.join(excluded)}\n" if excluded else "")
               + ("Device name reset to 'Kodi'.\n" if t['public'] else
                  "[COLOR yellow]Admin build: logins are included; goes to your PRIVATE repo.[/COLOR]\n")
               + "\nPackaging can take 10+ minutes on a Fire TV. Start?")
    if not dialog.yesno("Package & Publish", summary):
        return

    # ── Zip ──────────────────────────────────────────────────────────────
    zip_path = os.path.join(WORK_DIR, asset_name)
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    dp = xbmcgui.DialogProgress()
    dp.create("Packaging Build", "Starting...")
    started = time.time()

    def zprog(done, tot, label):
        pct = int(done * 100 / tot) if tot else 100
        dp.update(pct, f"Packaging {_fmt_mb(done)} of {_fmt_mb(tot)}\n{label[-60:]}")
        return not dp.iscanceled()

    try:
        zip_size = make_zip(zip_path, dirs, files, total, t['public'], zprog)
    except Cancelled:
        dp.close()
        dialog.ok("Package & Publish", "Cancelled. Nothing was uploaded.")
        return
    except Exception as e:
        dp.close()
        shutil.rmtree(WORK_DIR, ignore_errors=True)
        dialog.ok("Packaging Failed", f"{e}\n\nNothing was uploaded.")
        return
    dp.close()
    size_mb = int(round(zip_size / 1048576.0))
    log(f"Packaged {asset_name}: {size_mb} MB in {int(time.time() - started)}s")

    # ── Upload + record, with retry ──────────────────────────────────────
    while True:
        dp = xbmcgui.DialogProgress()
        dp.create("Publishing Build", f"Uploading {asset_name}...")

        def uprog(sent, tot):
            dp.update(int(sent * 100 / tot) if tot else 100,
                      f"Uploading {_fmt_mb(sent)} of {_fmt_mb(tot)}")
            return not dp.iscanceled()

        try:
            if t['public']:
                release = get_release_by_tag(t['repo'], t['tag'], token)
                asset   = upload_asset(release, zip_path, asset_name, token, uprog, replace)
                dl_url  = f"https://github.com/{t['repo']}/releases/download/{t['tag']}/{asset_name}"
                dp.update(100, "Updating builds.json...")
                update_manifest_on_github(token, t['id'], version, dl_url, size_mb,
                                          changelog, t['name'])
            else:
                tag = f"admin-{version}"
                try:
                    release = gh('POST', f"{API}/repos/{t['repo']}/releases", token, data={
                        'tag_name': tag, 'name': f"{t['name']} v{version}",
                        'body': changelog, 'draft': False, 'prerelease': False})
                except PublishError as e:
                    if '422' not in str(e):
                        raise
                    release = get_release_by_tag(t['repo'], tag, token)   # tag exists: reuse
                asset = upload_asset(release, zip_path, asset_name, token, uprog, replace=True)
            break
        except Cancelled:
            dp.close()
            if not dialog.yesno("Upload Cancelled", "Upload cancelled. Try again?"):
                shutil.rmtree(WORK_DIR, ignore_errors=True)
                return
        except Exception as e:
            dp.close()
            log(f"Publish failed: {e}", xbmc.LOGWARNING)
            if not dialog.yesno("Publish Failed", f"{e}\n\nTry again?"):
                shutil.rmtree(WORK_DIR, ignore_errors=True)
                return
    dp.close()
    shutil.rmtree(WORK_DIR, ignore_errors=True)

    # This device now runs the version just published; don't prompt it to update to itself.
    if installed_id == t['id']:
        try:
            with open(os.path.join(HOME, 'installed_version.txt'), 'w') as f:
                f.write(f"{t['id']}|{version}")
        except Exception:
            pass

    old_file = t['file']
    if t['public']:
        msg = (f"[B]{t['name']} v{version}[/B] ({size_mb} MB) is uploaded and builds.json is updated.\n\n"
               "Devices will see the update within about 5 minutes.\n\n"
               "On your PC, fetch/pull in GitHub Desktop before editing the repo again.")
        if old_file != asset_name:
            msg += f"\n\nAfter ~10 minutes you can delete the old [B]{old_file}[/B] from the release."
    else:
        msg = (f"[B]{t['name']} v{version}[/B] ({size_mb} MB) is published to your private "
               f"repo as release '{tag}'.\n\nAdmin devices will be offered it on their next check.")
    dialog.ok("Publish Complete", msg)
