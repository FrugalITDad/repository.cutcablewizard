import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, shutil, urllib.request, json, ssl, zipfile

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
# We define ADDON_DATA for our config files, but we'll download to TEMP
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
# special://temp/ is the safest place to write files on Android/FireStick
TEMP_DIR = xbmcvfs.translatePath("special://temp/")

MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
WHITELIST = [ADDON_ID, 'packages', 'temp', 'Database']

def get_json(url):
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard'})
        with urllib.request.urlopen(req, context=context, timeout=15) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        xbmc.log(f"Wizard Manifest Error: {str(e)}", xbmc.LOGERROR)
        return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup?\nWizard and repositories will be saved."): 
            return False
    
    home = xbmcvfs.translatePath("special://home/")
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            if item in WHITELIST or item.startswith('repository.'): 
                continue
            
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): 
                    shutil.rmtree(full_path, ignore_errors=True)
                else: 
                    os.remove(full_path)
            except: 
                pass
    
    xbmc.executebuiltin('SaveSceneSettings')
    if not silent:
        xbmcgui.Dialog().ok("Fresh Start", "Cleanup Complete. Kodi will now close.")
        xbmc.executebuiltin("Quit")
    return True

def install_build(url, name, version):
    # Ensure our temp and data directories exist
    if not xbmcvfs.exists(TEMP_DIR): xbmcvfs.mkdirs(TEMP_DIR)
    if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
    
    # Download to TEMP_DIR to bypass Android permission errors in addon_data
    zip_path = os.path.join(TEMP_DIR, "build.zip")
    
    # Wipe old data
    smart_fresh_start(silent=True)
    
    home = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", f"Downloading {name}...")

    try:
        context = ssl._create_unverified_context()
        # Using a higher timeout and a robust buffer for FireSticks
        with urllib.request.urlopen(url, context=context, timeout=30) as r, open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(262144) 
                if not chunk: break
                f.write(chunk)
                count += len(chunk)
                if total > 0: 
                    dp.update(int(count*100/total), f"Downloading: {int(count/1024/1024)}MB / {int(total/1024/1024)}MB")
                if dp.iscanceled(): return
        
        # Extraction
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            total_files = len(files)
            for i, file in enumerate(files):
                if i % 250 == 0: 
                    dp.update(int(i*100/total_files), f"Installing: {file.filename[:30]}")
                zf.extract(file, home)
        
        # Write setup triggers
        # We try-catch this because if addon_data is still locked, we don't want to crash
        try:
            with open(os.path.join(ADDON_DATA, 'firstrun.txt'), 'w') as f: f.write("pending")
            with open(os.path.join(ADDON_DATA, 'installed_version.txt'), 'w') as f: f.write(version)
        except:
            xbmc.log("WIZARD: Could not write trigger file to addon_data. Using fallback.", xbmc.LOGWARNING)

        dp.close()
        
        # Cleanup the temp zip to save space on FireSticks
        if os.path.exists(zip_path): os.remove(zip_path)
        
        xbmcgui.Dialog().ok("Success", "Build installed! Kodi will now close.\n\nOpen Kodi again to finish setup.")
        xbmc.executebuiltin("Quit")
        
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", f"Path Issue: {str(e)}\nTry going to Android Settings > Apps > Kodi > Permissions and enable 'Allow Management of All Files'.")

def check_for_updates():
    v_file = os.path.join(ADDON_DATA, 'installed_version.txt')
    if not os.path.exists(v_file):
        xbmcgui.Dialog().ok("Wizard", "Build version not found.")
        return

    with open(v_file) as f: 
        current = f.read().strip()
    
    manifest = get_json(MANIFEST_URL)
    if not manifest: return

    for build in manifest.get('builds', []):
        if build['version'] != current:
            if xbmcgui.Dialog().yesno("Update Available", f"New Version: {build['version']}\nInstall now?"):
                install_build(build['download_url'], build['name'], build['version'])
            return
    
    xbmcgui.Dialog().ok("Wizard", "Latest version already installed.")

def main_menu():
    options = ["Install Build", "Check for Updates", "Fresh Start"]
    choice = xbmcgui.Dialog().select("CordCutter Wizard", options)
    
    if choice == 0:
        manifest = get_json(MANIFEST_URL)
        if manifest:
            builds = manifest.get('builds', [])
            names = [f"{b['name']} (v{b['version']})" for b in builds]
            sel = xbmcgui.Dialog().select("Select Build", names)
            if sel != -1: 
                install_build(builds[sel]['download_url'], builds[sel]['name'], builds[sel]['version'])
    elif choice == 1:
        check_for_updates()
    elif choice == 2:
        smart_fresh_start()

if __name__ == '__main__': 
    main_menu()