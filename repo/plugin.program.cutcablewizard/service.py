import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

# --- CONFIG ---
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')
UPDATE_FILE  = os.path.join(ADDON_DATA, 'update_pending.json')
VERSION_FILE = os.path.join(ADDON_DATA, 'local_version.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def wait_for_settings_close():
    """Wait loop for non-blocking settings windows (Weather/Trakt)"""
    monitor = xbmc.Monitor()
    xbmc.sleep(1000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1): break
    xbmc.sleep(500)

def wait_for_pvr():
    """Background wait for TV Manager with custom message"""
    monitor = xbmc.Monitor()
    xbmc.sleep(2000)
    
    # Custom Background Message (Professional Progress BG)
    pbg = xbmcgui.DialogProgressBG()
    pbg.create("CordCutter", "Preparing TV Guide & Channels. Please wait...")
    
    # Wait until PVR stops updating or the PVR progress dialog closes
    while xbmc.getCondVisibility('PVR.IsUpdating') or xbmc.getCondVisibility('Window.IsActive(progressdialog)'):
        if monitor.waitForAbort(2): break
    
    pbg.close()
    xbmc.sleep(1000)

def check_for_updates():
    """Automatic Build Update detection"""
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
            if xbmcgui.Dialog().yesno("Update", f"New Build v{online_build['version']} is available. Update now?"):
                with open(UPDATE_FILE, 'w') as f: json.dump(online_build, f)
                xbmc.executebuiltin(f'RunScript({ADDON_ID})')
    except: pass

def run_first_run_setup():
    monitor = xbmc.Monitor()
    # 1. Wait for skin to initialize
    if monitor.waitForAbort(15): return 

    check_for_updates()
    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    
    # --- STEP 1: FRONT-LOAD IPTV TASKS ---
    # Trigger these immediately so they run while the user is busy or waiting
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(2000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    # --- STEP 2: THE CUSTOM WAIT MESSAGE ---
    # We pause here until the CPU spike from TV indexing subsides
    wait_for_pvr()

    # --- STEP 3: INTERACTIVE USER SETUP ---
    # 3a. Subtitles
    if dialog.yesno("Setup: Subtitles", "Would you like subtitles to be on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    # 3b. Device Name (Grabs current name as default)
    device_name = dialog.input("HINT: Enter a unique name for this device", xbmc.getInfoLabel('System.FriendlyName'), type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # 3c. Weather
    if dialog.yesno("Setup: Weather", "Would you like to configure the weather location?"):
        dialog.ok("Weather Hint", "HINT: Please do NOT turn on 'Current Location'.\nEnter city manually in the next screen.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    # 3d. Trakt
    if dialog.yesno("Setup: Trakt", "Would you like to configure Trakt?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- STEP 4: FINALIZE ---
    xbmc.executebuiltin('UpdatePVR')
    
    # Cleanup trigger
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    dialog.notification("CordCutter", "Setup Complete! Build is ready.", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    run_first_run_setup()