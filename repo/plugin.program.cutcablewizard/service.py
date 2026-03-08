import xbmc
import xbmcaddon
import xbmcgui
import urllib.request
import json
import os

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmc.translatePath(ADDON.getAddonInfo("profile"))

MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"


def get_json(url):

    try:
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read().decode())
    except:
        return None


def is_skin_busy():

    return (
        xbmc.getCondVisibility("Window.IsActive(busydialog)") or
        xbmc.getCondVisibility("Library.IsScanningVideo") or
        xbmc.getCondVisibility("Library.IsScanningMusic")
    )


def check_for_build_update():

    version_file = os.path.join(ADDON_DATA, "installed_version.txt")

    if not os.path.exists(version_file):
        return

    try:
        with open(version_file) as f:
            current = f.read().strip()
    except:
        return

    manifest = get_json(MANIFEST_URL)

    if not manifest:
        return

    builds = manifest.get("builds", [])

    for build in builds:

        latest = build.get("version")

        if latest and latest != current:

            xbmcgui.Dialog().notification(
                "CordCutter Wizard",
                f"New build available: {latest}",
                xbmcgui.NOTIFICATION_INFO,
                5000
            )

            break


def run_service():

    xbmc.sleep(15000)

    while is_skin_busy():
        xbmc.sleep(2000)

    check_for_build_update()


if __name__ == "__main__":
    run_service()