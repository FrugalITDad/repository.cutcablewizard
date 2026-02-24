import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

# --- CONFIGURATION (NO API CALLS AT TOP LEVEL) ---
ADDON_ID = 'plugin.program.cutcablewizard'

def get_addon_data():
    """Manually construct path to avoid 'Unknown Addon ID' crashes"""
    # This points to the same place as ADDON.getAddonInfo('profile')
    return xbmcvfs.translatePath('special://profile/addon_data/' + ADDON_ID)

def wait_for_settings_close():
    monitor = xbmc.Monitor()
    xbmc.sleep(2000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1): break
    xbmc.sleep(1500)

def run_first_run_setup():
    addon_data = get_addon_data()
    trigger_file = os.path.join(addon_data, 'firstrun.txt')

    # If the trigger file doesn't exist, exit immediately without doing anything
    if not os.path.exists(trigger_file): 
        return

    monitor = xbmc.Monitor()
    # Wait for skin/hardware to settle (approx 12s)
    if monitor.waitForAbort(12): return 

    dialog = xbmcgui.Dialog()
    
    # --- PHASE 1: INTERACTIVE ---
    if dialog.yesno("Setup (1/4): Subtitles", "Enable subtitles by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    device_name = dialog.input("Setup (2/4): Name this device", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    if dialog.yesno("Setup (3/4): Weather", "Configure weather location?"):
        dialog.ok("Weather Hint", "Search for your city manually.\nDo NOT use 'Current Location'.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    if dialog.yesno("Setup (4/4): Trakt", "Authorize Trakt?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- PHASE 2: LIVE TV SYNC (80s ALIGNMENT) ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Starting Live TV Merge...")
    
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(3000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    # 80 Second Countdown
    total_wait = 80
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        dp.update(percent, f"Syncing Channels & EPG... {i}s remaining", "Please wait for this background process to finish.")

    dp.update(98, "Refreshing TV Guide database...", "Almost finished...")
    xbmc.executebuiltin('UpdatePVR')
    xbmc.sleep(5000)

    # Cleanup trigger
    try: os.remove(trigger_file)
    except: pass
    
    dp.close()
    
    # --- FINAL REBOOT ---
    msg = "All configurations applied!\nTo see your new Guide and Weather, Kodi must restart."
    if dialog.yesno("Success!", msg, "Restart Now?", "Later"):
        xbmc.executebuiltin('ShutDown')
        xbmc.sleep(2000)
        os._exit(1)

if __name__ == '__main__':
    run_first_run_setup()