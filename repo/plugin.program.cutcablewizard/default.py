import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil, sqlite3

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard' 
REPO_ID = 'repository.cutcablewizard'       
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt') 
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
USER_AGENT = "Kodi-CutCableWizard/1.4.7"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

def smart_fresh_start():
    if not xbmcgui.Dialog().yesno("Smart Fresh Start", "This will wipe all builds but KEEP this Wizard and Repository.\n\nProceed?"):
        return

    home = xbmcvfs.translatePath("special://home/")
    addons_path = xbmcvfs.translatePath("special://home/addons/")
    userdata_path = xbmcvfs.translatePath("special://home/userdata/")
    
    keep_list = [REPO_ID, ADDON_ID, 'packages', 'temp']

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Performing Smart Wipe...")

    # 1. Purge Addons
    dirs, _ = xbmcvfs.listdir(addons_path)
    for count, folder in enumerate(dirs):
        if folder not in keep_list:
            dp.update(int(count * 40 / len(dirs)), f"Removing Addon: {folder}")
            # Use shutil for more aggressive deletion on Android
            full_p = os.path.join(addons_path, folder)
            shutil.rmtree(full_p, ignore_errors=True)

    # 2. Purge Userdata
    u_dirs, _ = xbmcvfs.listdir(userdata_path)
    for u_folder in u_dirs:
        if u_folder not in ['addon_data', 'Database']: 
            shutil.rmtree(os.path.join(userdata_path, u_folder), ignore_errors=True)
    
    # 3. Clean addon_data
    ad_path = os.path.join(userdata_path, 'addon_data')
    ad_dirs, _ = xbmcvfs.listdir(ad_path)
    for ad_folder in ad_dirs:
        if ad_folder not in keep_list:
            shutil.rmtree(os.path.join(ad_path, ad_folder), ignore_errors=True)

    # 4. RESET SECURITY
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')
    
    dp.close()
    xbmcgui.Dialog().ok("Success", "Wipe Complete. Restarting Kodi...")
    os._exit(1)

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
        
        # Binary Purge
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_path = os.path.join(addons_path, b)
            if os.path.exists(b_path): shutil.rmtree(b_path, ignore_errors=True)

        # Database Purge
        if os.path.exists(db_path):
            for file in os.listdir(db_path):
                if file.startswith("Addons") and file.endswith(".db"):
                    os.remove(os.path.join(db_path, file))

        # Force Skin to Aeon Nox Silvo
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"lookandfeel.skin","value":"skin.aeonnox.silvo"},"id":1}')

        # Repo Refresh
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.sleep(2000) 
        
        # Trigger Installs
        for addon_id in binaries: xbmc.executebuiltin(f'InstallAddon({addon_id})')
        
        # Wait Room
        max_wait, elapsed = 60, 0
        while not os.path.exists(os.path.join(addons_path, 'pvr.iptvsimple')) and elapsed < max_wait:
            if dp.iscanceled(): break
            dp.update(95, f"Syncing Files... {max_wait - elapsed}s")
            xbmc.sleep(1000)
            elapsed += 1

        dp.close()
        
        # Finalize Trigger
        if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        ADDON.setSetting(f"ver_{build_id}", version)

        xbmcgui.Dialog().ok("Complete", "Build Applied. Closing Kodi to save changes...")
        xbmc.sleep(3000) # Give Android time to finish write operations
        os._exit(1)
        
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    options = ["Install Build", "Smart Fresh Start"]
    choice = xbmcgui.Dialog().select(f"{ADDON_NAME}", options)
    if choice == 0:
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
    elif choice == 1:
        smart_fresh_start()

if __name__ == "__main__":
    main()
