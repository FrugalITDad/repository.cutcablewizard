import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')
UPDATE_FILE  = os.path.join(ADDON_DATA, 'update_pending.json')
VERSION_FILE = os.path.join(ADDON_DATA, 'local_version.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_online_version():
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(MANIFEST_URL, headers={'User-Agent': 'Kodi-Wizard/1.1'})
        with urllib.request.urlopen(req, context=ctx) as r:
            data = json.loads(r.read())
            return data['builds'][0]
    except: return None

def check_for_updates():
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.sleep(2000)
    xbmc.executebuiltin(f'InstallAddon({ADDON_ID})')
    if not os.path.exists(VERSION_FILE): return 
    online_build = get_online_version()
    if not online_build: return
    try:
        with open(VERSION_FILE, 'r') as f: current_ver = f.read().strip()
    except: return
    if online_build['version'] != current_ver:
        if xbmcgui.Dialog().yesno("Update Available", f"New Build v{online_build['version']} is available.\nUpdate now? (Settings will be saved)"):
            if not os.path.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
            with open(UPDATE_FILE, 'w') as f: json.dump(online_build, f)
            xbmc.executebuiltin(f'RunScript({ADDON_ID})')

def run_first_run_setup():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(10): return 
    check_for_updates()
    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    if dialog.yesno("Setup: Subtitles", "Would you like subtitles to be on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    device_name = dialog.input("HINT: Enter a unique name for this Fire Stick", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    if dialog.yesno("Setup: Weather", "Would you like to configure the weather location?"):
        dialog.ok("Weather Hint", "HINT: Please do NOT turn on 'Current Location'. Enter city manually.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')

    if dialog.yesno("Setup: Trakt", "Would you like to configure Trakt?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')

    try: os.remove(TRIGGER_FILE)
    except: pass
    dialog.notification("CordCutter", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    run_first_run_setup()
