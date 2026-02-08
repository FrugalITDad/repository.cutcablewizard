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

# URL to your build-info.json on GitHub
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/build-info.json"

def get_json(url):
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read())
    except Exception as e:
        xbmc.log(f"[{ADDON_NAME}] JSON Error: {e}", xbmc.LOGERROR)
        return None

def fresh_start():
    if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup before installing?\nHighly recommended for a clean build."):
        return True

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Cleaning Kodi...")
    home = xbmcvfs.translatePath("special://home/")
    
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if os.path.exists(path):
            for item in os.listdir(path):
                # Don't delete this wizard or the packages folder
                if item in [ADDON_ID, 'packages', 'temp_build.zip']: continue
                item_path = os.path.join(path, item)
                try:
                    if os.path.isdir(item_path): shutil.rmtree(item_path)
                    else: os.remove(item_path)
                except: pass
    dp.close()
    return True

def download_build(name, url, size):
    local_path = os.path.join(ADDON_DATA, "temp_build.zip")
    if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, f"Downloading {name}...")

    try:
        ctx = ssl._create_unverified_context()
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)

        with urllib.request.urlopen(url) as response, open(local_path, "wb") as out_file:
            downloaded = 0
            total = int(response.headers.get("Content-Length", "0") or (size * 1024 * 1024))

            while True:
                chunk = response.read(1024 * 1024)
                if not chunk: break
                out_file.write(chunk)
                downloaded += len(chunk)
                percent = min(int(downloaded * 100 / total), 100)
                dp.update(percent, f"Downloading {name}", f"{int(downloaded/1024/1024)}MB / {int(total/1024/1024)}MB")
                if dp.iscanceled(): return None
        return local_path
    except Exception as e:
        xbmcgui.Dialog().ok("Error", f"Download failed: {e}")
        return None
    finally: dp.close()

def install_build(zip_path):
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting files...")
    # Target is special://home/ so 'addons' and 'userdata' folders land in the right spot
    dest = xbmcvfs.translatePath("special://home/")

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            total = len(files)
            for i, f in enumerate(files):
                if i % 10 == 0:
                    dp.update(int(i*100/total), "Installing...", f.filename)
                if ".." in f.filename: continue # Safety
                zf.extract(f, dest)
        return True
    except Exception as e:
        xbmcgui.Dialog().ok("Error", f"Extraction failed: {e}")
        return False
    finally: dp.close()

def build_menu():
    data = get_json(MANIFEST_URL)
    if not data or "builds" not in data:
        return xbmcgui.Dialog().ok("Error", "Could not load build list.")

    builds = data["builds"]
    options = [f"{b['name']} (v{b['version']})\n[COLOR gray]{b['size_mb']}MB - {b['description']}[/COLOR]" for b in builds]
    
    choice = xbmcgui.Dialog().select("Select CordCutter Build", options)
    if choice == -1: return

    selected = builds[choice]
    
    # Password check if it's an admin build
    if selected.get("admin_only") and xbmcgui.Dialog().input("Password:", type=xbmcgui.ALPHANUM_HIDE_INPUT) != ADMIN_PASSWORD:
        return xbmcgui.Dialog().ok("Denied", "Incorrect Password")

    if not xbmcgui.Dialog().yesno("Confirm", f"Install {selected['name']}?"): return

    fresh_start()
    zip_file = download_build(selected['name'], selected['download_url'], selected['size_mb'])
    
    if zip_file and install_build(zip_file):
        xbmcgui.Dialog().ok("Success", "Install complete! Kodi will now close.")
        os._exit(1)

def main():
    choice = xbmcgui.Dialog().select(ADDON_NAME, ["Install Build", "Maintenance"])
    if choice == 0: build_menu()
    elif choice == 1:
        if xbmc.getCondVisibility('System.HasAddon(peno64.ezmaintenance)'):
            xbmc.executebuiltin('RunAddon("peno64.ezmaintenance")')
        else:
            xbmcgui.Dialog().ok("Notice", "EZ Maintenance+ not found.")

if __name__ == "__main__":
    main()
