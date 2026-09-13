import xbmc, xbmcgui, xbmcaddon, os, shutil, urllib.request, json, ssl, zipfile, xbmcvfs

# ---------------------------------------------------------------------------
# Addon Constants
# ---------------------------------------------------------------------------
ADDON    = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HOME     = xbmcvfs.translatePath("special://home/")

MANIFEST_URL        = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
FIRSTRUN_STEPS_FILE = os.path.join(HOME, 'firstrun_steps.txt')

BUILD_NAMES = {
    'cordcutter_base':         'CordCutter Base',
    'cordcutter_plus':         'CordCutter Plus',
    'cordcutter_plus_gaming':  'CordCutter Plus w Gaming',
    'cordcutter_pro':          'CordCutter Pro',
    'cordcutter_pro_gaming':   'CordCutter Pro w Gaming',
    'cordcutter_admin':        'CordCutter Admin',
}

HIDDEN_BUILD_IDS = {'cordcutter_fresh_start'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_json(url):
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard'})
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


def load_admin_settings():
    url   = ADDON.getSetting('admin_build_url').strip()
    token = ADDON.getSetting('admin_token').strip()
    if url and token:
        return url, token
    return None, None


# ---------------------------------------------------------------------------
# Fresh Start
# ---------------------------------------------------------------------------
FRESH_START_BUILD_ID = 'cordcutter_fresh_start'


def wipe_kodi():
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

    builds      = manifest.get('builds', [])
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
                  firstrun_steps=None, extra_headers=None):
    zip_path = os.path.join(HOME, "build.zip")

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

        dp.update(0, "Verifying download...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad_file = zf.testzip()
        if bad_file:
            raise zipfile.BadZipFile(f"Corrupt file in zip: {bad_file}")

        dp.update(0, "Preparing for installation...")
        wipe_kodi()

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

        with open(os.path.join(HOME, 'installed_version.txt'), 'w') as f:
            f.write(f"{build_id}|{version}")

        with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f:
            f.write("pending")

        if firstrun_steps:
            with open(FIRSTRUN_STEPS_FILE, 'w') as f:
                f.write(','.join(firstrun_steps))

        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)

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
# Re-run First Run Setup
# ---------------------------------------------------------------------------
def trigger_first_run_setup(manifest):
    build_id, version = get_installed_info()
    if not build_id:
        xbmcgui.Dialog().ok(
            "First Run Setup",
            "No build is currently installed.\n\n"
            "Please install a build first before running setup."
        )
        return

    firstrun_steps = None
    if manifest:
        builds        = manifest.get('builds', [])
        current_build = next((b for b in builds if b['id'] == build_id), None)
        if current_build:
            firstrun_steps = current_build.get('firstrun_steps')

    if build_id == 'cordcutter_admin' and not firstrun_steps:
        firstrun_steps = ['device_name', 'iptv_sync', 'buffer']

    build_name = BUILD_NAMES.get(build_id, build_id)
    if not xbmcgui.Dialog().yesno(
        "Re-run First Run Setup",
        f"This will restart Kodi and run the First Run Setup wizard for "
        f"[B]{build_name}[/B].\n\n"
        "Any settings previously configured during setup can be updated.\n\n"
        "Are you sure you want to continue?"
    ):
        return

    for addon_id in ['script.simkl', 'plugin.program.iptv.merge']:
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Addons.SetAddonEnabled",
            "params": {"addonid": addon_id, "enabled": False},
            "id": 1
        }))
        xbmc.log(f"[CutCableWizard] Pre-setup: disabled {addon_id}", xbmc.LOGINFO)

    try:
        with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f:
            f.write("pending")
        if firstrun_steps:
            with open(FIRSTRUN_STEPS_FILE, 'w') as f:
                f.write(','.join(firstrun_steps))
        elif os.path.exists(FIRSTRUN_STEPS_FILE):
            os.remove(FIRSTRUN_STEPS_FILE)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", f"Could not write setup trigger files:\n\n{str(e)}")
        return

    xbmcgui.Dialog().ok(
        "First Run Setup Scheduled",
        "Setup has been scheduled.\n\n"
        "Kodi will now close. After you reopen it, please wait approximately "
        "45 seconds for the First Run Setup wizard to appear."
    )
    os._exit(1)


# ---------------------------------------------------------------------------
# Admin Settings
# ---------------------------------------------------------------------------
def configure_admin_settings():
    """
    Prompts for admin build URL and access token using input dialogs.
    Values are stored via ADDON.setSetting() in the addon local data folder.
    """
    current_url   = ADDON.getSetting('admin_build_url').strip()
    current_token = ADDON.getSetting('admin_token').strip()

    status_url   = current_url if current_url else "Not set"
    status_token = "Configured" if current_token else "Not set"

    if not xbmcgui.Dialog().yesno(
        "Admin Settings",
        f"Build URL: [B]{status_url}[/B]\n"
        f"Access Token: [B]{status_token}[/B]\n\n"
        "Would you like to update these settings?"
    ):
        return

    url = xbmcgui.Dialog().input("Admin Build URL", defaultt=current_url)
    if url is None:
        return
    ADDON.setSetting('admin_build_url', url.strip())

    token = xbmcgui.Dialog().input("Access Token", defaultt=current_token)
    if token is None:
        return
    ADDON.setSetting('admin_token', token.strip())

    if url.strip() and token.strip():
        msg = ("Your admin settings have been saved to this device.\n\n"
               "The Admin build will now appear in the Install Build menu.")
    else:
        msg = ("Settings saved.\n\n"
               "Note: both URL and Token must be set for the "
               "Admin build to appear in the menu.")

    xbmcgui.Dialog().ok("Admin Settings Saved", msg)


# ---------------------------------------------------------------------------
# Update Check
# ---------------------------------------------------------------------------
def check_for_updates(manifest):
    if not manifest:
        return

    build_id, installed_version = get_installed_info()
    if not build_id or not installed_version:
        return

    if build_id == 'cordcutter_admin':
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
    manifest = get_json(MANIFEST_URL)

    admin_url, admin_token = load_admin_settings()
    admin_build = None
    if admin_url:
        admin_build = {
            'id':             'cordcutter_admin',
            'name':           'CordCutter Admin',
            'description':    'Personal admin build with pre-configured accounts.',
            'version':        '1.0',
            'size_mb':        0,
            'firstrun_steps': ['device_name', 'iptv_sync', 'buffer'],
        }

    options = ["Install Build", "Fresh Start", "First Run Setup", "Admin Settings"]
    choice  = xbmcgui.Dialog().select("CutCable Wizard", options)

    if choice == 0:
        if not manifest and not admin_build:
            xbmcgui.Dialog().ok(
                "Error",
                "Could not reach the build server.\n"
                "Please check your internet connection."
            )
            return

        builds = []
        if manifest:
            builds = [b for b in manifest.get('builds', [])
                      if b['id'] not in HIDDEN_BUILD_IDS
                      and not b.get('admin_only', False)]

        if admin_build:
            builds.append(admin_build)

        items = []
        for b in builds:
            size_mb  = b.get('size_mb', 0)
            size_str = f"{size_mb} MB" if size_mb else "N/A"
            item = xbmcgui.ListItem(
                label  = f"{b['name']}  |  v{b['version']}  |  {size_str}",
                label2 = b.get('description', '')
            )
            items.append(item)

        sel = xbmcgui.Dialog().select("CutCable Wizard", items, useDetails=True)
        if sel != -1:
            selected       = builds[sel]
            is_admin_build = selected['id'] == 'cordcutter_admin'
            install_build(
                url            = admin_url if is_admin_build else selected['download_url'],
                name           = selected['name'],
                version        = selected['version'],
                build_id       = selected['id'],
                firstrun_steps = selected.get('firstrun_steps'),
                extra_headers  = {'Authorization': f'token {admin_token}'}
                                 if is_admin_build else None
            )

    elif choice == 1:
        if smart_fresh_start(manifest):
            xbmcgui.Dialog().ok(
                "Fresh Start Complete",
                "Kodi has been wiped and restored to a clean slate.\n\n"
                "Unknown Sources are enabled and the CutCableWizard is ready.\n\n"
                "Kodi will now close. Reopen it when you are ready to install a build."
            )
            os._exit(1)

    elif choice == 2:
        trigger_first_run_setup(manifest)

    elif choice == 3:
        configure_admin_settings()

    check_for_updates(manifest)


if __name__ == '__main__':
    main_menu()
