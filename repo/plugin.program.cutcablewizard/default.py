import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil, sqlite3

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
# This physical file is the "Flag" that survives the restart
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt') 
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
USER_AGENT = "Kodi-CutCableWizard/1.4.6"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

# --- FORCE ENABLE ADDONS (The DB Hack) ---
def force_enable_addons():
    # This locates Kodi's internal database for addons (usually Addons33.db for Omega)
    db_path = xbmcvfs.translatePath("special://home/userdata/Database")
    if not os.path.exists(db_path): return
    
    # Find the latest Addons database file
    db_files = [f for f in os.listdir(db_path) if f.startswith("Addons") and f.endswith(".db")]
    if not db_files: return
    
    # Sort to get the highest version number
    latest_db = sorted(db_files)[-1]
    full_db_path = os.path.join(db_path, latest_db)
    
    xbmc.log(f"--- [Wizard] Attempting to force enable addons in: {latest_db}", xbmc.LOGINFO)
    
    try:
        # Connect to the DB and force 'enabled' to 1 for everything installed
        conn = sqlite3.connect(full_db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE installed SET enabled = 1")
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f"--- [Wizard] DB Update Failed: {str(e)}", xbmc.LOGERROR)

def backup_current_setup():
    backup_path = os.path.join(ADDON_DATA, 'backup_userdata_stable')
    home_path = xbmcvfs.translatePath("special://home/")
    userdata_src = os.path.join(home_path, 'userdata')
    
    try:
        usage = shutil.disk_usage(home_path)
        if usage.free < (200 * 1024 * 1024):
            xbmcgui.Dialog().ok(ADDON_NAME, "Backup Aborted: Less than 200MB free.")
            return False
    except: pass

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Safety Backup...")
    if xbmcvfs.exists(backup_path): xbmcvfs.rmdir(backup_path, force=True)
    xbmcvfs.mkdir(backup_path)
    
    dirs, files = xbmcvfs.listdir(userdata_src)
    total = len(dirs) + len(files)
    for count, item in enumerate(dirs + files):
        dp.update(int(count * 100 / total), f"Protecting: {item}")
        if any(skip in item for skip in ['Thumbnails', 'Database', 'Cache']): continue
        src_item = os.path.join(userdata_src, item)
        dst_item = os.path.join(backup_path, item)
        try:
            if xbmcvfs.exists(src_item + '/'): xbmcvfs.copytree(src_item, dst_item)
            else: xbmcvfs.copy(src_item, dst_item)
        except: continue
    dp.close()
    return True

def install_build(zip_path, build_id, version):
    dest = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting Build...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, f in enumerate(files):
                if i % 100 == 0: dp.update(int(i*100/len(files)), f"Installing: {f.filename[:30]}")
                zf.extract(f, dest)
        dp.close()
        xbmcvfs.delete(zip_path)
        
        # --- CRITICAL STEPS ---
        # 1. Create the PHYSICAL trigger file (This survives the reboot)
        if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f:
            f.write("trigger_active")
            
        # 2. Force Enable Addons in DB
        force_enable_addons()
        
        # 3. Store version info
        ADDON.setSetting(f"ver_{build_id}", version)

        xbmcgui.Dialog().ok("Success", "Build Applied! Kodi will now close.\n\nPLEASE RESTART KODI IMMEDIATELY.")
        xbmc.sleep(1000)
        os._exit(1)
    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", f"Failed: {str(e)}")

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    builds = manifest["builds"]
    options = [f"{b['name']} (v{b['version']})" for b in builds]
    choice = xbmcgui.Dialog().select("Select Build", options)
    
    if choice != -1:
        sel = builds[choice]
        if ADDON.getSetting(f"ver_{sel['id']}") != sel['version']:
            if xbmcgui.Dialog().yesno("Update", f"Install {sel['name']} v{sel['version']}?"):
                if backup_current_setup():
                    path = os.path.join(ADDON_DATA, "temp.zip")
                    dp = xbmcgui.DialogProgress()
                    dp.create(ADDON_NAME, "Downloading...")
                    urllib.request.urlretrieve(sel['download_url'], path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs)))
                    dp.close()
                    install_build(path, sel['id'], sel['version'])

if __name__ == "__main__":
    main()
