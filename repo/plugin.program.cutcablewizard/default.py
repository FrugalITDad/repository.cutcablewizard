import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
USER_CONFIG_FILE = os.path.join(ADDON_DATA, 'user_settings.json')
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

def load_user_config():
    if xbmcvfs.exists(USER_CONFIG_FILE):
        with open(USER_CONFIG_FILE, 'r') as f: return json.load(f)
    return {}

def save_user_config(data):
    if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
    with open(USER_CONFIG_FILE, 'w') as f: json.dump(data, f)

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

    # 3. Device Name (Set + Reload GUI)
    if 'device_name' not in config:
        config['device_name'] = dialog.input("Device Name", "Enter name for this device:", type=xbmcgui.INPUT_ALPHANUM)
    if config.get('device_name'):
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{config["device_name"]}"}},"id":1}}')
        xbmc.executebuiltin('ReloadSkin()') # Forces the Service Menu to update visually

    # 4. Weather (Gismeteo XML Direct Write)
    if 'weather_town' not in config:
        config['weather_town'] = dialog.input("Weather", "Enter town for Weather:", type=xbmcgui.INPUT_ALPHANUM)
    if config.get('weather_town'):
        gis_path = xbmcvfs.translatePath("special://userdata/addon_data/weather.gismeteo/settings.xml")
        gis_dir = os.path.dirname(gis_path)
        if not xbmcvfs.exists(gis_dir): xbmcvfs.mkdirs(gis_dir)
        
        # We manually build the XML to ensure Gismeteo sees the change
        xml_content = f'<settings version="2">\n    <setting id="Location1" default="true">{config["weather_town"]}</setting>\n    <setting id="Location1id" default="true">{config["weather_town"]}</setting>\n</settings>'
        with open(gis_path, "w") as f: f.write(xml_content)
        
        # Activate Gismeteo in Kodi
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')

    save_user_config(config)

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
        xbmcvfs.delete(zip_path)
        ADDON.setSetting(f"ver_{build_id}", version)
        apply_custom_tweaks()
        xbmcgui.Dialog().ok("Success", "Build Applied! Restarting Kodi.")
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
        if ADDON.getSetting(f"ver_{sel['id']}") != sel['version']:
            if xbmcgui.Dialog().yesno("Update Available", f"New version v{sel['version']} found. Install?"):
                if backup_current_setup():
                    path = os.path.join(ADDON_DATA, "temp.zip")
                    urllib.request.urlretrieve(sel['download_url'], path)
                    install_build(path, sel['id'], sel['version'])

if __name__ == "__main__":
    main()
