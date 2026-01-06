import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmc
import urllib.request
import os

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
    base_url = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/repo/zips/builds/%s/build-1.0.0.zip" % build_id
    local_path = os.path.join(ADDON_DATA, "temp_%s.zip" % build_id)
    
    try:
        dialog = xbmcgui.DialogProgress()
        dialog.create("CutCableWizard", "Downloading %s..." % build_id)
        
        urllib.request.urlretrieve(base_url, local_path)
        dialog.close()
        return local_path
    except:
        dialog.close()
        xbmcgui.Dialog().ok("Download Failed", "Could not download %s." % build_id)
        return None

def install_build(zip_path):
    dialog = xbmcgui.Dialog()
    if not dialog.yesno("Install Build", "Install this build?"):
        return False
    
    dialog = xbmcgui.DialogProgress()
    dialog.create("CutCableWizard", "Installing build...")
    
    success = xbmc.executebuiltin('RunAddon("plugin.program.cutcablewizard", "%s")' % zip_path)
    dialog.close()
    
    return success

def main():
    build_id = select_build()
    if not build_id:
        return

    dialog = xbmcgui.Dialog()
    dialog.ok("CutCableWizard", "Selected: %s\n\nDownloading..." % build_id)
    
    zip_path = download_build(build_id)
    if zip_path and install_build(zip_path):
        dialog.ok("Success", "Build %s installed!" % build_id)
    else:
        dialog.ok("Failed", "Build installation failed.")

if __name__ == "__main__":
    main()
