import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil, sqlite3

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard' # Your specific folder name
REPO_ID = 'repository.cutcablewizard'       # Your specific repo folder
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt') 
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
USER_AGENT = "Kodi-CutCableWizard/1.4.7"

# --- HELPER FUNCTIONS ---

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

# --- SMART FRESH START ---

def smart_fresh_start():
    if not xbmcgui.Dialog().yesno("Smart Fresh Start", "This will wipe all builds but KEEP this Wizard and Repository.\n\nProceed?"):
        return

    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, 'addons')
    userdata_path = os.path.join(home, 'userdata')
    
    # WHITELIST: Folders Kodi MUST NOT delete
    keep_list = [
        REPO_ID, 
        ADDON_ID,
        'packages', 
        'temp'
    ]

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Performing Smart Wipe...")

    # 1. Purge Addons (Except Wizard/Repo)
    dirs, files = xbmcvfs.listdir(addons_path)
    total = len(dirs)
    for count, folder in enumerate(dirs):
        if folder not in keep_list:
            dp.update(int(count * 50 / total), f"Removing Addon: {folder}")
            xbmcvfs.rmdir(os.path.join(addons_path, folder), force=True)

    # 2. Purge Userdata (Except critical settings and Addon Data)
    u_dirs, u_files = xbmcvfs.listdir(userdata_path)
    for u_folder in u_dirs:
        if u_folder not in ['addon_data', 'Database']: 
            xbmcvfs.rmdir(os.path.join(userdata_path, u_folder), force=True)
    
    # 3. Clean addon_data (Keep the Wizard's data)
    ad_path = os.path.join(userdata_path, 'addon_data')
    ad_dirs, ad_files = xbmcvfs.listdir(ad_path)
    for ad_folder in ad_dirs:
        if ad_folder not in keep_list:
            xbmcvfs.rmdir(os.path.join(ad_path, ad_folder), force=True)

    # 4. RESET SECURITY SETTINGS VIA JSON-RPC
    # This ensures "Unknown Sources" stays ON after the wipe
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')
    
    dp.close()
    xbmcgui.Dialog().ok("Success", "Kodi is now Fresh! Wizard and Repo were preserved.\n\nPlease restart Kodi.")
    os._exit(1)

# --- BUILD INSTALLATION ---

def install_build(zip_path, build_id, version):
    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, 'addons')
    db_path = os.path.join(home, 'userdata', 'Database')
    
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting Build...")
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, f in enumerate(files):
                if i % 100 == 0: dp.update(int(i*100/len(files)), f"Installing: {f.filename[:30]}")
                zf.extract(f, home)
        
        # Binary Purge (Safety Net)
        dp.update(85, "Sanitizing platform binaries...")
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_path = os.path.join(addons_path, b)
            if xbmcvfs.exists(b_path): xbmcvfs.rmdir(b_path, force=True)

        # Database Purge (Forces re-indexing for Android)
        dp.update(90, "Updating internal index...")
        if xbmcvfs.exists(db_path):
            _, files = xbmcvfs.listdir(db_path)
            for file in files:
                if file.startswith("Addons") and file.endswith(".db"):
                    xbmcvfs.delete(os.path.join(db_path, file))

        # Repo Refresh
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.sleep(3000) 
        
        # Trigger Android-Native Installs
        for addon_id in binaries: xbmc.executebuiltin(f'InstallAddon({addon_id})')
        
        # Wait Loop for PVR
        max_wait, elapsed = 60, 0
        check_path = os.path.join(addons_path, 'pvr.iptvsimple', '')
        while not xbmcvfs.exists(check_path) and elapsed < max_wait:
            if dp.iscanceled(): break
            dp.update(95, f"Downloading Android Components... {max_wait - elapsed}s")
            xbmc.sleep(1000)
            elapsed += 1

        dp.close()
        xbmcvfs.delete(zip_path)
        
        if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        ADDON.setSetting(f"ver_{build_id}", version)

        xbmcgui.Dialog().ok("Complete", "Build Installed!\n\nRestart Kodi to finish setup.")
        os._exit(1)
        
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

# --- MAIN MENU ---

def main():
    options = ["Install Build", "Smart Fresh Start"]
    choice = xbmcgui.Dialog().select(f"{ADDON_NAME} - Main Menu", options)
    
    if choice == 0: # Install Build
        manifest = get_json(MANIFEST_URL)
        if not manifest: return
        builds = manifest["builds"]
        b_choice = xbmcgui.Dialog().select("Select Build", [f"{b['name']} (v{b['version']})" for b in builds])
        if b_choice != -1:
            sel = builds[b_choice]
            path = os.path.join(ADDON_DATA, "temp.zip")
            dp = xbmcgui.DialogProgress()
            dp.create(ADDON_NAME, "Downloading...")
            urllib.request.urlretrieve(sel['download_url'], path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs)))
            dp.close()
            install_build(path, sel['id'], sel['version'])
            
    elif choice == 1: # Smart Fresh Start
        smart_fresh_start()

if __name__ == "__main__":
    main()
