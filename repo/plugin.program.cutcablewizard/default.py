import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmc
import urllib.request
import os
import json
import ssl

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
    """One-click automatic build installation"""
    dialog = xbmcgui.DialogProgress()
    dialog.create("CutCableWizard", "Installing build...")

    # Enable unknown sources (required for ZIP installs)
    xbmc.executebuiltin('SetGUIOption(GUIInfo.156,true)')
    xbmc.sleep(1000)

    # Copy ZIP to Kodi's temp install location
    temp_install_path = "special://temp/temp_build.zip"
    xbmcvfs.copy(zip_path, xbmcvfs.translatePath(temp_install_path))

    dialog.update(50)

    # Trigger ZIP installation via Kodi's native installer
    xbmc.executebuiltin('Skin.SetBool(EnableFileBrowse,true)')
    xbmc.executebuiltin(f'RunScript(special://xbmc/system/python/lib.py,"{temp_install_path}")')
    xbmc.sleep(3000)

    dialog.update(75, "Restarting Kodi...")
    xbmc.sleep(2000)

    # Clean up
    try:
        xbmcvfs.delete(zip_path)
        xbmcvfs.delete(xbmcvfs.translatePath(temp_install_path))
    except Exception:
        pass

    dialog.close()
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
