import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmc
import urllib.request
import os
import json
import ssl
import zipfile

ADDON = xbmcaddon.Addon(id="plugin.program.cutcablewizard")
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

BUILD_OPTIONS = [
    ("cordcutter_base",        "CordCutter Base\n\n[COLOR gray]Verified Free Services[/COLOR]"),
    ("cordcutter_pro",         "CordCutter Pro\n\n[COLOR gray]Base with third party addons[/COLOR]"),
    ("cordcutter_plus",        "CordCutter Plus\n\n[COLOR gray]Pro with Jellyfin[/COLOR]"),
    ("cordcutter_basegaming",  "CordCutter Base Gaming\n\n[COLOR gray]Base with gaming[/COLOR]"),
    ("cordcutter_progaming",   "CordCutter Pro Gaming\n\n[COLOR gray]Pro with gaming[/COLOR]"),
    ("cordcutter_plusgaming",  "CordCutter Plus Gaming\n\n[COLOR gray]Plus with gaming[/COLOR]"),
    ("cordcutter_admin",       "CordCutter Admin\n\n[COLOR gray]Admin build only[/COLOR]"),
]

ADMIN_PASSWORD = "2026"


def check_admin_password():
    dialog = xbmcgui.Dialog()
    password = dialog.input("Admin build password:", type=xbmcgui.ALPHANUM_HIDE_INPUT)
    return password == ADMIN_PASSWORD


def select_build():
    labels = [label for (_id, label) in BUILD_OPTIONS]
    dialog = xbmcgui.Dialog()
    choice = dialog.select("Select CordCutter build", labels)
    if choice == -1:
        return None

    build_id = BUILD_OPTIONS[choice][0]
    if build_id == "cordcutter_admin":
        if not check_admin_password():
            dialog.ok("Access Denied", "Incorrect admin password.")
            return None
    return build_id


def download_build(build_id):
    download_url = f"https://github.com/FrugalITDad/repository.cutcablewizard/releases/download/v1.0.0/{build_id}-build-1.0.0.zip"
    local_path = os.path.join(ADDON_DATA, f"temp_{build_id}.zip")

    # Ensure addon data folder exists
    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)

    try:
        dialog = xbmcgui.DialogProgress()
        dialog.create("CutCableWizard", f"Downloading {build_id}...")

        # Set up SSL and User-Agent for GitHub
        ctx = ssl.create_default_context()
        opener = urllib.request.build_opener()
        opener.addheaders = [("User-Agent", "Kodi-CordCutterWizard/1.0")]
        urllib.request.install_opener(opener)

        with urllib.request.urlopen(download_url, context=ctx) as response, open(local_path, "wb") as out_file:
            block_size = 1024 * 1024
            downloaded = 0
            total = int(response.headers.get("Content-Length", "0") or 0)

            while True:
                data = response.read(block_size)
                if not data:
                    break
                out_file.write(data)
                downloaded += len(data)

                if total > 0:
                    percent = int(downloaded * 100 / total)
                    dialog.update(percent)

        dialog.close()
        return local_path

    except Exception as e:
        dialog.close()
        xbmc.log(f"[CutCableWizard] download_build error for {build_id}: {repr(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Download Failed", f"Could not download {build_id}.\n\n{repr(e)}")
        return None


def auto_install_build(zip_path):
    """Extract build over Kodi userdata and restart"""
    dialog = xbmcgui.DialogProgress()
    dialog.create("CutCableWizard", "Installing build...")

    # Resolve paths
    source_path = xbmcvfs.translatePath(zip_path)
    userdata_path = xbmcvfs.translatePath("special://home/userdata/")

    xbmc.log(f"[CutCableWizard] Installing build from {source_path} to {userdata_path}", xbmc.LOGNOTICE)

    try:
        with zipfile.ZipFile(source_path, "r") as zf:
            file_list = zf.infolist()
            total = len(file_list) if file_list else 1

            for idx, member in enumerate(file_list):
                percent = int((idx + 1) * 100 / total)
                dialog.update(percent, "Installing build...", member.filename)

                # Build target path (adjust here if your zip has a wrapper folder to strip)
                target = os.path.join(userdata_path, member.filename)

                if member.is_dir():
                    if not xbmcvfs.exists(target):
                        xbmcvfs.mkdirs(target)
                    continue

                parent = os.path.dirname(target)
                if parent and not xbmcvfs.exists(parent):
                    xbmcvfs.mkdirs(parent)

                with zf.open(member, "r") as source_file:
                    # Use xbmcvfs.File for Kodi paths
                    f = xbmcvfs.File(target, "w")
                    try:
                        f.write(source_file.read())
                    finally:
                        f.close()

    except Exception as e:
        dialog.close()
        xbmc.log(f"[CutCableWizard] Error extracting build: {repr(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Install Failed", f"Error applying build.\n\n{repr(e)}")
        return False

    dialog.update(100, "Finalizing...", "")
    xbmc.sleep(1000)

    try:
        xbmcvfs.delete(source_path)
    except Exception:
        pass

    dialog.close()
    xbmcgui.Dialog().ok("Build Installed", "Kodi will now restart to apply changes.")
    xbmc.executebuiltin('RestartApp')
    return True


def main():
    dialog = xbmcgui.Dialog()
    choice = dialog.select("CutCableWizard", ["Install Build", "Maintenance"])

    if choice == 1:
        try:
            xbmc.executebuiltin('RunAddon("peno64.ezmaintenance")')
        except Exception:
            xbmcgui.Dialog().ok("Maintenance", "EZ Maintenance+ not found.")
        return

    build_id = select_build()
    if not build_id:
        return

    if not xbmcgui.Dialog().yesno("Confirm", f"Install {build_id}?\n\nThis will replace your current setup."):
        return

    # Download
    zip_path = download_build(build_id)
    if not zip_path:
        return

    # Auto install (one click - no user intervention)
    xbmcgui.Dialog().ok("Ready", f"{build_id} will now be installed automatically.\n\nKodi will restart.")
    auto_install_build(zip_path)


if __name__ == "__main__":
    main()
