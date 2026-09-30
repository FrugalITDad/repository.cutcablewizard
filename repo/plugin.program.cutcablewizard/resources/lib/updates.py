"""
Shared update helpers for CutCableWizard (used by default.py and service.py).

Covers:
  - Version comparison (only prompt when the published version is NEWER)
  - Admin build credentials (admin_config.json) and admin release lookup
  - Carrying First Run Setup choices across a same-build update
"""
import os, re, json, ssl, shutil, time, urllib.request
import xbmc, xbmcgui, xbmcvfs, xbmcaddon

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
SNOOZE_FILE         = os.path.join(HOME, 'update_snooze.json')

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


def _read_config():
    try:
        with open(ADMIN_CONFIG_FILE, 'r') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_config(data):
    os.makedirs(ADDON_PROFILE, exist_ok=True)
    tmp = ADMIN_CONFIG_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, ADMIN_CONFIG_FILE)
    try:
        os.chmod(ADMIN_CONFIG_FILE, 0o600)
    except Exception:
        pass


def save_admin_settings(url, token):
    """Saves the admin URL/token, keeping any other saved values (publishing token etc.)."""
    try:
        data = _read_config()
        data['admin_build_url'] = url
        data['admin_token']     = token
        _write_config(data)
        return True
    except Exception as e:
        log(f"Failed to save admin settings: {e}", xbmc.LOGWARNING)
        return False


def get_config_value(key, default=None):
    return _read_config().get(key, default)


def set_config_value(key, value):
    """Sets (or with value=None removes) one value in admin_config.json."""
    try:
        data = _read_config()
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
        _write_config(data)
        return True
    except Exception as e:
        log(f"Failed to save setting {key}: {e}", xbmc.LOGWARNING)
        return False


def load_publish_token():
    return (get_config_value('publish_token') or '').strip() or None


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


_SSL_CTX = None


def ssl_context():
    """
    Verified TLS context. Uses the system store plus Kodi's bundled CA file
    (Android/Fire TV Python has no system store of its own) and certifi if
    present. Certificates are always checked; there is no unverified fallback.
    """
    global _SSL_CTX
    if _SSL_CTX is None:
        ctx = ssl.create_default_context()
        candidates = [os.environ.get('SSL_CERT_FILE', ''),
                      xbmcvfs.translatePath('special://xbmc/system/certs/cacert.pem')]
        try:
            import certifi
            candidates.append(certifi.where())
        except Exception:
            pass
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    ctx.load_verify_locations(path)
                except Exception:
                    pass
        _SSL_CTX = ctx
    return _SSL_CTX


def is_cert_error(err):
    """True if an exception is a certificate/TLS verification failure."""
    reason = getattr(err, 'reason', err)
    return isinstance(reason, ssl.SSLError) or isinstance(err, ssl.SSLError)


CERT_ERROR_HELP = ("The secure connection to GitHub could not be verified, so nothing "
                   "was downloaded.\n\nThis is usually caused by the device's date and "
                   "time being wrong. Check Settings > Date & Time and try again.")


def github_api_request(api_url, token):
    context = ssl_context()
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
                    # Release notes double as the admin build's changelog
                    'changelog':    (rel.get('body') or '').strip(),
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
        changelog = latest.get('changelog', '')
    else:
        m = _RELEASE_URL_RE.match(url)
        version = (_asset_key(m.group(4))[1] if m else None) or '1.0'
        dl_url, size, changelog = url, 0, ''

    return {
        'id':             ADMIN_BUILD_ID,
        'name':           ADMIN_BUILD_NAME,
        'description':    'Personal admin build with pre-configured accounts.',
        'version':        version,
        'download_url':   dl_url,
        'size_mb':        size,
        'firstrun_steps': steps,
        'changelog':      changelog,
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


# ---------------------------------------------------------------------------
# "Remind me later" for update prompts
# ---------------------------------------------------------------------------
# (label, seconds) - None means "don't ask again until a newer version"
SNOOZE_OPTIONS = [
    ("Remind me tomorrow",          1 * 86400),
    ("Remind me in 3 days",         3 * 86400),
    ("Remind me in 1 week",         7 * 86400),
    ("Remind me in 2 weeks",       14 * 86400),
    ("Don't remind me about this version", None),
]


def is_snoozed(build_id, version):
    """
    True while the user has asked to be reminded later about this exact
    build + version. A newer version always clears the snooze.
    """
    try:
        with open(SNOOZE_FILE, 'r') as f:
            data = json.load(f)
    except Exception:
        return False
    if data.get('build_id') != build_id or data.get('version') != version:
        return False
    until = data.get('until')
    if until is None:
        return True
    return time.time() < float(until)


def clear_snooze():
    try:
        if os.path.exists(SNOOZE_FILE):
            os.remove(SNOOZE_FILE)
    except Exception:
        pass


def ask_snooze(build_id, version):
    """
    Shown after the user declines an update. Asks when to be reminded and
    records it. Backing out of the list defaults to tomorrow.
    """
    labels = [label for label, _ in SNOOZE_OPTIONS]
    sel = xbmcgui.Dialog().select("When should we remind you about this update?", labels)
    if sel < 0:
        sel = 0
    label, seconds = SNOOZE_OPTIONS[sel]
    data = {'build_id': build_id, 'version': version,
            'until': None if seconds is None else time.time() + seconds}
    try:
        with open(SNOOZE_FILE, 'w') as f:
            json.dump(data, f)
        log(f"Update {build_id} v{version} snoozed: {label}")
    except Exception as e:
        log(f"Could not save update reminder: {e}", xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# Update prompt (shared by the startup check and the wizard)
# ---------------------------------------------------------------------------
CHANGELOG_PREVIEW_CHARS = 160


def prompt_update(name, installed, latest, changelog='', heading="Update Available",
                  footer=""):
    """
    Asks whether to update, showing a short "What's new" preview. When there
    is a changelog, a [What's New] button opens the full text and then
    returns to the prompt. Returns True if the user chose to update.
    """
    changelog = (changelog or '').strip()
    msg = (f"A new version of [B]{name}[/B] is available!\n"
           f"Installed: v{installed}   Available: v{latest}\n")
    if changelog:
        preview = ' '.join(changelog.split())
        if len(preview) > CHANGELOG_PREVIEW_CHARS:
            preview = preview[:CHANGELOG_PREVIEW_CHARS].rsplit(' ', 1)[0] + '...'
        msg += f"\n[B]What's new:[/B] {preview}\n"
    msg += "\nWould you like to update now?" + (f"\n{footer}" if footer else "")

    dialog = xbmcgui.Dialog()
    if not changelog or not hasattr(dialog, 'yesnocustom'):
        return bool(dialog.yesno(heading, msg))

    while True:
        # -1 = backed out, 0 = No, 1 = Yes, 2 = What's New
        result = dialog.yesnocustom(heading, msg, "What's New",
                                    nolabel="Not Now", yeslabel="Update")
        if result == 2:
            dialog.textviewer(f"What's new in {name} v{latest}", changelog)
            continue
        return result == 1


# ---------------------------------------------------------------------------
# Keep the newest wizard across a build install
# ---------------------------------------------------------------------------
# Build zips contain a copy of this wizard. If that copy is older than the one
# doing the install, the device would boot into the old wizard (which may not
# know how to finish an update). Keep whichever is newer.
WIZARD_KEEP_DIR = os.path.join(HOME, 'cutcable_wizard_keep')


def _addon_xml_version(addon_dir):
    try:
        with open(os.path.join(addon_dir, 'addon.xml'), 'r', encoding='utf-8') as f:
            m = re.search(r'<addon\b[^>]*\bversion="([^"]+)"', f.read())
        return m.group(1) if m else None
    except Exception:
        return None


def stash_running_wizard():
    """Call BEFORE wipe_kodi(). Copies the running wizard aside."""
    try:
        src = xbmcvfs.translatePath(xbmcaddon.Addon(ADDON_ID).getAddonInfo('path'))
        shutil.rmtree(WIZARD_KEEP_DIR, ignore_errors=True)
        shutil.copytree(src, WIZARD_KEEP_DIR,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        return True
    except Exception as e:
        log(f"Could not stash running wizard: {e}", xbmc.LOGWARNING)
        return False


def restore_newest_wizard():
    """Call AFTER extracting the build. Puts the stashed wizard back if it is newer."""
    try:
        if not os.path.isdir(WIZARD_KEEP_DIR):
            return
        dest     = os.path.join(HOME, 'addons', ADDON_ID)
        running  = _addon_xml_version(WIZARD_KEEP_DIR)
        bundled  = _addon_xml_version(dest) if os.path.isdir(dest) else None
        if running and (bundled is None or is_newer(running, bundled)):
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(WIZARD_KEEP_DIR, dest)
            log(f"Kept wizard v{running} (build contained v{bundled}).")
        else:
            log(f"Build's wizard v{bundled} is current; keeping it.")
    except Exception as e:
        log(f"Could not restore newest wizard: {e}", xbmc.LOGWARNING)
    finally:
        shutil.rmtree(WIZARD_KEEP_DIR, ignore_errors=True)


# ---------------------------------------------------------------------------
# Compiled (binary) add-ons built for a different device
# ---------------------------------------------------------------------------
# Builds are made on Fire TV, so add-ons with compiled code (Live TV,
# InputStream, ...) are built for 32-bit ARM Android. Other devices - e.g.
# Google TV running 64-bit Kodi, Windows, Mac - can't load them. These get
# removed and reinstalled from the official Kodi repository instead.
# Their settings in userdata/addon_data are kept (they aren't device specific).
FRIENDLY_ADDON_NAMES = {
    'pvr.iptvsimple':           'Live TV (IPTV Simple)',
    'pvr.hdhomerun':            'Live TV (HDHomeRun)',
    'inputstream.adaptive':     'Streaming support (InputStream Adaptive)',
    'inputstream.ffmpegdirect': 'Streaming support (FFmpegDirect)',
    'inputstream.rtmp':         'Streaming support (RTMP)',
    'vfs.libarchive':           'Archive support',
    'visualization.starburst':  'Music visualization',
}
_NATIVE_EXT = ('.so', '.dll', '.dylib')


def this_platform():
    """
    Returns (tags, label): the Kodi <platform> names this device can load,
    and a readable description. Uses the Kodi process's own bitness, so a
    32-bit Kodi on 64-bit hardware (typical Fire TV) is reported as armv7.
    """
    import platform, struct
    bits = struct.calcsize('P') * 8
    mach = (platform.machine() or '').lower()
    arm  = mach.startswith(('arm', 'aarch'))
    x86  = mach in ('x86_64', 'amd64', 'i386', 'i686', 'x86')
    cond = xbmc.getCondVisibility

    if cond('System.Platform.Android'):
        if arm:
            tag = 'android-armv7' if bits == 32 else 'android-aarch64'
        elif x86:
            tag = 'android-x86' if bits == 32 else 'android-x86_64'
        else:
            tag = 'android'
        return {'android', tag}, f"{bits}-bit Android"
    if cond('System.Platform.Windows') or cond('System.Platform.UWP'):
        tag = 'windows-x86_64' if bits == 64 else 'windows-i686'
        return {'windows', 'windx', 'windowsstore', tag}, "Windows"
    if cond('System.Platform.IOS'):
        return {'ios', 'ios-aarch64', 'darwin_embedded'}, "iOS"
    if cond('System.Platform.TVOS'):
        return {'tvos', 'tvos-aarch64', 'darwin_embedded'}, "Apple TV"
    if cond('System.Platform.OSX'):
        tag = 'osx-arm64' if arm else 'osx-x86_64'
        return {'osx', 'osx64', tag}, "Mac"
    if cond('System.Platform.Linux'):
        return {'linux'}, "Linux"
    return set(), "this device"


def _read_platform_info(addon_dir):
    """Returns (platform_tags, has_native_code) from an add-on folder."""
    try:
        with open(os.path.join(addon_dir, 'addon.xml'), 'r', encoding='utf-8', errors='replace') as f:
            xml = f.read()
    except Exception:
        return None, False
    tags = set()
    for block in re.findall(r'<platform>([^<]*)</platform>', xml):
        tags.update(block.split())
    native = bool(re.search(r'\blibrary_\w+="', xml))
    if not native:
        for _root, _dirs, files in os.walk(addon_dir):
            if any(f.endswith(_NATIVE_EXT) for f in files):
                native = True
                break
    return tags, native


def find_incompatible_addons():
    """
    Add-ons in special://home/addons with compiled code that were built for a
    different platform than this device. Python-only add-ons are never touched.
    """
    base = os.path.join(HOME, 'addons')
    tags_here, _ = this_platform()
    bad = []
    if not tags_here or not os.path.isdir(base):
        return bad          # unknown device type: never remove anything
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not os.path.isdir(path) or name in ('packages', 'temp'):
            continue
        tags, native = _read_platform_info(path)
        if not native or not tags or 'all' in tags:
            continue
        if not (tags & tags_here):
            bad.append(name)
    return bad


def remove_addon_folders(addon_ids):
    removed = []
    for addon_id in addon_ids:
        path = os.path.join(HOME, 'addons', addon_id)
        try:
            shutil.rmtree(path)
            removed.append(addon_id)
        except Exception as e:
            log(f"Could not remove {addon_id}: {e}", xbmc.LOGWARNING)
    return removed
