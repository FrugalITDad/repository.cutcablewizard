import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
USER_AGENT = "Kodi-CutCableWizard/1.4.2"
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

# --- ROBUST BACKUP ENGINE ---
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

# --- INSTALLATION ENGINE ---
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
        
        # Cleanup
        xbmcvfs.delete(zip_path)
        
        # --- THE MAGIC STEPS ---
        # 1. Store version
        ADDON.setSetting(f"ver_{build_id}", version)
        # 2. Set the 'Setup Flag' - This tells service.py to run on next boot
        ADDON.setSetting("run_setup", "true")
        
        xbmcgui.Dialog().ok("Success", "Build Applied! Kodi will now close. Restart Kodi to finish setup and personalization.")
        
        # Force close to ensure files aren't overwritten by Kodi on exit
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
        # Check if an update is actually needed
        if ADDON.getSetting(f"ver_{sel['id']}") != sel['version']:
            if xbmcgui.Dialog().yesno("Build Update", f"A new version (v{sel['version']}) is available. Update now?"):
                if backup_current_setup():
                    path = os.path.join(ADDON_DATA, "temp.zip")
                    # Download
                    dp = xbmcgui.DialogProgress()
                    dp.create(ADDON_NAME, "Downloading...")
                    urllib.request.urlretrieve(sel['download_url'], path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs)))
                    dp.close()
                    # Install
                    install_build(path, sel['id'], sel['version'])
        else:
            if xbmcgui.Dialog().yesno("No Update", "You are on the latest version. Reinstall anyway?"):
                if backup_current_setup():
                    path = os.path.join(ADDON_DATA, "temp.zip")
                    urllib.request.urlretrieve(sel['download_url'], path)
                    install_build(path, sel['id'], sel['version'])

if __name__ == "__main__":
    main()
