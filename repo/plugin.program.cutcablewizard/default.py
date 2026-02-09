import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION ---
ADDON       = xbmcaddon.Addon()
ADDON_ID    = ADDON.getAddonInfo('id')
ADDON_NAME  = ADDON.getAddonInfo('name')
ADDON_DATA  = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE= os.path.join(ADDON_DATA, 'firstrun.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

# Whitelist: What we DO NOT delete during a Fresh Start
WHITELIST = [ADDON_ID, 'repository.cutcablewizard', 'packages', 'temp']

def log(msg):
    xbmc.log(f"[{ADDON_NAME}] {msg}", xbmc.LOGINFO)

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard/1.1'})
        with urllib.request.urlopen(req, context=ctx) as r:
            data = r.read()
            if not data: return None
            return json.loads(data)
    except Exception as e:
        xbmcgui.Dialog().ok("Connection Error", f"Could not load builds.json\n{str(e)}")
        return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "This will wipe your current setup.\nYour Wizard and Repo will be saved. Proceed?"): 
            return False
    
    home = xbmcvfs.translatePath("special://home/")
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            if item in WHITELIST or item == 'Database' or item == 'addon_data': continue
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
    return True

def install_build(url, name):
    if not smart_fresh_start(silent=True): return

    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")

    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", "Downloading Build...\nPlease Wait")

    try:
        # 1. DOWNLOAD
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as r, open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(16384)
                if not chunk: break
                f.write(chunk)
                count += len(chunk)
                if total > 0:
                    percent = int(count * 100 / total)
                    dp.update(percent, f"Downloading {name}...\n{int(count/1024/1024)}MB / {int(total/1024/1024)}MB")
                else:
                    dp.update(0, f"Downloading...\n{int(count/1024/1024)}MB")

        # 2. EXTRACTION
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            total_files = len(files)
            for i, file in enumerate(files):
                if i % 50 == 0: 
                    dp.update(int(i*100/total_files), f"Extracting Files...\n{file.filename[:35]}")
                target = os.path.join(home, file.filename)
                if not os.path.normpath(target).startswith(os.path.normpath(home)): continue
                if file.is_dir():
                    if not os.path.exists(target): os.makedirs(target, exist_ok=True)
                else:
                    parent = os.path.dirname(target)
                    if not os.path.exists(parent): os.makedirs(parent, exist_ok=True)
                    with open(target, "wb") as f_out: f_out.write(zf.read(file))

        # 3. CLEANUP & DB NUKE
        dp.update(98, "Finalizing...\nCleaning Addon Database & Binaries")
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_path = os.path.join(home, 'addons', b)
            if os.path.exists(b_path): shutil.rmtree(b_path, ignore_errors=True)

        db_path = os.path.join(home, 'userdata', 'Database')
        if os.path.exists(db_path):
            for f in os.listdir(db_path):
                if f.startswith("Addons") and f.endswith(".db"):
                    try: os.remove(os.path.join(db_path, f))
                    except: pass

        # 4. PRE-REBOOT BOOTSTRAP
        # Enable Unknown Sources
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')
        # FORCE ENABLE WIZARD (Crucial so service.py runs on reboot)
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","params":{"addonid":"%s","enabled":true},"id":1}' % ADDON_ID)

        with open(TRIGGER_FILE, "w") as f: f.write("active")
        
        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Installed!\nKodi will now close.\nUpon relaunch, wait 30s for activation.")
        os._exit(1)

    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", f"Installation Failed:\n{str(e)}")

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    options = ["Install Build", "Fresh Start Only"]
    choice = xbmcgui.Dialog().select("CutCableWizard", options)
    if choice == 0:
        builds = manifest.get('builds', [])
        names = [f"{b.get('name', 'Unknown')} (v{b.get('version', '?')})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1:
            install_build(builds[sel]['download_url'], builds[sel].get('name', 'Build'))
    elif choice == 1:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__':
    main()
