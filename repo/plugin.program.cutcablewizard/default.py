import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import urllib.request
import json
import os
import zipfile

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_DATA = xbmc.translatePath(ADDON.getAddonInfo("profile"))

MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"


def get_json(url):

    try:
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read().decode())
    except:
        xbmcgui.Dialog().ok("CordCutter Wizard", "Failed to download build list.")
        return None


def is_android_tv():

    if xbmc.getCondVisibility("System.Platform.Android"):
        return True

    return False


def optimize_firetv():

    xbmc.executeJSONRPC(json.dumps({
     "jsonrpc":"2.0",
     "method":"Settings.SetSettingValue",
     "params":{"setting":"cache.buffer.mode","value":1},
     "id":1
    }))

    xbmc.executeJSONRPC(json.dumps({
     "jsonrpc":"2.0",
     "method":"Settings.SetSettingValue",
     "params":{"setting":"videoplayer.adjustrefreshrate","value":1},
     "id":1
    }))


def download_build(url, name):

    zip_path = os.path.join(ADDON_DATA, name + ".zip")

    progress = xbmcgui.DialogProgress()
    progress.create("CordCutter Wizard", "Downloading build...")

    try:

        with urllib.request.urlopen(url) as response, open(zip_path, "wb") as out:

            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            block = 8192

            while True:

                buffer = response.read(block)

                if not buffer:
                    break

                downloaded += len(buffer)
                out.write(buffer)

                percent = int(downloaded * 100 / total)
                progress.update(percent, "Downloading build...")

        progress.close()
        return zip_path

    except:
        progress.close()
        xbmcgui.Dialog().ok("CordCutter Wizard", "Download failed.")
        return None


def extract_build(zip_path):

    progress = xbmcgui.DialogProgress()
    progress.create("CordCutter Wizard", "Installing build...")

    home = xbmc.translatePath("special://home/")

    with zipfile.ZipFile(zip_path, "r") as zip_ref:

        total = len(zip_ref.infolist())
        count = 0

        for file in zip_ref.infolist():

            zip_ref.extract(file, home)

            count += 1
            percent = int(count * 100 / total)

            progress.update(percent, "Installing files...")

    progress.close()


def install_build(build):

    if not is_android_tv():

        xbmcgui.Dialog().ok(
            "Unsupported Device",
            "CordCutter builds are designed for Fire TV and Google TV devices."
        )

        return

    confirm = xbmcgui.Dialog().yesno(
        "Install Build",
        f"{build['name']}\n\nVersion: {build['version']}\nSize: {build['size_mb']} MB\n\nInstall now?"
    )

    if not confirm:
        return

    zip_path = download_build(build["download_url"], build["id"])

    if not zip_path:
        return

    extract_build(zip_path)

    version_file = os.path.join(ADDON_DATA, "installed_version.txt")

    with open(version_file, "w") as f:
        f.write(build["version"])

    optimize_firetv()

    xbmcgui.Dialog().ok("CordCutter Wizard", "Build installed successfully.\nRestart Kodi.")


def show_builds():

    manifest = get_json(MANIFEST_URL)

    if not manifest:
        return

    builds = manifest.get("builds", [])

    options = []

    for b in builds:

        options.append(
            f"{b['name']} ({b['size_mb']} MB)\n{b['description']}"
        )

    choice = xbmcgui.Dialog().select("Select Build", options)

    if choice >= 0:

        build = builds[choice]

        xbmcgui.Dialog().textviewer(
            build["name"],
            f"Version: {build['version']}\n\nDescription:\n{build['description']}\n\nChangelog:\n{build['changelog']}"
        )

        install_build(build)


def check_for_updates():

    version_file = os.path.join(ADDON_DATA, "installed_version.txt")

    if not os.path.exists(version_file):
        xbmcgui.Dialog().ok("CordCutter Wizard", "No build currently installed.")
        return

    with open(version_file) as f:
        current_version = f.read().strip()

    manifest = get_json(MANIFEST_URL)

    for build in manifest["builds"]:

        if build["version"] != current_version:

            if xbmcgui.Dialog().yesno(
                "Update Available",
                f"Installed: {current_version}\nLatest: {build['version']}\n\nInstall update?"
            ):
                install_build(build)

            return

    xbmcgui.Dialog().ok("CordCutter Wizard", "You are already on the latest build.")


def fresh_start():

    if xbmcgui.Dialog().yesno(
        "Fresh Start",
        "This will erase your Kodi configuration.\nContinue?"
    ):

        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.indigo/?action=freshstart)")


def main_menu():

    options = [
        "Install Build",
        "Check for Updates",
        "Fresh Start"
    ]

    choice = xbmcgui.Dialog().select("CordCutter Wizard", options)

    if choice == 0:
        show_builds()

    elif choice == 1:
        check_for_updates()

    elif choice == 2:
        fresh_start()


if __name__ == "__main__":
    main_menu()