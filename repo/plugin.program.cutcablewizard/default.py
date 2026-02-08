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
        # Create unverified context for Android/Embedded compatibility
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
    """Wipes addons and userdata, preserving the wizard itself"""
    if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup before installing?\n\nThis is highly recommended to avoid errors."):
        return True

    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Performing Fresh Start...")
    
    # Paths
    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, "addons")
    userdata_path = os.path.join(home, "userdata")
    
    # 1. Clean Addons (Preserve this wizard and packages folder)
    if os.path.exists(addons_path):
        for item in os.listdir(addons_path):
            # Skip the wizard itself and the packages folder (caches)
            if item == "packages" or item == ADDON_ID:
                continue
            
            item_path = os.path.join(addons_path, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception as e:
                xbmc.log(f"[{ADDON_NAME}] Failed to delete {item}: {e}", xbmc.LOGWARNING)

    # 2. Clean Userdata
    if os.path.exists(userdata_path):
        for item in os.listdir(userdata_path):
            # Skip database to avoid immediate crash, though usually standard wizards wipe everything
            if item == "Database": 
                continue 
            
            item_path = os.path.join(userdata_path, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception as e:
                xbmc.log(f"[{ADDON_NAME}] Failed to delete {item}: {e}", xbmc.LOGWARNING)

    dp.close()
    return True


def download_build(name, url, size_mb):
    local_path = os.path.join(ADDON_DATA, "temp_build.zip")
    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)

    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, f"Downloading {name}...")

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        opener.addheaders = [("User-Agent", USER_AGENT)]
        urllib.request.install_opener(opener)

        with urllib.request.urlopen(url) as response, open(local_path, "wb") as out_file:
            block_size = 1024 * 1024
            downloaded = 0
            # Use provided size_mb for progress bar if Content-Length is missing
            total = int(response.headers.get("Content-Length", "0") or (size_mb * 1024 * 1024))

            while True:
                data = response.read(block_size)
                if not data:
                    break
                out_file.write(data)
                downloaded += len(data)
                
                if total > 0:
                    percent = int(downloaded * 100 / total)
                    # Cap at 100% just in case
                    percent = min(percent, 100)
                    dialog.update(percent, f"Downloading {name}...", f"{int(downloaded/1024/1024)} MB / {int(total/1024/1024)} MB")
                
                if dialog.iscanceled():
                    dialog.close()
                    return None

        dialog.close()
        return local_path

    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().ok("Error", f"Download failed: {str(e)}")
        return None


def install_build(zip_path):
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, "Extracting Build...")
    
    # CRITICAL: Extract to special://home/ to cover both addons and userdata
    extract_path = xbmcvfs.translatePath("special://home/")
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_list = zf.infolist()
            total_files = len(file_list)
            
            for idx, member in enumerate(file_list):
                if idx % 50 == 0: # Update UI less frequently to speed up install
                    percent = int((idx / total_files) * 100)
                    dialog.update(percent, "Installing...", member.filename)
                
                # Security: Zip Slip protection
                if member.filename.startswith("..") or ".." in member.filename:
                    continue
                    
                # Standard extraction
                zf.extract(member, extract_path)

        dialog.update(100, "Installation Complete", "Preparing to close...")
        xbmc.sleep(1000)
        dialog.close()
        
        # Cleanup Zip
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        return True
        
    except Exception as e:
        dialog.close()
        xbmcgui.Dialog().ok("Error", f"Extraction failed: {str(e)}")
        return False


def build_menu():
    # Fetch builds from JSON
    manifest = get_json(MANIFEST_URL)
    
    if not manifest or "builds" not in manifest:
        # Error notification is handled in get_json
        return

    builds = manifest["builds"]
    names = []
    
    # Format the list for the GUI
    for b in builds:
        b_name = b.get("name", "Unknown")
        b_ver = b.get("version", "1.0")
        b_desc = b.get("description", "")
        names.append(f"{b_name} (v{b_ver})\n[COLOR gray]{b_desc}[/COLOR]")

    dialog = xbmcgui.Dialog()
    choice = dialog.select(f"{ADDON_NAME} - Select Build", names)

    if choice == -1:
        return

    selected = builds[choice]

    # Admin Protection
    if selected.get("admin_only", False):
        dialog_pass = xbmcgui.Dialog()
        password = dialog_pass.input("Admin Password:", type=xbmcgui.ALPHANUM_HIDE_INPUT)
        if password != ADMIN_PASSWORD:
            xbmcgui.Dialog().notification(ADDON_NAME, "Access Denied", xbmcgui.NOTIFICATION_ERROR)
            return

    # Confirmation
    if not xbmcgui.Dialog().yesno("Confirm Install", f"Install {selected['name']}?\n\nThis will download {selected.get('size_mb', 0)} MB."):
        return

    # 1. Fresh Start
    fresh_start()

    # 2. Download
    size = selected.get("size_mb", 0)
    zip_file = download_build(selected['name'], selected['download_url'], size)
    if not zip_file:
        return

    # 3. Install
    if install_build(zip_file):
        # 4. Force Close
        xbmcgui.Dialog().ok("Success", "Build installed successfully.\n\nClick OK to force close Kodi and apply changes.")
        os._exit(1)


def main_menu():
    options = ["Build Menu", "Maintenance Tools"]
    choice = xbmcgui.Dialog().select(ADDON_NAME, options)
    
    if choice == 0:
        build_menu()
    elif choice == 1:
        # Launch maintenance tool if available
        if xbmc.getCondVisibility('System.HasAddon(peno64.ezmaintenance)'):
             xbmc.executebuiltin('RunAddon("peno64.ezmaintenance")')
        else:
             xbmcgui.Dialog().ok("Missing Addon", "EZ Maintenance+ is not installed.")


if __name__ == "__main__":
    main_menu()
