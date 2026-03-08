import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, shutil, urllib.request, json, ssl, zipfile

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HOME = xbmcvfs.translatePath("special://home/")
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
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
        return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup?"): return False
    for folder in ['addons', 'userdata']:
        path = os.path.join(HOME, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            if item in WHITELIST or item.startswith('repository.'): continue
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
    return True

def install_build(url, name, version):
    if not xbmcvfs.exists(TEMP_DIR): xbmcvfs.mkdirs(TEMP_DIR)
    zip_path = os.path.join(TEMP_DIR, "build.zip")
    smart_fresh_start(silent=True)
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", f"Downloading {name}...")

    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(url, context=context) as r, open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(262144)
                if not chunk: break
                f.write(chunk)
                count += len(chunk)
                if total > 0: dp.update(int(count*100/total), "Downloading...")
        
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, file in enumerate(files):
                if i % 300 == 0: dp.update(int(i*100/len(files)), "Installing Files...")
                zf.extract(file, HOME)

        with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f: f.write("pending")
        with open(os.path.join(HOME, 'installed_version.txt'), 'w') as f: f.write(version)
        
        dp.close()
        if os.path.exists(zip_path): os.remove(zip_path)

        # NEW MESSAGE AS REQUESTED
        xbmcgui.Dialog().ok("Install Complete", 
            "Build Applied! Kodi must now FORCE CLOSE to load the new skin.\n\n"
            "IMPORTANT: After you re-open Kodi, please wait about ONE MINUTE "
            "for the First Run Setup to automatically begin.")
        os._exit(1) 
        
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main_menu():
    manifest = get_json(MANIFEST_URL)
    options = ["Install Build", "Check for Updates", "Fresh Start"]
    choice = xbmcgui.Dialog().select("CordCutter Wizard", options)
    if choice == 0 and manifest:
        builds = manifest.get('builds', [])
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1: install_build(builds[sel]['download_url'], builds[sel]['name'], builds[sel]['version'])
    elif choice == 2:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__': main_menu()