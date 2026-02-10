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
            # Assuming first build in list is the "main" one
            return data['builds'][0]
    except: return None

def check_for_updates():
    # 1. Wizard Self-Update
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.sleep(2000)
    xbmc.executebuiltin(f'InstallAddon({ADDON_ID})')

    # 2. Build Update Check
    if not os.path.exists(VERSION_FILE): return # No build installed yet
    
    online_build = get_online_version()
    if not online_build: return

    try:
        with open(VERSION_FILE, 'r') as f: current_ver = f.read().strip()
    except: return

    # Compare Strings (Simple check: is online != current)
    # You can use more complex logic if you use semantic versioning
    if online_build['version'] != current_ver:
        if xbmcgui.Dialog().yesno("Update Available", f"New Build v{online_build['version']} is available.\nUpdate now? (Settings will be saved)"):
            
            # Write Update Info so default.py knows what to do
            if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
            with open(UPDATE_FILE, 'w') as f:
                json.dump(online_build, f)
            
            # Launch the Wizard
            xbmc.executebuiltin(f'RunScript({ADDON_ID})')

def run_first_run_setup():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(10): return 

    # Run Update Check first
    check_for_updates()

    # If trigger exists, run setup
    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    
    # QUESTION 1: SUBTITLES
    if dialog.yesno("Setup: Subtitles", "Would you like subtitles to be on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    # QUESTION 2: DEVICE NAME
    device_name = dialog.input("HINT: Enter a unique name for this Fire Stick", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # QUESTION 3: WEATHER
    if dialog.yesno("Setup: Weather", "Would you like to configure the weather location?"):
        dialog.ok("Weather Hint", "HINT: Please do NOT turn on 'Current Location' in the next menu. Enter your city manually.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')

    # QUESTION 4: TRAKT
    if dialog.yesno("Setup: Trakt", "Would you like to configure the Trakt application?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')

    try: os.remove(TRIGGER_FILE)
    except: pass
    dialog.notification("CordCutter", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    run_first_run_setup()
