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
    """Get build metadata from GitHub Releases or repo"""
    info_url = f"https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/repo/zips/builds/{build_id}/build-info.json"
    try:
        with urllib.request.urlopen(info_url) as response:
            return json.loads(response.read())
    except:
        # Fallback to direct release URL
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
        dialog.create("CutCableWizard", f"Downloading {build_id} ({build_info.get('size_mb', 'Unknown')}MB)...")
        dialog.update(0)
        
        # Download with progress
        with urllib.request.urlopen(download_url) as response, open(local_path, 'wb') as out_file:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = int(100 * downloaded / total_size)
                    dialog.update(percent)
        
        dialog.close()
        xbmcgui.Dialog().ok("Download Complete", f"{build_id} downloaded successfully!")
        return local_path
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().ok("Download Failed", f"Could not download {build_id}.\nCheck internet connection.")
        xbmc.log(f"CutCableWizard download error: {str(e)}", xbmc.LOGERROR)
        return None

def backup_current():
    """Run EZ Maintenance+ backup before install"""
    dialog = xbmcgui.Dialog()
    if dialog.yesno("Backup Current", "Create backup of current setup?"):
        try:
            xbmc.executebuiltin('RunAddon("peno64.ezmaintenance")')
            xbmc.sleep(2000)  # Wait for backup to complete
            xbmcgui.Dialog().ok("Backup", "Backup completed. Ready to install new build.")
        except:
            xbmcgui.Dialog().ok("Backup", "Backup skipped.")

def install_build(zip_path, build_id):
    dialog = xbmcgui.Dialog()
    if not dialog.yesno("Ready to Install", f"Install {build_id} build?\n\nYour current setup will be replaced."):
        return False
    
    dialog = xbmcgui.DialogProgress()
    dialog.create("CutCableWizard", "Installing build...")
    dialog.update(25)
    
    # Enable file browsing
    cmd = 'Skin.SetBool(propname="EnableFileBrowse",value="true")'
    xbmc.executebuiltin(cmd)
    dialog.update(50)
    
    # Install ZIP using correct Kodi method
    success = xbmc.executebuiltin(f'ZipFile("{zip_path}",=special://home/)')
    
    dialog.update(75, "Finalizing...")
    xbmc.sleep(2000)
    
    if success:
        dialog.close()
        xbmcgui.Dialog().ok("Success!", f"{build_id} installed!\n\nKodi will restart in 5 seconds.")
        xbmc.executebuiltin('RestartApp')
        return True
    else:
        dialog.close()
        xbmcgui.Dialog().ok("Install Failed", "Build installation failed.\nCheck Kodi log for details.")
        return False

def main():
    dialog = xbmcgui.Dialog()
    choice = dialog.select("CutCableWizard", ["Install Build", "Maintenance Tools"])
    
    if choice == 1:
        # Maintenance tools (EZ Maintenance+)
        try:
            xbmc.executebuiltin('RunAddon("peno64.ezmaintenance")')
        except:
            xbmcgui.Dialog().ok("Maintenance", "EZ Maintenance+ not found. Install from repository.")
        return
    
    # Build installation flow
    build_id = select_build()
    if not build_id:
        return
    
    # Show build info
    build_info = get_build_info(build_id)
    dialog.ok("Selected Build", 
              f"[COLOR lime]{BUILD_OPTIONS[[id for (id, label) in BUILD_OPTIONS].index(build_id)][1]}[/COLOR]\n\n"
              f"Version: {build_info.get('version', '1.0.0')}\n"
              f"Size: {build_info.get('size_mb', 'Unknown')}MB")
    
    # Backup current setup
    backup_current()
    
    # Download and install
    zip_path = download_build(build_id)
    if zip_path:
        install_build(zip_path, build_id)

if __name__ == "__main__":
    main()
