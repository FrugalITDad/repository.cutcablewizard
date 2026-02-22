import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION ---
ADDON       = xbmcaddon.Addon()
ADDON_ID    = ADDON.getAddonInfo('id')
ADDON_DATA  = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

# Communication Files
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

# --- SETTINGS RETENTION ---
def backup_user_data():
    if os.path.exists(BACKUP_PATH): shutil.rmtree(BACKUP_PATH)
    os.makedirs(BACKUP_PATH, exist_ok=True)
    home = xbmcvfs.translatePath("special://home/")
    
    # 1. XMLs
    for xml in ['favourites.xml', 'sources.xml']:
        src = os.path.join(home, 'userdata', xml)
        if os.path.exists(src): shutil.copy(src, BACKUP_PATH)
    
    # 2. Addon Logins/Settings
    ud_addon_data = os.path.join(home, 'userdata', 'addon_data')
    targets = ['script.trakt', 'script.module.resolveurl', 'plugin.video.fen', 'plugin.video.seren', 'plugin.video.umbrella']
    if os.path.exists(ud_addon_data):
        for item in os.listdir(ud_addon_data):
            if item in targets:
                src = os.path.join(ud_addon_data, item)
                dst = os.path.join(BACKUP_PATH, item)
                if os.path.isdir(src): shutil.copytree(src, dst)

def restore_user_data():
    if not os.path.exists(BACKUP_PATH): return
    home = xbmcvfs.translatePath("special://home/")
    ud_addon_data = os.path.join(home, 'userdata', 'addon_data')
    for f in os.listdir(BACKUP_PATH):
        if f.endswith('.xml'):
            shutil.copy(os.path.join(BACKUP_PATH, f), os.path.join(home, 'userdata', f))
    for item in os.listdir(BACKUP_PATH):
        src = os.path.join(BACKUP_PATH, item)
        if os.path.isdir(src):
            dst = os.path.join(ud_addon_data, item)
            if os.path.exists(dst): shutil.rmtree(dst)
            shutil.copytree(src, dst)
    shutil.rmtree(BACKUP_PATH, ignore_errors=True)

# --- ENGINE ---
def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup but keep this Wizard?"): return False
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
    if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
    if keep_data: backup_user_data()
    if not smart_fresh_start(silent=True): return

    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", f"Downloading {name}...")

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
                if i % 50 == 0: dp.update(int(i*100/len(files)), "Extracting Build Files...")
                target = os.path.join(home, file.filename)
                if not os.path.normpath(target).startswith(os.path.normpath(home)): continue
                if file.is_dir(): os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as f_out: f_out.write(zf.read(file))

        if keep_data: restore_user_data()
        with open(VERSION_FILE, 'w') as f: f.write(str(version))
        with open(TRIGGER_FILE, "w") as f: f.write("setup_pending")
        if os.path.exists(UPDATE_FILE): os.remove(UPDATE_FILE)

        dp.close()
        
        msg = "Success! Now please:\n1. Open Kodi & wait 10 seconds.\n2. Close Kodi completely.\n3. Open Kodi AGAIN to start the Wizard Setup."
        xbmcgui.Dialog().ok("CordCutter", msg)
        os._exit(1)
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", f"Installation Failed: {str(e)}")

def main():
    if os.path.exists(UPDATE_FILE):
        try:
            with open(UPDATE_FILE, 'r') as f: update_info = json.load(f)
            install_build(update_info['url'], update_info['name'], update_info['version'], keep_data=True)
            return
        except: pass

    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    choice = xbmcgui.Dialog().select("CordCutter Wizard", ["Install Build", "Fresh Start"])
    if choice == 0:
        builds = manifest.get('builds', [])
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1: install_build(builds[sel]['download_url'], builds[sel]['name'], builds[sel]['version'])
    elif choice == 1:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__': main()