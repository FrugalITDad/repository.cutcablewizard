import xbmc, xbmcgui, xbmcaddon, os, shutil, urllib.request, json, ssl, zipfile, xbmcvfs

# ---------------------------------------------------------------------------
# Addon Constants
# ---------------------------------------------------------------------------
ADDON    = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HOME     = xbmcvfs.translatePath("special://home/")

MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

# Addons preserved during fresh start (folder names inside /addons)
PROTECTED_ADDONS = {'plugin.program.cutcablewizard', 'repository.cutcablewizard'}

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
def smart_fresh_start(silent=False):
    """
    Wipes Kodi completely, preserving only:
      - addons/plugin.program.cutcablewizard
      - addons/repository.cutcablewizard
      - userdata/addon_data/plugin.program.cutcablewizard  (wizard prefs)
    Also deletes packages/, temp/, and Database/ in full.
    After the wipe applies two Kodi settings:
      - Unknown Sources  → ON
      - Addon updates    → Any Repositories
    """
    if not silent:
        if not xbmcgui.Dialog().yesno(
            "Fresh Start",
            "This will completely wipe your Kodi installation.\n"
            "Only the CutCableWizard addon and repository will be preserved.\n\n"
            "Are you absolutely sure?"
        ):
            return False

    # ── addons folder ──────────────────────────────────────────────────────
    addons_path = os.path.join(HOME, 'addons')
    if os.path.exists(addons_path):
        for item in os.listdir(addons_path):
            if item in PROTECTED_ADDONS:
                continue
            full = os.path.join(addons_path, item)
            try:
                shutil.rmtree(full, ignore_errors=True) if os.path.isdir(full) else os.remove(full)
            except Exception:
                pass

    # ── userdata folder ────────────────────────────────────────────────────
    userdata_path = os.path.join(HOME, 'userdata')
    if os.path.exists(userdata_path):
        for item in os.listdir(userdata_path):
            full = os.path.join(userdata_path, item)

            if item == 'addon_data' and os.path.isdir(full):
                # Inside addon_data keep only the wizard's own settings
                for addon_folder in os.listdir(full):
                    if addon_folder == 'plugin.program.cutcablewizard':
                        continue
                    sub = os.path.join(full, addon_folder)
                    try:
                        shutil.rmtree(sub, ignore_errors=True) if os.path.isdir(sub) else os.remove(sub)
                    except Exception:
                        pass
                continue  # done with addon_data, move to next item

            try:
                shutil.rmtree(full, ignore_errors=True) if os.path.isdir(full) else os.remove(full)
            except Exception:
                pass

    # ── Full wipe: packages, temp, Database ───────────────────────────────
    for folder in ['packages', 'temp', 'Database']:
        path = os.path.join(HOME, folder)
        if os.path.exists(path):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass

    # ── Clean up HOME root trigger files so they don't fire after the wipe ─
    # firstrun.txt must be deleted here — if a build was previously installed
    # it would survive the folder wipes and wrongly trigger First Run setup
    # on the next boot.
    for trigger in ['firstrun.txt', 'installed_version.txt', 'last_update_check.txt']:
        path = os.path.join(HOME, trigger)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    # ── Write post-fresh-start trigger ────────────────────────────────────
    # We CANNOT apply Kodi settings (unknown sources, addon updates) here
    # because guisettings.xml was just deleted and os._exit(1) is called
    # immediately after — any in-memory changes would be lost.
    # service.py detects this trigger on the next boot and applies the
    # settings once Kodi is fully initialised with a fresh database.
    try:
        with open(os.path.join(HOME, 'post_fresh_start.txt'), 'w') as f:
            f.write("pending")
    except Exception:
        pass

    return True


# ---------------------------------------------------------------------------
# Build Installation
# ---------------------------------------------------------------------------
def install_build(url, name, version, build_id):
    # Write the zip directly to HOME which is guaranteed to exist and be
    # writable on all Android/FireTV devices. special://temp/ resolves to a
    # path that Kodi may not have created yet, causing the "no such file"
    # error even after makedirs — HOME has no such issue.
    zip_path = os.path.join(HOME, "build.zip")
    xbmc.log(f"[CutCableWizard] Zip download path: {zip_path}", xbmc.LOGINFO)
    xbmc.log(f"[CutCableWizard] HOME exists: {os.path.exists(HOME)}", xbmc.LOGINFO)

    # Wipe first (silent – user already confirmed via build selection)
    smart_fresh_start(silent=True)

    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", f"Downloading {name}...")

    try:
        # ── 1. Download ───────────────────────────────────────────────────
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
                    return

        # ── 2. Extract ────────────────────────────────────────────────────
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

        # ── 3. Write trigger files ────────────────────────────────────────
        with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f:
            f.write("pending")
        # Store build_id|version so the update checker knows which build
        # is installed and can compare against the manifest correctly.
        with open(os.path.join(HOME, 'installed_version.txt'), 'w') as f:
            f.write(f"{build_id}|{version}")

        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)

        # ── 4. Inform user then force-close ───────────────────────────────
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
        xbmcgui.Dialog().ok("Installation Error", f"Installation failed:\n\n{str(e)}")


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
        names  = [f"{b['name']} (v{b['version']})" for b in builds]
        sel    = xbmcgui.Dialog().select("Select a Build", names)
        if sel != -1:
            install_build(
                builds[sel]['download_url'],
                builds[sel]['name'],
                builds[sel]['version'],
                builds[sel]['id']
            )

    elif choice == 1:
        if smart_fresh_start():
            xbmcgui.Dialog().ok(
                "Fresh Start Complete",
                "Kodi has been wiped and Unknown Sources have been enabled.\n\n"
                "Kodi will now close. Reopen it when you are ready to install a build."
            )
            os._exit(1)

    # ── Post-menu update check ────────────────────────────────────────────
    # Runs whenever the user closes the menu without triggering an os._exit.
    # (install_build and fresh start both call os._exit so they never reach here.)
    check_for_updates(manifest)


if __name__ == '__main__':
    main_menu()