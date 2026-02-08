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
USER_CONFIG_FILE = os.path.join(ADDON_DATA, 'user_settings.json')
USER_AGENT = "Kodi-CordCutterWizard/1.0"
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

# --- PERSISTENCE LOGIC ---
def load_user_config():
    if os.path.exists(USER_CONFIG_FILE):
        with open(USER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_config(data):
    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
    with open(USER_CONFIG_FILE, 'w') as f:
        json.dump(data, f)

# --- BACKUP LOGIC ---
def backup_current_setup():
    backup_path = os.path.join(ADDON_DATA, 'backup_last_stable')
    home_path = xbmcvfs.translatePath("special://home/")
    
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Creating Backup...")
    
    if os.path.exists(backup_path): shutil.rmtree(backup_path)
    os.makedirs(backup_path)
    
    folders = ['userdata', 'addons']
    for idx, folder in enumerate(folders):
        src = os.path.join(home_path, folder)
        dst = os.path.join(backup_path, folder)
        dp.update(int((idx+1)*100/len(folders)), f"Backing up: {folder}")
        if os.path.exists(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('Packages', 'Thumbnails', 'temp_build.zip'))
    dp.close()

# --- THE QUESTIONS & SETTINGS INJECTOR ---
def apply_custom_tweaks():
    config = load_user_config()
    dialog = xbmcgui.Dialog()

    # 1. Subtitles (Check if already answered)
    if 'subs' not in config:
        config['subs'] = dialog.yesno("Subtitles", "Turn subtitles on by default?")
    
    val = "true" if config['subs'] else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # 2. Trakt
    if dialog.yesno("Trakt", "Would you like to configure Trakt now?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')

    # 3. Device Name (Update Services screen)
    if 'device_name' not in config:
        config['device_name'] = dialog.input("Device Name", "Enter a name for this device:", type=xbmcgui.INPUT_ALPHANUM)
    
    if config['device_name']:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{config["device_name"]}"}},"id":1}}')

    # 4. Weather (Gismeteo)
    if 'weather_town' not in config:
        config['weather_town'] = dialog.input("Weather", "Enter nearest town for weather:", type=xbmcgui.INPUT_ALPHANUM)
    
    if config['weather_town']:
        # Set core Kodi location
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"weather.location1","value":"{config["weather_town"]}"}},"id":1}}')
        # Gismeteo usually requires a manual search in its GUI to lock the ID, 
        # but setting Location1 in Kodi core lets Gismeteo pick it up.

    save_user_config(config)

def download_build(name, url):
    local_path = os.path.join(ADDON_DATA, "temp_build.zip")
    if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, f"Downloading {name}...")
    try:
        urllib.request.urlretrieve(url, local_path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs), f"Downloading... {int(nb*bs/1024/1024)}MB"))
        dp.close()
        return local_path
    except:
        dp.close()
        return None

def install_build(zip_path):
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting Build...")
    dest = xbmcvfs.translatePath("special://home/")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, f in enumerate(files):
                if i % 50 == 0: dp.update(int(i*100/len(files)), f"Extracting: {f.filename[:30]}")
                zf.extract(f, dest)
        dp.close()
        os.remove(zip_path)
        apply_custom_tweaks()
        xbmcgui.Dialog().ok("Success", "Build Applied! Kodi will now close.")
        os._exit(1)
    except:
        dp.close()
        xbmcgui.Dialog().ok("Error", "Installation failed. Check log.")

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    
    builds = manifest["builds"]
    options = [f"{b['name']} (v{b['version']})" for b in builds]
    choice = xbmcgui.Dialog().select("Select Build", options)
    
    if choice != -1:
        selected = builds[choice]
        # Version Check
        local_v = ADDON.getSetting(f"ver_{selected['name']}")
        if local_v == selected['version']:
            if not xbmcgui.Dialog().yesno("No Update", "You already have this version. Reinstall?"): return

        if xbmcgui.Dialog().yesno("Install", f"Download {selected['name']}?"):
            backup_current_setup()
            zip_file = download_build(selected['name'], selected['download_url'])
            if zip_file:
                ADDON.setSetting(f"ver_{selected['name']}", selected['version'])
                install_build(zip_file)

if __name__ == "__main__":
    main()
