import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION ---
ADDON       = xbmcaddon.Addon()
ADDON_ID    = ADDON.getAddonInfo('id')
ADDON_DATA  = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
# Files used to coordinate between Service and Wizard
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')
UPDATE_FILE  = os.path.join(ADDON_DATA, 'update_pending.json')
VERSION_FILE = os.path.join(ADDON_DATA, 'local_version.txt')
BACKUP_PATH  = os.path.join(ADDON_DATA, 'temp_backup')

MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
WHITELIST    = [ADDON_ID, 'repository.cutcablewizard', 'packages', 'temp']

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard/1.1'})
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except: return None

# --- SMART DATA RETENTION ---
def backup_user_data():
    """Saves Trakt, Debrid, Favorites, and Sources before a wipe"""
    if os.path.exists(BACKUP_PATH): shutil.rmtree(BACKUP_PATH)
    os.makedirs(BACKUP_PATH)
    
    home = xbmcvfs.translatePath("special://home/")
    
    # 1. Key XML Files
    for xml in ['favourites.xml', 'sources.xml']:
        src = os.path.join(home, 'userdata', xml)
        if os.path.exists(src): shutil.copy(src, BACKUP_PATH)

    # 2. Addon Data (Trakt, ResolveURL/Debrid, Elementum, Fen, etc.)
    # We backup the full directories to keep logins intact
    ud_addon_data = os.path.join(home, 'userdata', 'addon_data')
    targets = ['script.trakt', 'script.module.resolveurl', 'plugin.video.fen', 'plugin.video.seren', 'plugin.video.umbrella']
    
    if os.path.exists(ud_addon_data):
        for item in os.listdir(ud_addon_data):
            if item in targets or item.startswith('plugin.video'):
                src = os.path.join(ud_addon_data, item)
                dst = os.path.join(BACKUP_PATH, item)
                if os.path.isdir(src): shutil.copytree(src, dst)

    # 3. Save Device Name
    name = xbmc.getInfoLabel('System.FriendlyName')
    with open(os.path.join(BACKUP_PATH, 'device_name.txt'), 'w') as f: f.write(name)

def restore_user_data():
    """Restores the saved data after install"""
    if not os.path.exists(BACKUP_PATH): return
    home = xbmcvfs.translatePath("special://home/")
    ud_addon_data = os.path.join(home, 'userdata', 'addon_data')
    
    # 1. Restore XMLs
    for f in os.listdir(BACKUP_PATH):
        if f.endswith('.xml'):
            shutil.copy(os.path.join(BACKUP_PATH, f), os.path.join(home, 'userdata', f))
            
    # 2. Restore Addon Data folders
    for item in os.listdir(BACKUP_PATH):
        src = os.path.join(BACKUP_PATH, item)
        if os.path.isdir(src):
            dst = os.path.join(ud_addon_data, item)
            if os.path.exists(dst): shutil.rmtree(dst) # Overwrite build default with user data
            shutil.copytree(src, dst)
            
    # 3. Restore Device Name
    name_file = os.path.join(BACKUP_PATH, 'device_name.txt')
    if os.path.exists(name_file):
        with open(name_file, 'r') as f: name = f.read()
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % name)
    
    # Cleanup
    shutil.rmtree(BACKUP_PATH, ignore_errors=True)

# --- INSTALLATION LOGIC ---
def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe setup but keep Wizard?"): return False
    
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

def install_build(url, name, version, keep_data=False):
    if keep_data:
        xbmcgui.Dialog().notification("Wizard", "Backing up Settings...", xbmcgui.NOTIFICATION_INFO, 3000)
        backup_user_data()

    if not smart_fresh_start(silent=True): return

    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", f"Downloading {name}...")

    try:
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
                if total > 0: dp.update(int(count*100/total), f"Downloading {name}...")

        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, file in enumerate(files):
                if i % 50 == 0: dp.update(int(i*100/len(files)), "Extracting...")
                target = os.path.join(home, file.filename)
                if not os.path.normpath(target).startswith(os.path.normpath(home)): continue
                if file.is_dir(): os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as f_out: f_out.write(zf.read(file))

        if keep_data:
            dp.update(95, "Restoring Settings...")
            restore_user_data()

        # Save Version Info
        with open(VERSION_FILE, 'w') as f: f.write(str(version))
        
        # Trigger First Run
        with open(TRIGGER_FILE, "w") as f: f.write("setup_pending")
        
        # Clean Update trigger
        if os.path.exists(UPDATE_FILE): os.remove(UPDATE_FILE)

        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Updated!\nKodi will now close.")
        os._exit(1)

    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    # 1. CHECK FOR PENDING UPDATE FROM SERVICE.PY
    if os.path.exists(UPDATE_FILE):
        try:
            with open(UPDATE_FILE, 'r') as f: update_info = json.load(f)
            install_build(update_info['url'], update_info['name'], update_info['version'], keep_data=True)
            return
        except: pass

    # 2. STANDARD MENU
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    choice = xbmcgui.Dialog().select("CordCutter Wizard", ["Install Build", "Fresh Start"])
    if choice == 0:
        builds = manifest.get('builds', [])
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1: 
            # Regular install - No data retention unless we want it implicitly
            install_build(builds[sel]['download_url'], builds[sel]['name'], builds[sel]['version'], keep_data=False)
    elif choice == 1:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__': main()
