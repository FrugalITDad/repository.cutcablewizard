import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmc
import urllib.request
import os
import json

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

def get_build_info(build_id):
    info_url = f"https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/repo/zips/builds/{build_id}/build-info.json"
    try:
        with urllib.request.urlopen(info_url) as response:
            return json.loads(response.read())
    except:
        return {
            "version": "1.0.0",
            "download_url": f"https://github.com/FrugalITDad/repository.cutcablewizard/releases/download/v1.0.0/{build_id}-build-1.0.0.zip",
            "size_mb": 175
        }

def download_build(build_id):
    build_info = get_build_info(build_id)
    download_url = build_info.get('download_url', f"https://github.com/FrugalITDad/repository.cutcablewizard/releases/download/v1.0.0/{build_id}-build-1.0.0.zip")
    local_path = os.path.join(ADDON_DATA, f"temp_{build_id}.zip")
    
    try:
        dialog = xbmcgui.DialogProgress()
        dialog.create("CutCableWizard", f"Downloading {build_id}...")
        dialog.update(0)
        
        urllib.request.urlretrieve(download_url, local_path, lambda nb, bs, size: dialog.update(int(100 * nb * bs / (size or 1))))
        dialog.close()
        return local_path
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().ok("Download Failed", f"Could not download {build_id}.\nError: {str(e)[:100]}")
        return None

def backup_current():
    dialog = xbmcgui.Dialog()
    if dialog.yesno("Backup Current", "Create backup before installing?"):
        xbmcgui.Dialog().ok("Backup", "Please run EZ Maintenance+ backup manually,\nthen select this build again.")

def install_build(zip_path, build_id):
    dialog = xbmcgui.Dialog()
    if not dialog.yesno("Ready to Install", f"Click OK to install {build_id}.\n\nMANUAL STEP: Go to Add-ons → Install from zip → select the downloaded ZIP"):
        return False
    
    xbmcgui.Dialog().ok("Next Steps",
        "1. Go to: Add-ons → Install from zip file\n"
        "2. Browse: {ADDON_DATA}\n"
        "3. Select: temp_{build_id}.zip\n"
        "4. Install → Kodi will restart")
    
    return True

def main():
    dialog = xbmcgui.Dialog()
    choice = dialog.select("CutCableWizard", ["Install Build", "Maintenance"])
    
    if choice == 1:
        try:
            xbmc.executebuiltin('RunAddon("peno64.ezmaintenance")')
        except:
            xbmcgui.Dialog().ok("Maintenance", "EZ Maintenance+ not installed.")
        return
    
    build_id = select_build()
    if not build_id:
        return
    
    build_info = get_build_info(build_id)
    dialog.ok("Build Ready", f"[COLOR lime]{build_id}[/COLOR]\nVersion: {build_info['version']}\n\nZIP downloaded to:\n{ADDON_DATA}temp_{build_id}.zip")
    
    backup_current()
    install_build(None, build_id)

if __name__ == "__main__":
    main()
