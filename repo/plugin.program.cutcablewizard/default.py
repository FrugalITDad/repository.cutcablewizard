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
USER_AGENT = "Kodi-CutCableWizard/1.4.2"
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

# --- HELPER FUNCTIONS ---
def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

def load_user_config():
    if xbmcvfs.exists(USER_CONFIG_FILE):
        with open(USER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_config(data):
    if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
    with open(USER_CONFIG_FILE, 'w') as f:
        json.dump(data, f)

# --- THE PERSONALIZATION INJECTOR ---
def apply_custom_tweaks():
    config = load_user_config()
    dialog = xbmcgui.Dialog()

    # 1. Subtitles
    if 'subs' not in config:
        config['subs'] = dialog.yesno("Subtitles", "Turn subtitles on by default?")
    
    val = "true" if config['subs'] else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # 2. Trakt
    if dialog.yesno("Trakt", "Configure Trakt now?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')

    # 3. Device Name
    if 'device_name' not in config:
        config['device_name'] = dialog.input("Device Name", "Enter a name for this device (Services screen):", type=xbmcgui.INPUT_ALPHANUM)
    
    if config['device_name']:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{config["device_name"]}"}},"id":1}}')

    # 4. Weather (Gismeteo)
    if 'weather_town' not in config:
        config['weather_town'] = dialog.input("Weather", "Enter nearest town for Gismeteo:", type=xbmcgui.INPUT_ALPHANUM)
    
    if config['weather_town']:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"weather.location1","value":"{config["weather_town"]}"}},"id":1}}')

    save_user_config(config)

# --- ROBUST BACKUP ENGINE ---
def backup_current_setup():
    backup_path = os.path.join(ADDON_DATA, 'backup_userdata_stable')
    home_path = xbmcvfs.translatePath("special://home/")
    userdata_src = os.path.join(home_path, 'userdata')
    
    # Check Free Space (Target 200MB minimum for safety)
    try:
        usage = shutil.disk_usage(home_path)
        if usage.free < (200 * 1024 * 1024):
            xbmcgui.Dialog().ok(ADDON_NAME, "Backup Aborted: Less than 200MB free space.")
            return False
    except: pass # Fallback if shutil.disk_usage is restricted

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
def download_build(name, url):
    local_path = os.path.join(ADDON_DATA, "temp_build.zip")
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
        apply_custom_tweaks()
        xbmcgui.Dialog().ok("Success", "Build Applied! Restarting Kodi to save settings.")
        os._exit(1)
    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", f"Install failed: {str(e)}")

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest:
        xbmcgui.Dialog().ok(ADDON_NAME, "Error: Could not reach GitHub manifest.")
        return
    
    builds = manifest["builds"]
    options = [f"{b['name']} (v{b['version']})" for b in builds]
    choice = xbmcgui.Dialog().select("Select Build to Install", options)
    
    if choice != -1:
        selected = builds[choice]
        local_v = ADDON.getSetting(f"ver_{selected['id']}")
        
        if local_v == selected['version']:
            if not xbmcgui.Dialog().yesno("Up to Date", "Version matches. Reinstall?"): return

        if xbmcgui.Dialog().yesno("Install Build", f"Upgrade to {selected['name']} v{selected['version']}?"):
            if backup_current_setup():
                zip_file = download_build(selected['name'], selected['download_url'])
                if zip_file:
                    ADDON.setSetting(f"ver_{selected['id']}", selected['version'])
                    install_build(zip_file)

if __name__ == "__main__":
    main()
