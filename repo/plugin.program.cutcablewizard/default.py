import xbmc, xbmcgui, xbmcaddon, os, shutil, urllib.request, json, ssl, zipfile, xbmcvfs

# ---------------------------------------------------------------------------
# Addon Constants
# ---------------------------------------------------------------------------
ADDON    = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HOME     = xbmcvfs.translatePath("special://home/")

MANIFEST_URL          = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
CLOUDFLARE_WORKER_URL = "https://cutcable-admin.wcouse3.workers.dev"   # ← replace after deploying Worker

# Trigger files written to HOME root
FIRSTRUN_STEPS_FILE  = os.path.join(HOME, 'firstrun_steps.txt')

# ---------------------------------------------------------------------------
# Admin / Developer Mode State
# ---------------------------------------------------------------------------
# Both flags are in-memory only — never written to disk.
# They are automatically cleared when Kodi force-closes after install (os._exit).
_admin_mode           = False   # True = admin build visible + dev mode active
_admin_password_cache = None    # Password held for Bearer token during same session

# Human-readable names for the switch-build warning dialog.
BUILD_NAMES = {
    'cordcutter_base':         'CordCutter Base',
    'cordcutter_plus':         'CordCutter Plus',
    'cordcutter_plus_gaming':  'CordCutter Plus w Gaming',
    'cordcutter_pro':          'CordCutter Pro',
    'cordcutter_pro_gaming':   'CordCutter Pro w Gaming',
    'cordcutter_admin':        'CordCutter Admin',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_json(url, extra_headers=None):
    try:
        context = ssl._create_unverified_context()
        headers = {'User-Agent': 'Kodi-Wizard'}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=context, timeout=15) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def set_kodi_setting(setting, value):
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {"setting": setting, "value": value},
        "id": 1
    }))


def get_installed_info():
    """
    Returns (build_id, version) tuple from installed_version.txt.
    File format: build_id|version  e.g. cordcutter_plus|1.1.0
    Returns (None, None) when no build is installed.
    """
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
# Admin Mode
# ---------------------------------------------------------------------------
def unlock_admin_mode():
    """
    Prompts for the admin password and validates it against the Cloudflare Worker.
    On success sets _admin_mode and caches the password for the Bearer header.
    Both are in-memory only and clear when the process exits after install.

    Returns True if successfully unlocked, False otherwise.
    """
    global _admin_mode, _admin_password_cache

    password = xbmcgui.Dialog().input(
        "Admin Mode — Enter Password",
        type=xbmcgui.INPUT_ALPHANUM,
        option=xbmcgui.ALPHANUM_HIDE_INPUT
    )
    if not password:
        return False

    try:
        context = ssl._create_unverified_context()
        import urllib.parse
        # URL-encode the password so special characters are preserved.
        params   = urllib.parse.urlencode({'password': password}, quote_via=urllib.parse.quote)
        auth_url = f"{CLOUDFLARE_WORKER_URL}/auth?{params}"
        xbmc.log(f"[CutCableWizard] Admin auth: password chars: {[ord(c) for c in password]}", xbmc.LOGINFO)
        xbmc.log(f"[CutCableWizard] Admin auth: connecting to {auth_url}", xbmc.LOGINFO)
        # Quick test — also try the manifest URL to confirm urllib works at all
        test_result = get_json(MANIFEST_URL)
        xbmc.log(f"[CutCableWizard] Admin auth: manifest reachable: {test_result is not None}", xbmc.LOGINFO)

        # Use xbmcvfs to make the HTTP request — more reliable than urllib
        # on Android/FireTV where urllib can throw error 1042.
        raw    = None
        result = {'valid': False}
        # Use the same get_json() pattern as the manifest fetch — this is
        # the only HTTP method confirmed working on FireTV/Android in this addon.
        try:
            context_  = ssl._create_unverified_context()
            req       = urllib.request.Request(
                auth_url,
                headers={'User-Agent': 'Kodi-Wizard'}
            )
            with urllib.request.urlopen(req, context=context_, timeout=15) as r:
                raw = r.read().decode('utf-8')
            xbmc.log(f"[CutCableWizard] Admin auth urllib status: 200", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[CutCableWizard] Admin auth urllib error: {type(e).__name__}: {e}", xbmc.LOGWARNING)

        xbmc.log(f"[CutCableWizard] Admin auth raw response: [{raw}]", xbmc.LOGINFO)
        if raw:
            try:
                result = json.loads(raw)
            except Exception:
                xbmc.log(f"[CutCableWizard] Admin auth JSON parse failed on: [{raw}]", xbmc.LOGWARNING)
                result = {'valid': False}
        if result.get('valid'):
            _admin_mode           = True
            _admin_password_cache = password
            xbmc.log("[CutCableWizard] Admin mode unlocked.", xbmc.LOGINFO)
            xbmcgui.Dialog().ok(
                "Admin Mode Unlocked",
                "Admin mode is now active.\n\n"
                "[B]Developer mode:[/B] First Run Setup will be suppressed "
                "after the next install — Kodi will boot normally.\n\n"
                "[B]Admin build:[/B] Now visible in the Install Build menu.\n\n"
                "Both features clear automatically after one install."
            )
            return True
    except Exception as e:
        xbmc.log(f"[CutCableWizard] Admin auth error: {type(e).__name__}: {e}", xbmc.LOGWARNING)
        xbmcgui.Dialog().ok(
            "Admin Mode Error",
            f"Could not reach the authentication server.\n\n"
            f"Error: {type(e).__name__}: {str(e)}\n\n"
            "Please check your internet connection and try again."
        )
        return False

    if not result.get('valid'):
        xbmcgui.Dialog().ok("Admin Mode", "Incorrect password.")
    return False


# ---------------------------------------------------------------------------
# Fresh Start
# ---------------------------------------------------------------------------
FRESH_START_BUILD_ID = 'cordcutter_fresh_start'


def wipe_kodi():
    """
    Core wipe routine shared by smart_fresh_start() and install_build().
    Deletes all Kodi folders and HOME root trigger files completely.
    The caller is responsible for extracting a zip immediately after.
    """
    for folder in ['addons', 'userdata', 'packages', 'temp', 'Database']:
        path = os.path.join(HOME, folder)
        if os.path.exists(path):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

    for trigger in ['firstrun.txt', 'firstrun_steps.txt', 'installed_version.txt',
                    'last_update_check.txt', 'post_fresh_start.txt']:
        path = os.path.join(HOME, trigger)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def smart_fresh_start(manifest):
    """
    Full fresh start flow:
      1. Confirm with the user
      2. Find the clean slate build URL in the manifest
      3. Download and verify the zip (existing setup untouched until here)
      4. Wipe everything
      5. Extract the clean slate zip
      6. Return True so main_menu() can force-close Kodi
    """
    if not xbmcgui.Dialog().yesno(
        "Fresh Start",
        "This will completely wipe your Kodi installation and restore a "
        "clean base with only the CutCableWizard installed.\n\n"
        "Are you absolutely sure?"
    ):
        return False

    if not manifest:
        xbmcgui.Dialog().ok(
            "Fresh Start Error",
            "Could not reach the build server to download the clean slate.\n\n"
            "Please check your internet connection and try again."
        )
        return False

    builds     = manifest.get('builds', [])
    fresh_build = next((b for b in builds if b['id'] == FRESH_START_BUILD_ID), None)
    if not fresh_build:
        xbmcgui.Dialog().ok(
            "Fresh Start Error",
            "The clean slate build was not found in the manifest.\n\n"
            "Please update the CutCableWizard to the latest version."
        )
        return False

    zip_path = os.path.join(HOME, "freshstart.zip")
    dp = xbmcgui.DialogProgress()
    dp.create("Fresh Start", "Downloading clean slate...")

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(fresh_build['download_url'], context=context) as r, \
             open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                count += len(chunk)
                if total > 0:
                    dp.update(int(count * 100 / total), "Downloading clean slate...")
                if dp.iscanceled():
                    dp.close()
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    return False

        dp.update(0, "Verifying download...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad_file = zf.testzip()
        if bad_file:
            raise zipfile.BadZipFile(f"Corrupt file in zip: {bad_file}")

        dp.update(0, "Wiping Kodi...")
        wipe_kodi()

        dp.update(0, "Restoring clean slate...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files       = zf.infolist()
            total_files = len(files)
            for i, zipped_file in enumerate(files):
                if i % 100 == 0:
                    dp.update(
                        int(i * 100 / total_files),
                        f"Restoring: {zipped_file.filename[:35]}"
                    )
                zf.extract(zipped_file, HOME)

        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return True

    except Exception as e:
        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        xbmcgui.Dialog().ok(
            "Fresh Start Error",
            f"Fresh Start failed:\n\n{str(e)}\n\n"
            "Your existing setup has not been modified."
        )
        return False


# ---------------------------------------------------------------------------
# Build Installation
# ---------------------------------------------------------------------------
def install_build(url, name, version, build_id,
                  dev_mode=False, firstrun_steps=None, extra_headers=None):
    """
    Downloads, verifies, and installs a build zip.

    dev_mode=True     — skips writing firstrun.txt so First Run Setup does
                        not trigger on the next boot (maintenance use).
    firstrun_steps    — optional list of step names written to firstrun_steps.txt
                        so service.py only runs those steps. None = all steps.
    extra_headers     — optional dict of HTTP headers for the download request
                        (used to pass the Bearer token for the admin build).
    """
    zip_path = os.path.join(HOME, "build.zip")

    # ── Build switch warning ───────────────────────────────────────────────
    installed_id, installed_version = get_installed_info()
    if installed_id and installed_id != build_id:
        installed_name = BUILD_NAMES.get(installed_id, installed_id)
        if not xbmcgui.Dialog().yesno(
            "Replace Existing Build?",
            f"You currently have [B]{installed_name} v{installed_version}[/B] installed.\n\n"
            f"Installing [B]{name} v{version}[/B] will completely replace it and "
            f"wipe your current setup.\n\n"
            "Are you sure you want to continue?"
        ):
            return

    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", f"Downloading {name}...")

    try:
        # ── 1. Download ───────────────────────────────────────────────────
        context = ssl._create_unverified_context()
        headers = {'User-Agent': 'Kodi-Wizard'}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=context) as r, open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                count += len(chunk)
                if total > 0:
                    dp.update(int(count * 100 / total), f"Downloading {name}...")
                if dp.iscanceled():
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    dp.close()
                    return

        # ── 2. Verify ─────────────────────────────────────────────────────
        dp.update(0, "Verifying download...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad_file = zf.testzip()
        if bad_file:
            raise zipfile.BadZipFile(f"Corrupt file in zip: {bad_file}")

        # ── 3. Wipe ───────────────────────────────────────────────────────
        dp.update(0, "Preparing for installation...")
        wipe_kodi()

        # ── 4. Extract ────────────────────────────────────────────────────
        dp.update(0, "Extracting build files...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            files       = zf.infolist()
            total_files = len(files)
            for i, zipped_file in enumerate(files):
                if i % 300 == 0:
                    dp.update(
                        int(i * 100 / total_files),
                        f"Extracting: {zipped_file.filename[:35]}"
                    )
                zf.extract(zipped_file, HOME)

        # ── 5. Write trigger files ────────────────────────────────────────
        # installed_version.txt is always written so the update checker and
        # build-switch warning work correctly regardless of dev_mode.
        with open(os.path.join(HOME, 'installed_version.txt'), 'w') as f:
            f.write(f"{build_id}|{version}")

        if dev_mode:
            # Maintenance mode — do NOT write firstrun.txt.
            # Kodi boots normally with no setup wizard.
            xbmc.log(
                f"[CutCableWizard] Dev mode — firstrun suppressed for {build_id}.",
                xbmc.LOGINFO
            )
        else:
            with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f:
                f.write("pending")
            # If specific steps were requested (e.g. admin build), write the
            # list so service.py knows to skip everything else.
            if firstrun_steps:
                with open(FIRSTRUN_STEPS_FILE, 'w') as f:
                    f.write(','.join(firstrun_steps))

        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)

        # ── 6. Inform user then force-close ───────────────────────────────
        if dev_mode:
            xbmcgui.Dialog().ok(
                "Install Complete [DEV MODE]",
                f"[B]{name} v{version}[/B] has been applied.\n\n"
                "[B]Developer mode:[/B] First Run Setup will NOT run — "
                "Kodi will boot normally so you can make changes.\n\n"
                "Kodi will now force close."
            )
        else:
            xbmcgui.Dialog().ok(
                "Install Complete",
                f"[B]{name} v{version}[/B] has been applied!\n\n"
                "Kodi must now FORCE CLOSE to load the new skin.\n\n"
                "[B]IMPORTANT:[/B] After you re-open Kodi, please wait "
                "approximately 45 seconds for the First Run Setup to begin automatically."
            )
        os._exit(1)

    except Exception as e:
        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        xbmcgui.Dialog().ok(
            "Installation Error",
            f"Installation failed:\n\n{str(e)}\n\n"
            "Your existing setup has not been modified."
        )


# ---------------------------------------------------------------------------
# Update Check  (called after main menu – daily check is in service.py)
# ---------------------------------------------------------------------------
def check_for_updates(manifest):
    """
    Compares the installed build version against the manifest.
    Prompts the user to update if a newer version is available.
    """
    if not manifest:
        return

    build_id, installed_version = get_installed_info()
    if not build_id or not installed_version:
        return

    builds        = manifest.get('builds', [])
    current_build = next((b for b in builds if b['id'] == build_id), None)
    if not current_build:
        return

    latest_version = current_build.get('version', '')
    if latest_version and latest_version != installed_version:
        if xbmcgui.Dialog().yesno(
            "Update Available",
            f"A new version of [B]{current_build['name']}[/B] is available!\n\n"
            f"  Installed : v{installed_version}\n"
            f"  Available : v{latest_version}\n\n"
            "Would you like to update now?"
        ):
            install_build(
                url            = current_build['download_url'],
                name           = current_build['name'],
                version        = latest_version,
                build_id       = build_id,
                firstrun_steps = current_build.get('firstrun_steps')
            )


# ---------------------------------------------------------------------------
# Main Menu
# ---------------------------------------------------------------------------
def main_menu():
    global _admin_mode

    manifest = get_json(MANIFEST_URL)
    title    = "CutCable Wizard [ADMIN MODE]" if _admin_mode else "CutCable Wizard"
    options  = ["Install Build", "Fresh Start", "Admin Mode"]
    choice   = xbmcgui.Dialog().select(title, options)

    # ── Admin Mode ─────────────────────────────────────────────────────────
    if choice == 2:
        if _admin_mode:
            xbmcgui.Dialog().ok("Admin Mode", "Admin mode is already active.")
        else:
            unlock_admin_mode()
        # Re-open menu so title updates to [ADMIN MODE] on success
        main_menu()
        return

    # ── Install Build ──────────────────────────────────────────────────────
    if choice == 0:
        if not manifest:
            xbmcgui.Dialog().ok(
                "Error",
                "Could not reach the build server.\n"
                "Please check your internet connection."
            )
            return

        # Public builds — always visible
        builds = [b for b in manifest.get('builds', [])
                  if not b.get('admin_only', False)]

        # Admin builds — only visible when admin mode is active.
        # The fresh start build is excluded even in admin mode since it is
        # used internally by the Fresh Start menu option only.
        if _admin_mode:
            admin_builds = [b for b in manifest.get('builds', [])
                            if b.get('admin_only', False)
                            and b['id'] != FRESH_START_BUILD_ID]
            builds = builds + admin_builds

        items = []
        for b in builds:
            size_mb  = b.get('size_mb', 0)
            size_str = f"{size_mb} MB" if size_mb else "N/A"
            item = xbmcgui.ListItem(
                label  = f"{b['name']}  |  v{b['version']}  |  {size_str}",
                label2 = b.get('description', '')
            )
            items.append(item)

        sel = xbmcgui.Dialog().select(title, items, useDetails=True)
        if sel != -1:
            selected       = builds[sel]
            is_admin_build = selected.get('admin_only', False)

            install_build(
                url            = selected['download_url'],
                name           = selected['name'],
                version        = selected['version'],
                build_id       = selected['id'],
                dev_mode       = _admin_mode,
                firstrun_steps = selected.get('firstrun_steps'),
                # Admin build download is gated by the Cloudflare Worker —
                # pass the cached password as a Bearer token so the Worker
                # can verify it server-side before streaming the zip.
                extra_headers  = {'Authorization': f'Bearer {_admin_password_cache}'}
                                 if is_admin_build else None
            )

    # ── Fresh Start ────────────────────────────────────────────────────────
    elif choice == 1:
        if smart_fresh_start(manifest):
            xbmcgui.Dialog().ok(
                "Fresh Start Complete",
                "Kodi has been wiped and restored to a clean slate.\n\n"
                "Unknown Sources are enabled and the CutCableWizard is ready.\n\n"
                "Kodi will now close. Reopen it when you are ready to install a build."
            )
            os._exit(1)

    # ── Post-menu update check ────────────────────────────────────────────
    check_for_updates(manifest)


if __name__ == '__main__':
    main_menu()