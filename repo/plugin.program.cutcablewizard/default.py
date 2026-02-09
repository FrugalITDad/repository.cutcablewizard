import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION ---
ADDON       = xbmcaddon.Addon()
ADDON_ID    = ADDON.getAddonInfo('id')
ADDON_NAME  = ADDON.getAddonInfo('name')
ADDON_DATA  = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
# Trigger file is no longer strictly needed for remediation, but kept for legacy support
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

# Whitelist: Folders we DO NOT touch during a Fresh Start
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
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup but keep this Wizard?"): 
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
    # 1. Prepare for installation
    if not smart_fresh_start(silent=True): return

    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")

    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", "Downloading Build...\nPlease Wait")

    try:
        # 2. DOWNLOAD
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

        # 3. EXTRACTION
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

        # 4. SELECTIVE BINARY CLEANUP
        # We delete the binary folders to remove Windows .dll files.
        # We DO NOT delete Addons.db here. This keeps the Wizard enabled.
        dp.update(98, "Finalizing...\nCleaning incompatible binaries")
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_path = os.path.join(home, 'addons', b)
            if os.path.exists(b_path):
                shutil.rmtree(b_path, ignore_errors=True)

        # 5. TRIGGER & SHUTDOWN
        # Mark unknown sources as true
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')

        # Create the trigger file for service.py
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        
        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Installed!\n\nKodi will now close. On relaunch, the Wizard\nwill automatically fix IPTV and update itself.")
        os._exit(1)

    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", f"Installation Failed:\n{str(e)}")
        log(f"Install Error: {e}")

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    
    options = ["Install CordCutter Build", "Fresh Start Only"]
    choice = xbmcgui.Dialog().select("CutCableWizard", options)
    
    if choice == 0:
        builds = manifest.get('builds', [])
        names = [f"{b.get('name', 'Unknown')} (v{b.get('version', '?')})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1:
            install_build(builds[sel]['download_url'], builds[sel].get('name', 'Build'))
    elif choice == 1:
        if smart_fresh_start():
            xbmcgui.Dialog().ok("Success", "Fresh Start Complete.\nKodi will now restart.")
            os._exit(1)

if __name__ == '__main__':
    main()
