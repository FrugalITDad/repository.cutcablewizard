import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

# --- NO xbmcaddon.Addon() CALLS AT THE TOP ---
ADDON_ID = 'plugin.program.cutcablewizard'

def get_addon_data():
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

    if not os.path.exists(trigger_file): 
        return

    monitor = xbmc.Monitor()
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
        dialog.ok("Weather Hint", "Search for your city manually. Do NOT use 'Current Location'.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    if dialog.yesno("Setup (4/4): Trakt", "Authorize Trakt?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- PHASE 2: LIVE TV SYNC ---
    dp = xbmcgui.DialogProgress()
    # Heading + Message in one string for Kodi 21 compatibility
    dp.create("CordCutter", "Starting Live TV Merge and Sync...")
    
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(3000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    total_wait = 130
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        
        # FIX: Only 2 arguments passed (percent, and one combined string)
        msg = f"Syncing Channels & EPG Guide...\nTime Remaining: {i}s"
        dp.update(percent, msg)

    dp.update(98, "Refreshing TV database... almost finished.")
    xbmc.executebuiltin('UpdatePVR')
    xbmc.sleep(5000)

    try: os.remove(trigger_file)
    except: pass
    
    dp.close()
    
    # FIX: Final confirmation (2 arguments max)
    if dialog.yesno("Success!", "Setup complete! Restart Kodi now to finalize everything?"):
        xbmc.executebuiltin('ShutDown')

if __name__ == '__main__':
    run_first_run_setup()