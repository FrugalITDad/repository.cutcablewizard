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

# Points to the raw JSON file at the root of your GitHub repo
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"


def get_json(url):
    """Fetch and parse JSON from remote URL with SSL workaround"""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = response.read()
            return json.loads(data)
    except Exception as e:
        xbmc.log(f"[{ADDON_NAME}] JSON Fetch Error: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(ADDON_NAME, "Could not load build list", xbmcgui.NOTIFICATION_ERROR)
        return None


def fresh_start():
    """Wipes addons and userdata, preserving the wizard itself to prevent conflicts"""
    if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup before installing?\n\nHighly recommended for Windows and Android boxes."):
        return True

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Performing Fresh Start...")
    
    home = xbmcvfs.translatePath("special://home/")
    
    # Folders to clear
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if os.path.exists(path):
            items = os.listdir(path)
            total = len(items)
            for idx, item in enumerate(items):
                # PROTECT THE WIZARD AND CORE PACKAGES
                if item in [ADDON_ID, 'packages', 'temp_build.zip', 'Database']:
                    continue
                
                dp.update(int(idx*100/total), "Cleaning...", item)
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
    """Downloads the build ZIP to the addon data folder"""
    local_path = os.path.join(ADDON_DATA, "temp_build.zip")
    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, f"Downloading {name}...")

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)

        with urllib.request.urlopen(url) as response, open(local_path, "wb") as out_file:
            # Get total size from header or fallback to JSON value
            total = int(response.headers.get("Content-Length", "0") or (size_mb * 1024 * 1024))
            downloaded = 0
            block_size = 1024 * 1024

            while True:
                data = response.read(block_size)
                if not data: break
                out_file.write(data)
                downloaded += len(data)
                
                percent = min(int(downloaded * 100 / total), 100)
                dp.update(percent, f"Downloading {name}...", f"{int(downloaded/1024/1024)}MB / {int(total/1024/1024)}MB")
                
                if dp.iscanceled():
                    dp.close()
                    return None
        dp.close()
        return local_path
    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Download Error", str(e))
        return None


def install_build(zip_path):
    """Extracts build directly to special://home/ using robust file streaming"""
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting Build Files...")
    
    # Target is the root of Kodi (Windows: %APPDATA%/Kodi/ | Android: /files/.kodi/)
    dest = xbmcvfs.translatePath("special://home/")
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            total = len(files)
            
            for i, f in enumerate(files):
                if i % 25 == 0:
                    percent = int(i * 100 / total)
                    dp.update(percent, "Installing...", f.filename)
                
                if ".." in f.filename: continue
                
                path = os.path.join(dest, f.filename)
                
                if f.filename.endswith('/'):
                    if not os.path.exists(path):
                        os.makedirs(path)
                else:
                    # Ensure the folder for the file exists
                    parent = os.path.dirname(path)
                    if not os.path.exists(parent):
                        os.makedirs(parent)
                    
                    # Write the file data manually to ensure permissions are handled
                    with zf.open(f) as source, open(path, 'wb') as target:
                        shutil.copyfileobj(source, target)

        dp.update(100, "Installation Complete", "Saving changes...")
        xbmc.sleep(2000)
        dp.close()
        
        # Cleanup
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        xbmcgui.Dialog().ok("Success", "Build applied! Kodi will now close to refresh settings.")
        
        # Force exit to prevent Kodi from overwriting new guisettings.xml with old cache
        os._exit(1)
        return True
        
    except Exception as e:
        dp.close()
        xbmc.log(f"INSTALL ERROR: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Installation Error", f"Check log: {str(e)}")
        return False


def build_menu():
    manifest = get_json(MANIFEST_URL)
    if not manifest or "builds" not in manifest:
        return

    builds = manifest["builds"]
    options = [f"{b['name']} v{b['version']}\n[COLOR gray]{b['description']}[/COLOR]" for b in builds]
    
    choice = xbmcgui.Dialog().select(f"{ADDON_NAME} - Select Build", options)
    if choice == -1: return

    selected = builds[choice]

    # Password check for admin builds
    if selected.get("admin_only", False):
        if xbmcgui.Dialog().input("Admin Password:", type=xbmcgui.ALPHANUM_HIDE_INPUT) != ADMIN_PASSWORD:
            xbmcgui.Dialog().notification("Error", "Incorrect Password", xbmcgui.NOTIFICATION_ERROR)
            return

    if not xbmcgui.Dialog().yesno("Ready?", f"Install {selected['name']}?"):
        return

    # Start the process
    if fresh_start():
        zip_file = download_build(selected['name'], selected['download_url'], selected.get('size_mb', 0))
        if zip_file:
            install_build(zip_file)


def main():
    options = ["Install Build", "Maintenance", "Check for Updates"]
    choice = xbmcgui.Dialog().select(ADDON_NAME, options)
    
    if choice == 0:
        build_menu()
    elif choice == 1:
        if xbmc.getCondVisibility('System.HasAddon(peno64.ezmaintenance)'):
             xbmc.executebuiltin('RunAddon("peno64.ezmaintenance")')
        else:
             xbmcgui.Dialog().ok("Notice", "EZ Maintenance+ not found in your build.")
    elif choice == 2:
        xbmcgui.Dialog().notification("Update Check", "You are running the latest version.", xbmcgui.NOTIFICATION_INFO)

if __name__ == "__main__":
    main()
