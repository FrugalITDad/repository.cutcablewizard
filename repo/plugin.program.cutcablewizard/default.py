import xbmc, xbmcgui, xbmcaddon, os, shutil, urllib.request, json, ssl, zipfile, xbmcvfs

# ---------------------------------------------------------------------------
# Addon Constants
# ---------------------------------------------------------------------------
ADDON    = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HOME     = xbmcvfs.translatePath("special://home/")

MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

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
        # Legacy file that only stored a version number – cannot match a build
        return None, data.strip()
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Fresh Start
# ---------------------------------------------------------------------------

FRESH_START_BUILD_ID  = 'cordcutter_fresh_start'

def wipe_kodi():
    """
    Core wipe routine shared by both smart_fresh_start() and install_build().
    Deletes all Kodi folders and HOME root trigger files completely.
    Nothing is preserved — the caller is responsible for extracting a zip
    immediately after so Kodi always boots into a known good state.
    """
    # ── addons ────────────────────────────────────────────────────────────
    for folder in ['addons', 'userdata', 'packages', 'temp', 'Database']:
        path = os.path.join(HOME, folder)
        if os.path.exists(path):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

    # ── HOME root trigger files ───────────────────────────────────────────
    for trigger in ['firstrun.txt', 'installed_version.txt',
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
      2. Fetch the clean slate build URL from the manifest
      3. Download and verify the zip (user's existing setup untouched until here)
      4. Wipe everything
      5. Extract clean slate zip (bakes in Unknown Sources ON + Any Repositories
         + wizard + repo — no post-boot JSON-RPC calls needed)
      6. Force close so Kodi boots into the clean slate

    The clean slate zip replaces the old post_fresh_start.txt trigger approach.
    Settings are guaranteed to be correct because they are baked into the zip's
    guisettings.xml rather than applied via JSON-RPC after the fact.
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

    # ── Find the clean slate build in the manifest ────────────────────────
    builds = manifest.get('builds', [])
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
        # ── 1. Download ───────────────────────────────────────────────────
        context = ssl._create_unverified_context()
        url = fresh_build['download_url']
        with urllib.request.urlopen(url, context=context) as r, open(zip_path, 'wb') as f:
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

        # ── 2. Verify ─────────────────────────────────────────────────────
        dp.update(0, "Verifying download...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                bad_file = zf.testzip()
            if bad_file:
                raise zipfile.BadZipFile(f"Corrupt file in zip: {bad_file}")
        except zipfile.BadZipFile as e:
            dp.close()
            if os.path.exists(zip_path):
                os.remove(zip_path)
            xbmcgui.Dialog().ok(
                "Fresh Start Error",
                f"The clean slate download appears to be corrupt.\n\n{str(e)}\n\n"
                "Your existing setup has not been touched. Please try again."
            )
            return False

        # ── 3. Wipe ───────────────────────────────────────────────────────
        dp.update(0, "Wiping Kodi...")
        wipe_kodi()

        # ── 4. Extract clean slate ────────────────────────────────────────
        dp.update(0, "Restoring clean slate...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.infolist()
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

# Human-readable names for build IDs used in the switch-build warning.
BUILD_NAMES = {
    'cordcutter_base':         'CordCutter Base',
    'cordcutter_plus':         'CordCutter Plus',
    'cordcutter_plus_gaming':  'CordCutter Plus w Gaming',
    'cordcutter_pro':          'CordCutter Pro',
    'cordcutter_pro_gaming':   'CordCutter Pro w Gaming',
}

def install_build(url, name, version, build_id):
    zip_path = os.path.join(HOME, "build.zip")
    xbmc.log(f"[CutCableWizard] Zip download path: {zip_path}", xbmc.LOGINFO)
    xbmc.log(f"[CutCableWizard] HOME exists: {os.path.exists(HOME)}", xbmc.LOGINFO)

    # ── 0. Warn if a different build is already installed ─────────────────
    # Reads installed_version.txt to check what is currently on the device.
    # If it is a different build (not just a version update of the same one)
    # we show a clear warning so the user knows what will be replaced.
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
            return  # User cancelled — leave current build untouched

    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", f"Downloading {name}...")

    try:
        # ── 1. Download ───────────────────────────────────────────────────
        # Download is done BEFORE the wipe. If the download fails the user's
        # existing Kodi setup is left completely intact — nothing is lost.
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(url, context=context) as r, open(zip_path, 'wb') as f:
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

        # ── 2. Verify zip before wiping ───────────────────────────────────
        # Confirms the downloaded file is a valid zip. If it is corrupt or
        # incomplete the wipe is aborted and the user keeps their current setup.
        dp.update(0, "Verifying download...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                bad_file = zf.testzip()
            if bad_file:
                raise zipfile.BadZipFile(f"Corrupt file in zip: {bad_file}")
        except zipfile.BadZipFile as e:
            dp.close()
            if os.path.exists(zip_path):
                os.remove(zip_path)
            xbmcgui.Dialog().ok(
                "Download Error",
                f"The downloaded build file appears to be corrupt.\n\n"
                f"{str(e)}\n\n"
                "Your existing setup has not been touched. Please try again."
            )
            return

        # ── 3. Wipe ───────────────────────────────────────────────────────
        # Only reached if download and verification both succeeded.
        dp.update(0, "Preparing for installation...")
        wipe_kodi()

        # ── 4. Extract ────────────────────────────────────────────────────
        dp.update(0, "Extracting build files...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            total_files = len(files)
            for i, zipped_file in enumerate(files):
                if i % 300 == 0:
                    dp.update(
                        int(i * 100 / total_files),
                        f"Extracting: {zipped_file.filename[:35]}"
                    )
                zf.extract(zipped_file, HOME)

        # ── 5. Write trigger files ────────────────────────────────────────
        with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f:
            f.write("pending")
        with open(os.path.join(HOME, 'installed_version.txt'), 'w') as f:
            f.write(f"{build_id}|{version}")

        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)

        # ── 6. Inform user then force-close ───────────────────────────────
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
    Only runs if a known build is installed.
    """
    if not manifest:
        return

    build_id, installed_version = get_installed_info()
    if not build_id or not installed_version:
        return  # No recognised build installed, nothing to compare

    builds = manifest.get('builds', [])
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
                current_build['download_url'],
                current_build['name'],
                latest_version,
                build_id
            )


# ---------------------------------------------------------------------------
# Main Menu
# ---------------------------------------------------------------------------
def main_menu():
    manifest = get_json(MANIFEST_URL)

    options = ["Install Build", "Fresh Start"]
    choice  = xbmcgui.Dialog().select("CutCable Wizard", options)

    if choice == 0:
        if not manifest:
            xbmcgui.Dialog().ok("Error", "Could not reach the build server.\nPlease check your internet connection.")
            return
        # Filter out admin-only builds for regular users
        builds = [b for b in manifest.get('builds', []) if not b.get('admin_only', False)]

        # Build a ListItem per build so the select dialog shows:
        #   Line 1 (label)  — Name, version and size
        #   Line 2 (label2) — Description from builds.json
        # Requires useDetails=True which is supported from Kodi 19 onwards.
        items = []
        for b in builds:
            size_mb = b.get('size_mb', 0)
            size_str = f"{size_mb} MB" if size_mb else "Unknown size"
            item = xbmcgui.ListItem(
                label  = f"{b['name']}  |  v{b['version']}  |  {size_str}",
                label2 = b.get('description', '')
            )
            items.append(item)

        sel = xbmcgui.Dialog().select("Select a Build", items, useDetails=True)
        if sel != -1:
            install_build(
                builds[sel]['download_url'],
                builds[sel]['name'],
                builds[sel]['version'],
                builds[sel]['id']
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

    # ── Post-menu update check ────────────────────────────────────────────
    # Runs whenever the user closes the menu without triggering an os._exit.
    # (install_build and fresh start both call os._exit so they never reach here.)
    check_for_updates(manifest)


if __name__ == '__main__':
    main_menu()