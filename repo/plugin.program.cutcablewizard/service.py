import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')
UPDATE_FILE  = os.path.join(ADDON_DATA, 'update_pending.json')
VERSION_FILE = os.path.join(ADDON_DATA, 'local_version.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def wait_for_settings_close():
    monitor = xbmc.Monitor()
    xbmc.sleep(1000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1): break
    xbmc.sleep(500)

def check_for_updates():
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.sleep(2000)
    xbmc.executebuiltin(f'InstallAddon({ADDON_ID})')
    if not os.path.exists(VERSION_FILE): return 
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        with urllib.request.urlopen(MANIFEST_URL, context=ctx) as r:
            online_build = json.loads(r.read())['builds'][0]
        with open(VERSION_FILE, 'r') as f: current_ver = f.read().strip()
        if online_build['version'] != current_ver:
            if xbmcgui.Dialog().yesno("Update", "New Build available. Update now?"):
                with open(UPDATE_FILE, 'w') as f: json.dump(online_build, f)
                xbmc.executebuiltin(f'RunScript({ADDON_ID})')
    except: pass

def run_first_run_setup():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(12): return 

    check_for_updates()
    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    
    # --- STEP 1: FRONT-LOAD IPTV TASKS (Background) ---
    dialog.notification("CordCutter", "Syncing TV in background...", xbmcgui.NOTIFICATION_INFO, 3000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(2000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    # --- STEP 2: INTERACTIVE SETUP ---
    # Subtitles
    if dialog.yesno("Setup: Subtitles", "Would you like subtitles to be on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    # Device Name
    device_name = dialog.input("HINT: Enter a unique name for this device", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # Weather
    if dialog.yesno("Setup: Weather", "Would you like to configure the weather location?"):
        dialog.ok("Weather Hint", "HINT: Please do NOT turn on 'Current Location'.\nEnter city manually in the next screen.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    # Trakt
    if dialog.yesno("Setup: Trakt", "Would you like to configure Trakt?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- STEP 3: FINALIZE ---
    xbmc.executebuiltin('UpdatePVR')
    try: os.remove(TRIGGER_FILE)
    except: pass
    dialog.notification("CordCutter", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    run_first_run_setup()