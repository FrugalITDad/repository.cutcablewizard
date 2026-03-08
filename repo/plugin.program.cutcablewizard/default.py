import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, shutil, urllib.request, json, ssl, zipfile

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

# Whitelist to prevent deleting the wizard and repos during Fresh Start
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
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup?\nWizard and repositories will be saved."): return False
    
    home = xbmcvfs.translatePath("special://home/")
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            if item in WHITELIST or item.startswith('repository.'): continue
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
    
    xbmc.executebuiltin('SaveSceneSettings')
    if not silent:
        xbmcgui.Dialog().ok("Fresh Start", "Cleanup Complete. Kodi will now close.")
        xbmc.executebuiltin("Quit")
    return True

def install_build(url, name, version):
    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
    
    # 1. Wipe old data first
    smart_fresh_start(silent=True)
    
    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", f"Downloading {name}...")

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(url, context=context) as r, open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(262144) # Fast buffer
                if not chunk: break
                f.write(chunk)
                count += len(chunk)
                if total > 0: dp.update(int(count*100/total), "Downloading Build...")
        
        # 2. Extract
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, file in enumerate(files):
                if i % 200 == 0: dp.update(int(i*100/len(files)), "Extracting Content...")
                zf.extract(file, home)
        
        # 3. Create triggers for service.py
        with open(os.path.join(ADDON_DATA, 'firstrun.txt'), 'w') as f: f.write("pending")
        with open(os.path.join(ADDON_DATA, 'installed_version.txt'), 'w') as f: f.write(version)
        
        dp.close()
        xbmcgui.Dialog().ok("Success", "Build installed! Kodi will now close to finish setup.")
        xbmc.executebuiltin("Quit")
    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", f"Failed: {str(e)}")

def main_menu():
    manifest = get_json(MANIFEST_URL)
    options = ["Install Build", "Check for Updates", "Fresh Start"]
    choice = xbmcgui.Dialog().select("CordCutter Wizard", options)
    
    if choice == 0 and manifest:
        builds = manifest.get('builds', [])
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1: install_build(builds[sel]['download_url'], builds[sel]['name'], builds[sel]['version'])
    elif choice == 1:
        # Check for updates logic
        pass
    elif choice == 2:
        smart_fresh_start()

if __name__ == '__main__': main_menu()