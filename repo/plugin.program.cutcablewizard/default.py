import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil, re, sqlite3

# --- CONFIG ---
ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard'
REPO_ID = 'repository.cutcablewizard'
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as r:
            return json.loads(r.read())
    except: return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe all builds but KEEP Wizard and Repo?"):
            return False
    
    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, 'addons')
    userdata_path = os.path.join(home, 'userdata')
    keep = [ADDON_ID, REPO_ID, 'packages', 'temp']
    
    dp = xbmcgui.DialogProgress()
    dp.create("Wizard", "Cleaning System...")
    
    try:
        # Clean Addons
        for folder in os.listdir(addons_path):
            if folder not in keep:
                shutil.rmtree(os.path.join(addons_path, folder), ignore_errors=True)
        # Clean Userdata
        for folder in os.listdir(userdata_path):
            if folder not in ['addon_data', 'Database']:
                shutil.rmtree(os.path.join(userdata_path, folder), ignore_errors=True)
        
        # Reset Unknown Sources
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')
        dp.close()
        return True
    except:
        dp.close()
        return False

def install_build(url, build_id, version):
    # 1. Ask for Fresh Start first (Recommended for Android)
    do_fresh = xbmcgui.Dialog().yesno("Build Install", "Perform Fresh Start before installing? (Recommended)")
    if do_fresh:
        smart_fresh_start(silent=True)

    path = os.path.join(ADDON_DATA, "temp.zip")
    dp = xbmcgui.DialogProgress()
    dp.create("CutCable Wizard", "Downloading...")
    
    try:
        # Download
        urllib.request.urlretrieve(url, path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs)))
        
        # Extract
        dp.update(0, "Extracting Build...")
        home = xbmcvfs.translatePath("special://home/")
        with zipfile.ZipFile(path, "r") as zf:
            zf.extractall(home)
        
        # 2. Force Skin via AdvancedSettings
        adv_file = xbmcvfs.translatePath("special://userdata/advancedsettings.xml")
        with open(adv_file, "w") as f:
            f.write('<advancedsettings><lookandfeel><skin>skin.aeonnox.silvo</skin></lookandfeel></advancedsettings>')

        # 3. Write Trigger for Service
        if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        ADDON.setSetting(f"ver_{build_id}", version)

        dp.close()
        xbmcgui.Dialog().ok("Complete", "Build Installed! Restart Kodi and WAIT 20 seconds for the skin to load.")
        os._exit(1)
    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    options = ["Install Build", "Smart Fresh Start"]
    choice = xbmcgui.Dialog().select("CutCable Wizard", options)
    
    if choice == 0:
        manifest = get_json(MANIFEST_URL)
        if not manifest: return
        builds = manifest.get("builds", [])
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        b_choice = xbmcgui.Dialog().select("Select Build", names)
        if b_choice != -1:
            sel = builds[b_choice]
            install_build(sel['download_url'], sel['id'], sel['version'])
    elif choice == 1:
        if smart_fresh_start():
            xbmcgui.Dialog().ok("Done", "Kodi cleaned. Restarting...")
            os._exit(1)

if __name__ == '__main__':
    main()
