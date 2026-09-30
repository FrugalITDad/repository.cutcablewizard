"""
Swaps compiled add-ons for the right device DURING build extraction.

Builds are made on a Fire TV, so add-ons with compiled code (Live TV,
InputStream Adaptive / FFmpegDirect / RTMP, ...) are built for 32-bit ARM
Android. When a build is installed on a different kind of device (e.g. a
Google TV running 64-bit Kodi), this module downloads the matching version of
each one from the official Kodi add-on repository before Kodi restarts, so
nothing has to be installed or confirmed afterwards.

Downloads are verified the same way Kodi verifies them: the SHA-256 comes from
mirrors.kodi.tv over a certificate-checked connection, and the file from the
mirror it redirects to must match it. Anything that can't be fetched or
verified is left for the startup repair in service.py (which asks Kodi to
install it).
"""
import os, re, gzip, json, base64, shutil, hashlib, zipfile, urllib.request, urllib.error
import xbmc

from resources.lib import updates

MIRROR  = 'https://mirrors.kodi.tv/addons'
KODI_CODENAMES = {19: 'matrix', 20: 'nexus', 21: 'omega', 22: 'piers'}
WORK_DIR = os.path.join(updates.HOME, 'cutcable_binaries')


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[CutCableWizard][Binaries] {msg}", level)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def kodi_codename():
    m = re.match(r'(\d+)', xbmc.getInfoLabel('System.BuildVersion') or '')
    return KODI_CODENAMES.get(int(m.group(1))) if m else None


# ---------------------------------------------------------------------------
# What in the build needs replacing
# ---------------------------------------------------------------------------
def incompatible_in_zip(zf):
    """
    [(addon_id, version, tags)] for add-ons in the build zip that contain
    compiled code for a different platform than this device.
    """
    here, _ = updates.this_platform()
    if not here:
        return []
    names = zf.namelist()
    native_dirs = {n.split('/')[1] for n in names
                   if n.startswith('addons/') and n.count('/') >= 2
                   and n.lower().endswith(('.so', '.dll', '.dylib'))}
    out = []
    for addon_id in sorted(native_dirs):
        try:
            xml = zf.read(f'addons/{addon_id}/addon.xml').decode('utf-8', 'replace')
        except KeyError:
            continue
        tags = set()
        for block in re.findall(r'<platform>([^<]*)</platform>', xml):
            tags.update(block.split())
        if not tags or 'all' in tags or (tags & here):
            continue
        m = re.search(r'<addon\b[^>]*\bversion="([^"]+)"', xml)
        out.append((addon_id, m.group(1) if m else None, tags))
    return out


# ---------------------------------------------------------------------------
# Official repository lookups
# ---------------------------------------------------------------------------
def _resolve(codename, addon_id, tag, version):
    """
    Returns (download_url, sha256_hex) for one add-on zip, or None if the
    repository doesn't have it. Mirrors Kodi's CRepository::ResolvePathAndHash.
    """
    path   = f"{MIRROR}/{codename}/{addon_id}+{tag}/{addon_id}-{version}.zip"
    opener = urllib.request.build_opener(
        _NoRedirect, urllib.request.HTTPSHandler(context=updates.ssl_context()))
    req = urllib.request.Request(path, headers={'User-Agent': 'Kodi-Wizard'})
    try:
        resp     = opener.open(req, timeout=20)
        headers  = resp.headers
        location = path
        resp.close()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            headers  = e.headers
            location = headers.get('Location') or path
        elif e.code == 404:
            return None
        else:
            raise
    b64 = headers.get('Content-Sha256')
    digest = base64.b64decode(b64).hex() if b64 else None
    if not digest:
        with urllib.request.urlopen(path + '.sha256', context=updates.ssl_context(), timeout=20) as r:
            digest = r.read().decode('ascii', 'replace').split()[0].strip().lower()
    if not re.fullmatch(r'[0-9a-f]{64}', digest or ''):
        raise ValueError(f"no valid SHA-256 for {path}")
    return location, digest


_INDEX = None


def _latest_from_index(codename, addon_id, here):
    """(version, tag) of the newest build of addon_id for this device, from addons.xml.gz."""
    global _INDEX
    if _INDEX is None:
        url = f"{MIRROR}/{codename}/addons.xml.gz"
        with urllib.request.urlopen(url, context=updates.ssl_context(), timeout=60) as r:
            _INDEX = gzip.decompress(r.read()).decode('utf-8', 'replace')
    best = None
    for m in re.finditer(r'<addon\b[^>]*\bid="' + re.escape(addon_id) + r'"[^>]*>.*?</addon>',
                         _INDEX, re.S):
        block = m.group(0)
        vm = re.search(r'\bversion="([^"]+)"', block[:block.find('>')])
        tags = set()
        for p in re.findall(r'<platform>([^<]*)</platform>', block):
            tags.update(p.split())
        match = sorted(t for t in tags & here if '-' in t) or sorted(tags & here)
        if vm and match and (best is None or updates.is_newer(vm.group(1), best[0])):
            best = (vm.group(1), match[0])
    return best


def _download_verified(url, dest, sha256_hex):
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard'})
    with urllib.request.urlopen(req, context=updates.ssl_context(), timeout=60) as r, \
            open(dest, 'wb') as f:
        while True:
            chunk = r.read(262144)
            if not chunk:
                break
            h.update(chunk)
            f.write(chunk)
    if h.hexdigest() != sha256_hex:
        os.remove(dest)
        raise ValueError(f"checksum mismatch for {os.path.basename(dest)}")


# ---------------------------------------------------------------------------
# Public API used by install_build()
# ---------------------------------------------------------------------------
def prepare(build_zip_path, progress=None):
    """
    Call after the build zip is downloaded and BEFORE wiping. Downloads a
    verified replacement for each incompatible compiled add-on.
    Returns (replacements {addon_id: local_zip}, not_replaced [addon_id]).
    Never raises: anything that fails is simply left for the startup repair.
    """
    replacements, not_replaced = {}, []
    try:
        with zipfile.ZipFile(build_zip_path) as zf:
            needed = incompatible_in_zip(zf)
    except Exception as e:
        log(f"Could not inspect build for compiled add-ons: {e}", xbmc.LOGWARNING)
        return replacements, not_replaced
    if not needed:
        return replacements, not_replaced

    here, device = updates.this_platform()
    codename     = kodi_codename()
    specific     = sorted(t for t in here if '-' in t)
    log(f"Build has add-ons for another device ({device}): {[n[0] for n in needed]}")
    if not codename or not specific:
        return replacements, [n[0] for n in needed]

    shutil.rmtree(WORK_DIR, ignore_errors=True)
    os.makedirs(WORK_DIR, exist_ok=True)
    for i, (addon_id, version, _tags) in enumerate(needed):
        label = updates.FRIENDLY_ADDON_NAMES.get(addon_id, addon_id)
        if progress:
            progress(int(i * 100 / len(needed)), f"Getting {label} for this device ({device})...")
        try:
            resolved, use_version, use_tag = None, version, specific[0]
            if version:
                resolved = _resolve(codename, addon_id, use_tag, version)   # same version first
            if not resolved:
                latest = _latest_from_index(codename, addon_id, here)
                if latest:
                    use_version, use_tag = latest
                    resolved = _resolve(codename, addon_id, use_tag, use_version)
            if not resolved:
                log(f"{addon_id}: no version for {device} in the Kodi repository")
                not_replaced.append(addon_id)
                continue
            url, digest = resolved
            dest = os.path.join(WORK_DIR, f"{addon_id}-{use_version}.zip")
            _download_verified(url, dest, digest)
            with zipfile.ZipFile(dest) as z:
                bad = [n for n in z.namelist() if not n.startswith(addon_id + '/') or '..' in n]
                if bad:
                    raise ValueError(f"unexpected paths in {addon_id} zip: {bad[:3]}")
            replacements[addon_id] = dest
            log(f"{addon_id}: fetched v{use_version} for {use_tag} (sha256 verified)")
        except Exception as e:
            log(f"{addon_id}: could not fetch replacement: {e}", xbmc.LOGWARNING)
            not_replaced.append(addon_id)
    return replacements, not_replaced


def install(replacements):
    """Call AFTER the build is extracted. Puts the device-correct add-ons in place."""
    base = os.path.join(updates.HOME, 'addons')
    for addon_id, zip_path in replacements.items():
        try:
            shutil.rmtree(os.path.join(base, addon_id), ignore_errors=True)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(base)
        except Exception as e:
            log(f"Could not install {addon_id}: {e}", xbmc.LOGWARNING)
    shutil.rmtree(WORK_DIR, ignore_errors=True)


def cleanup():
    shutil.rmtree(WORK_DIR, ignore_errors=True)
