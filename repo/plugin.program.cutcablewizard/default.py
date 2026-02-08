import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmc
import urllib.request
import os
import json
import ssl
import zipfile
import shutil

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
USER_AGENT = "Kodi-CordCutterWizard/1.0"
ADMIN_PASSWORD = "2026"
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except Exception as e:
        return None

def fresh_start():
    if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe setup before installing?"):
        return True
    
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Initialising Clean...")
    
    home = xbmcvfs.translatePath("special://home/")
    
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if os.path.exists(path):
            items = os.listdir(path)
            total = len(items)
            for idx, item in enumerate(items):
                # PROTECT CORE FILES
                if item in [ADDON_ID, 'packages', 'temp_build.zip', 'Database']:
                    continue
                
                percent = int(idx * 100 / total) if total > 0 else 0
                # FIXED: Only 2 arguments given here
                dp.update(percent, f"Cleaning: {item}")
                
                item_path = os.path.join(path, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except:
                    pass
    dp.close()
    return True

def download_build(name, url, size_mb):
    local_path = os.path.join(ADDON_DATA, "temp_build.zip")
    if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
    
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Starting Download...")
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)
        
        with urllib.request.urlopen(url) as response, open(local_path, "wb") as out_file:
            total = int(response.headers.get("Content-Length", 0) or (size_mb * 1024 * 1024))
            dl = 0
            block = 1024 * 1024
            while True:
                chunk = response.read(block)
                if not chunk: break
                out_file.write(chunk)
                dl += len(chunk)
                percent = min(int(dl * 100 / total), 100)
                # FIXED: Only 2 arguments
                dp.update(percent, f"Downloading: {int(dl/1024/1024)}MB / {int(total/1024/1024)}MB")
                if dp.iscanceled(): return None
        dp.close()
        return local_path
    except Exception as e:
        dp.close()
        return None

def install_build(zip_path):
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting...")
    dest = xbmcvfs.translatePath("special://home/")
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            total = len(files)
            for i, f in enumerate(files):
                if i % 50 == 0:
                    percent = int(i * 100 / total)
                    # FIXED: Only 2 arguments
                    dp.update(percent, f"Installing: {f.filename[:40]}")
                
                if ".." in f.filename: continue
                path = os.path.join(dest, f.filename)
                
                if f.filename.endswith('/'):
                    if not os.path.exists(path): os.makedirs(path)
                else:
                    parent = os.path.dirname(path)
                    if not os.path.exists(parent): os.makedirs(parent)
                    with zf.open(f) as s, open(path, 'wb') as t:
                        shutil.copyfileobj(s, t)
        
        dp.close()
        if os.path.exists(zip_path): os.remove(zip_path)
        
        xbmcgui.Dialog().ok("Success", "Build Applied! Restart Kodi now.")
        os._exit(1)
    except Exception as e:
        dp.close()
        return False

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: 
        xbmcgui.Dialog().ok("Error", "Could not connect to GitHub")
        return
        
    builds = manifest["builds"]
    options = [f"{b['name']} v{b['version']}" for b in builds]
    choice = xbmcgui.Dialog().select("Select Build", options)
    
    if choice != -1:
        selected = builds[choice]
        if fresh_start():
            zip_file = download_build(selected['name'], selected['download_url'], selected.get('size_mb', 0))
            if zip_file:
                install_build(zip_file)

if __name__ == "__main__":
    main()
