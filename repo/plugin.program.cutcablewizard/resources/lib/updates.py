"""
Shared update helpers for CutCableWizard (used by default.py and service.py).

Covers:
  - Version comparison (only prompt when the published version is NEWER)
  - Admin build credentials (admin_config.json) and admin release lookup
  - Carrying First Run Setup choices across a same-build update
"""
import os, re, json, ssl, shutil, urllib.request
import xbmc, xbmcvfs, xbmcaddon

ADDON_ID      = 'plugin.program.cutcablewizard'
HOME          = xbmcvfs.translatePath("special://home/")
ADDON_PROFILE = xbmcvfs.translatePath(xbmcaddon.Addon(ADDON_ID).getAddonInfo('profile'))

ADMIN_BUILD_ID      = 'cordcutter_admin'
ADMIN_BUILD_NAME    = 'CordCutter Admin'
ADMIN_DEFAULT_STEPS = ['device_name', 'iptv_sync', 'buffer']
ADMIN_CONFIG_FILE   = os.path.join(ADDON_PROFILE, 'admin_config.json')
# admin_config.json relative to HOME, so it can be carried through a wipe
ADMIN_CONFIG_REL    = os.path.join('userdata', 'addon_data', ADDON_ID, 'admin_config.json')

FIRSTRUN_FILE       = os.path.join(HOME, 'firstrun.txt')
FIRSTRUN_STEPS_FILE = os.path.join(HOME, 'firstrun_steps.txt')
FIRSTRUN_DONE_FILE  = os.path.join(HOME, 'firstrun_completed.json')
POST_UPDATE_FILE    = os.path.join(HOME, 'post_update.json')
RESTORE_DIR         = os.path.join(HOME, 'cutcable_restore')

# Canonical order of First Run steps (must match service.run_first_time_setup)
ALL_STEPS = ['subtitles', 'weather', 'device_name', 'simkl',
             'jellycon', 'iagl', 'iptv_sync', 'buffer']

# What each First Run step changes, so it can be captured before an update
# wipes Kodi and put back afterwards.
#   settings -> Kodi settings re-applied via JSON-RPC on next boot
#   addons   -> addon enabled/disabled state re-applied on next boot
#   paths    -> files/folders (relative to HOME) copied back over the new build
STEP_PRESERVE = {
    'subtitles':   {'settings': ['subtitles.enabled']},
    'device_name': {'settings': ['services.devicename']},
    'weather':     {'paths': ['userdata/addon_data/weather.multi']},
    'simkl':       {'paths': ['userdata/addon_data/script.simkl'],
                    'addons': ['script.simkl']},
    'jellycon':    {'paths': ['userdata/addon_data/plugin.video.jellycon'],
                    'addons': ['plugin.video.jellycon']},
    'iagl':        {'paths': ['userdata/addon_data/plugin.program.iagl']},
    'buffer':      {'paths': ['userdata/advancedsettings.xml']},
    # iptv_sync has nothing to capture; it is simply re-run after the update.
}


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[CutCableWizard] {msg}", level)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------
def _version_tuple(v):
    return tuple(int(p) for p in re.findall(r'\d+', str(v or '')))


def is_newer(latest, installed):
    """True when `latest` is a higher version than `installed`."""
    if not latest:
        return False
    if not installed:
        return True
    lt, it = _version_tuple(latest), _version_tuple(installed)
    if lt and it:
        n  = max(len(lt), len(it))
        lt = lt + (0,) * (n - len(lt))
        it = it + (0,) * (n - len(it))
        return lt > it
    return str(latest).strip() != str(installed).strip()


# ---------------------------------------------------------------------------
# Installed build info
# ---------------------------------------------------------------------------
def get_installed_info():
    path = os.path.join(HOME, 'installed_version.txt')
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, 'r') as f:
            data = f.read().strip()
        if '|' in data:
            build_id, version = data.split('|', 1)
            return build_id.strip(), version.strip()
        return None, data.strip()
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Admin credentials
# ---------------------------------------------------------------------------
def load_admin_settings():
    """Returns (url, token) if both are set in admin_config.json, else (None, None)."""
    if not os.path.exists(ADMIN_CONFIG_FILE):
        return None, None
    try:
        with open(ADMIN_CONFIG_FILE, 'r') as f:
            data = json.load(f)
        url   = data.get('admin_build_url', '').strip()
        token = data.get('admin_token', '').strip()
        if url and token:
            return url, token
    except Exception:
        pass
    return None, None


def save_admin_settings(url, token):
    try:
        os.makedirs(ADDON_PROFILE, exist_ok=True)
        with open(ADMIN_CONFIG_FILE, 'w') as f:
            json.dump({'admin_build_url': url, 'admin_token': token}, f)
        return True
    except Exception as e:
        log(f"Failed to save admin settings: {e}", xbmc.LOGWARNING)
        return False


def backup_admin_config():
    """Reads admin_config.json into memory so it survives wipe_kodi()."""
    try:
        if os.path.exists(ADMIN_CONFIG_FILE):
            with open(ADMIN_CONFIG_FILE, 'rb') as f:
                return f.read()
    except Exception:
        pass
    return None


def restore_admin_config(data):
    if not data:
        return
    try:
        os.makedirs(ADDON_PROFILE, exist_ok=True)
        with open(ADMIN_CONFIG_FILE, 'wb') as f:
            f.write(data)
    except Exception as e:
        log(f"Could not restore admin_config.json: {e}", xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# GitHub (admin build lookup)
# ---------------------------------------------------------------------------
_RELEASE_URL_RE = re.compile(
    r'https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/([^/?#]+)')
_ASSET_VER_RE   = re.compile(r'^(.*?)[-_]?v?(\d+(?:\.\d+)+)\.zip$', re.I)


def github_api_request(api_url, token):
    context = ssl._create_unverified_context()
    headers = {
        'Authorization':        f'Bearer {token}',
        'Accept':               'application/vnd.github+json',
        'User-Agent':           'Kodi-Wizard',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req, context=context, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


def _asset_key(filename):
    """
    Splits a zip name into (prefix, version).
      cordcutter_admin-build-1.2.0.zip -> ('cordcutter_admin-build', '1.2.0')
      cordcutter_admin.zip             -> ('cordcutter_admin', None)
    """
    m = _ASSET_VER_RE.match(filename)
    if m:
        return m.group(1).lower(), m.group(2)
    base = filename[:-4] if filename.lower().endswith('.zip') else filename
    return base.lower(), None


def find_latest_admin_release(admin_url, token):
    """
    Looks through the releases of the repo named in the configured admin URL
    and returns the newest zip whose name matches the configured file name
    (ignoring the version number). Version comes from the file name, or from
    the release tag when the file name has no version in it.

    Returns {'version', 'download_url', 'size_mb', 'tag'} or None.
    """
    m = _RELEASE_URL_RE.match(admin_url or '')
    if not m:
        log("Admin URL is not a GitHub release download URL; cannot check for updates.",
            xbmc.LOGWARNING)
        return None
    owner, repo, _tag, filename = m.groups()
    prefix, _ = _asset_key(filename)

    releases = github_api_request(
        f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=30", token)

    best = None
    for rel in releases or []:
        if rel.get('draft'):
            continue
        for a in rel.get('assets', []):
            name = a.get('name', '')
            if not name.lower().endswith('.zip'):
                continue
            a_prefix, a_ver = _asset_key(name)
            if a_prefix != prefix:
                continue
            ver = a_ver or str(rel.get('tag_name', '')).lstrip('vV')
            if not ver:
                continue
            if best is None or is_newer(ver, best['version']):
                best = {
                    'version':      ver,
                    'download_url': a.get('browser_download_url'),
                    'size_mb':      int(round(a.get('size', 0) / 1048576.0)),
                    'tag':          rel.get('tag_name'),
                }
    return best


def get_admin_build(manifest=None):
    """
    Returns (build_dict, token) for the admin build when a URL and token are
    configured, otherwise (None, None). The build dict points at the newest
    matching release if one can be found, falling back to the configured URL.
    """
    url, token = load_admin_settings()
    if not (url and token):
        return None, None

    steps = ADMIN_DEFAULT_STEPS
    if manifest:
        entry = next((b for b in manifest.get('builds', [])
                      if b.get('id') == ADMIN_BUILD_ID), None)
        if entry and entry.get('firstrun_steps'):
            steps = entry['firstrun_steps']

    latest = None
    try:
        latest = find_latest_admin_release(url, token)
    except Exception as e:
        log(f"Admin release lookup failed: {e}", xbmc.LOGWARNING)

    if latest:
        version, dl_url, size = latest['version'], latest['download_url'], latest['size_mb']
    else:
        m = _RELEASE_URL_RE.match(url)
        version = (_asset_key(m.group(4))[1] if m else None) or '1.0'
        dl_url, size = url, 0

    return {
        'id':             ADMIN_BUILD_ID,
        'name':           ADMIN_BUILD_NAME,
        'description':    'Personal admin build with pre-configured accounts.',
        'version':        version,
        'download_url':   dl_url,
        'size_mb':        size,
        'firstrun_steps': steps,
        'version_known':  latest is not None,
    }, token


# ---------------------------------------------------------------------------
# First Run bookkeeping
# ---------------------------------------------------------------------------
def read_completed_firstrun(build_id):
    """Steps already completed for build_id, or None if no record exists."""
    try:
        with open(FIRSTRUN_DONE_FILE, 'r') as f:
            data = json.load(f)
        if data.get('build_id') == build_id:
            return list(data.get('steps', []))
    except Exception:
        pass
    return None


def write_completed_firstrun(build_id, steps):
    try:
        ordered = [s for s in ALL_STEPS if s in set(steps)]
        with open(FIRSTRUN_DONE_FILE, 'w') as f:
            json.dump({'build_id': build_id, 'steps': ordered}, f)
    except Exception as e:
        log(f"Could not write {FIRSTRUN_DONE_FILE}: {e}", xbmc.LOGWARNING)


def plan_same_build_update(build_id, new_steps):
    """
    Decides which First Run steps can be carried over and which still need
    to be asked. Returns (carried, pending). Installs made before this
    feature have no completion record; for those, a finished first run
    (no firstrun.txt) is treated as having completed every current step.
    """
    new_steps = list(new_steps or ALL_STEPS)
    completed = read_completed_firstrun(build_id)
    if completed is None:
        completed = new_steps
    carried = [s for s in new_steps if s in completed]
    pending = [s for s in new_steps if s not in completed]
    return carried, pending


# ---------------------------------------------------------------------------
# Snapshot / restore of user settings
# ---------------------------------------------------------------------------
def _rpc(method, params):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(
            {"jsonrpc": "2.0", "method": method, "params": params, "id": 1})))
    except Exception:
        return {}


def get_kodi_setting(setting):
    data = _rpc("Settings.GetSettingValue", {"setting": setting})
    if 'result' in data and 'value' in data['result']:
        return True, data['result']['value']
    return False, None


def get_addon_enabled(addon_id):
    data = _rpc("Addons.GetAddonDetails", {"addonid": addon_id, "properties": ["enabled"]})
    try:
        return bool(data['result']['addon']['enabled'])
    except Exception:
        return None


def _copy_any(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def snapshot_user_settings(steps):
    """
    Call BEFORE wipe_kodi(). Records Kodi settings / addon states and copies
    the files each carried step touches into RESTORE_DIR.
    """
    shutil.rmtree(RESTORE_DIR, ignore_errors=True)
    os.makedirs(RESTORE_DIR, exist_ok=True)

    state = {'steps': list(steps), 'settings': {}, 'addons': {}, 'paths': []}
    for step in steps:
        spec = STEP_PRESERVE.get(step, {})
        for key in spec.get('settings', []):
            ok, val = get_kodi_setting(key)
            if ok:
                state['settings'][key] = val
        for addon_id in spec.get('addons', []):
            enabled = get_addon_enabled(addon_id)
            if enabled is not None:
                state['addons'][addon_id] = enabled
        for rel in spec.get('paths', []):
            src = os.path.join(HOME, rel)
            if os.path.exists(src):
                try:
                    _copy_any(src, os.path.join(RESTORE_DIR, rel))
                    state['paths'].append(rel)
                except Exception as e:
                    log(f"Snapshot of {rel} failed: {e}", xbmc.LOGWARNING)
    log(f"Snapshot for update: steps={steps} settings={list(state['settings'])} "
        f"addons={state['addons']} paths={state['paths']}")
    return state


def restore_user_files(state):
    """Call AFTER the new build is extracted. Copies saved files back over it."""
    for rel in state.get('paths', []):
        src = os.path.join(RESTORE_DIR, rel)
        if os.path.exists(src):
            try:
                _copy_any(src, os.path.join(HOME, rel))
            except Exception as e:
                log(f"Restore of {rel} failed: {e}", xbmc.LOGWARNING)
    shutil.rmtree(RESTORE_DIR, ignore_errors=True)


def write_post_update(state, name, version):
    """Leaves instructions for service.py to finish the restore on next boot."""
    data = {
        'name':      name,
        'version':   version,
        'settings':  state.get('settings', {}),
        'addons':    state.get('addons', {}),
        'iptv_sync': 'iptv_sync' in state.get('steps', []),
    }
    with open(POST_UPDATE_FILE, 'w') as f:
        json.dump(data, f)


def read_post_update():
    try:
        with open(POST_UPDATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def clear_post_update():
    try:
        if os.path.exists(POST_UPDATE_FILE):
            os.remove(POST_UPDATE_FILE)
    except Exception:
        pass
