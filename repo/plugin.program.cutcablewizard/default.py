import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION (Strings only, no API calls yet) ---
ADDON_ID     = 'plugin.program.cutcablewizard'
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
WHITELIST    = [ADDON_ID, 'repository.cutcablewizard', 'packages', 'temp']

def get_addon_data():
    """Manually construct path to prevent 'Unknown Addon ID' crashes"""
    return xbmcvfs.translatePath('special://profile/addon_data/' + ADDON_ID)

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard/1.1'})
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except: return None

def backup_user_data(backup_path):
    if os.path.exists(backup_path): shutil.rmtree(backup_path)
    os.makedirs(backup_path, exist_ok=True)
    home = xbmcvfs.translatePath("special://home/")
    for xml in ['favourites.xml', 'sources.xml']:
        src = os.path.join(home, 'userdata', xml)
        if os.path.exists(src): shutil.copy(src, backup_path)
    ud_addon_data = os.path.join(home, 'userdata', 'addon_data')
    targets = ['script.trakt', 'script.module.resolveurl', 'plugin.video.fen', 'plugin.video.seren']
    if os.path.exists(ud_addon_data):
        for item in os.listdir(ud_addon_data):
            if item in targets:
                src = os.path.join(ud_addon_data, item)
                dst = os.path.join(backup_path, item)
                if os.path.isdir(src): shutil.copytree(src, dst)

def restore_user_data(backup_path):
    if not os.path.exists(backup_path): return
    home = xbmcvfs.translatePath("special://home/")
    ud_addon_data = os.path.join(home, 'userdata', 'addon_data')
    for f in os.listdir(backup_path):
        if f.endswith('.xml'):
            shutil.copy(os.path.join(backup_path, f), os.path.join(home, 'userdata', f))
    for item in os.listdir(backup_path):
        src = os.path.join(backup_path, item)
        if os.path.isdir(src):
            dst = os.path.join(ud_addon_data, item)
            if os.path.exists(dst): shutil.rmtree(dst)
            shutil.copytree(src, dst)
    shutil.rmtree(backup_path, ignore_errors=True)

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
    addon_data   = get_addon_data()
    version_file = os.path.join(addon_data, 'local_version.txt')
    trigger_file = os.path.join(addon_data, 'firstrun.txt')
    update_file  = os.path.join(addon_data, 'update_pending.json')
    backup_path  = os.path.join(addon_data, 'temp_backup')
    
    if not xbmcvfs.exists(addon_data): xbmcvfs.mkdirs(addon_data)
    if keep_data: backup_user_data(backup_path)
    if not smart_fresh_start(silent=True): return

    zip_path = os.path.join(addon_data, "temp.zip")
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

        if keep_data: restore_user_data(backup_path)
        with open(version_file, 'w') as f: f.write(str(version))
        with open(trigger_file, "w") as f: f.write("setup_pending")
        if os.path.exists(update_file): os.remove(update_file)

        dp.close()
        
        # --- FIX: Only 2 arguments to prevent TypeError ---
        success_msg = "Build Applied! Close Kodi normally, then relaunch to start the setup wizard."
        xbmcgui.Dialog().ok("Success", success_msg)
        os._exit(1)
        
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", f"Failed: {str(e)}")

def main():
    addon_data = get_addon_data()
    update_file = os.path.join(addon_data, 'update_pending.json')
    
    if os.path.exists(update_file):
        try:
            with open(update_file, 'r') as f: update_info = json.load(f)
            install_build(update_info['url'], update_info['name'], update_info['version'], keep_data=True)
            return
        except: pass

    manifest = get_json(MANIFEST_URL)
    if not manifest: 
        xbmcgui.Dialog().ok("Connection Error", "Check internet and try again.")
        return
        
    choice = xbmcgui.Dialog().select("CordCutter Wizard", ["Install Build", "Fresh Start"])
    if choice == 0:
        builds = manifest.get('builds', [])
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1: install_build(builds[sel]['download_url'], builds[sel]['name'], builds[sel]['version'])
    elif choice == 1:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__': main()