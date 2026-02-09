import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIG ---
ADDON       = xbmcaddon.Addon()
ADDON_ID    = 'plugin.program.cutcablewizard'
ADDON_DATA  = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE= os.path.join(ADDON_DATA, 'trigger.txt')
# *** UPDATE THIS URL TO YOUR JSON FILE ***
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def log(msg):
    xbmc.log(f"[{ADDON_ID}] {msg}", xbmc.LOGINFO)

def check_permissions():
    """Verify write access to Home before starting."""
    home = xbmcvfs.translatePath("special://home/")
    test_file = os.path.join(home, 'perm_test.txt')
    try:
        with open(test_file, 'w') as f: f.write('test')
        os.remove(test_file)
        return True
    except Exception as e:
        log(f"Permission Check Failed: {e}")
        return False

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard/1.0'})
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except Exception as e:
        xbmcgui.Dialog().ok("Connection Error", f"Could not read builds: {e}")
        return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe setup but KEEP Wizard?"): return False
    
    # 1. DELETE PACKAGES (Crucial for space)
    packages = xbmcvfs.translatePath("special://home/addons/packages")
    if os.path.exists(packages):
        shutil.rmtree(packages, ignore_errors=True)
        os.makedirs(packages)

    # 2. WIPE ADDONS/USERDATA
    home = xbmcvfs.translatePath("special://home/")
    keep = [ADDON_ID, 'repository.cutcablewizard', 'packages', 'temp', 'backup']
    
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        
        for item in os.listdir(path):
            if item in keep or item == 'Database': continue # Skip Database to avoid locks
            
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
    return True

def install_build(url):
    if not check_permissions():
        xbmcgui.Dialog().ok("Permission Error", "Kodi cannot write to storage.", "Go to Android Settings > Apps > Kodi > Permissions", "Enable 'Allow All The Time' or 'Files and Media'")
        return

    if not smart_fresh_start(silent=True): return

    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)

    dp = xbmcgui.DialogProgress()
    dp.create("Wizard", "Downloading...", "Please Wait")

    # --- STEP 1: DOWNLOAD ---
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(url, context=ctx) as r, open(zip_path, 'wb') as f:
            total_size = int(r.info().get('Content-Length', 0))
            block_size = 8192
            count = 0
            while True:
                chunk = r.read(block_size)
                if not chunk: break
                f.write(chunk)
                count += len(chunk)
                percent = int(count * 100 / total_size) if total_size > 0 else 0
                dp.update(percent, f"Downloading: {int(count/1024/1024)} MB")
                if dp.iscanceled(): 
                    dp.close()
                    return

        # --- STEP 2: EXTRACT (SAFE MODE) ---
        dp.update(0, "Extracting...", "Initializing Safe Mode")
        home = xbmcvfs.translatePath("special://home/")
        
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_list = zf.infolist()
            total_files = len(file_list)
            
            for index, file_info in enumerate(file_list):
                if index % 50 == 0:
                    dp.update(int(index * 100 / total_files), "Extracting...", file_info.filename)
                    if dp.iscanceled(): break
                
                # Sanitize path to prevent 'Zip Slip' or absolute path errors
                target_path = os.path.join(home, file_info.filename)
                
                # Skip if trying to overwrite the Wizard itself
                if ADDON_ID in target_path: continue

                try:
                    if file_info.is_dir():
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        parent_dir = os.path.dirname(target_path)
                        if not os.path.exists(parent_dir):
                            os.makedirs(parent_dir, exist_ok=True)
                        
                        with open(target_path, "wb") as f_out:
                            f_out.write(zf.read(file_info))
                except Exception as e:
                    # Log but don't crash on single file errors (thumbs, etc.)
                    log(f"Failed to extract {file_info.filename}: {e}")

        # --- STEP 3: FINALIZE ---
        dp.update(100, "Finalizing", "Setting Skin...")
        
        # Write trigger for service.py to handle skin switch on boot
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        
        # Force a simple advancedsettings to ensure no caching issues on first boot
        adv_path = os.path.join(home, 'userdata', 'advancedsettings.xml')
        with open(adv_path, 'w') as f:
            f.write('<advancedsettings><cache><memorysize>139460608</memorysize></cache></advancedsettings>')

        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Installed Successfully!", "Click OK to Force Close Kodi.")
        os._exit(1)

    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", f"Install Failed: {e}")

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    
    builds = manifest.get('builds', [])
    names = [b['name'] for b in builds]
    
    choice = xbmcgui.Dialog().select("Select Build", names)
    if choice != -1:
        install_build(builds[choice]['download_url'])

if __name__ == '__main__':
    main()
