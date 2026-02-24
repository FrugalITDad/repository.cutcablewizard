import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

# --- CRITICAL FIX: NO API CALLS AT TOP LEVEL ---
ADDON_ID = 'plugin.program.cutcablewizard'

def get_addon_data():
    """Manually construct path to bypass database indexing errors"""
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
    # Wait for the system to settle before popping dialogs
    if monitor.waitForAbort(12): return 

    dialog = xbmcgui.Dialog()
    
    # --- PHASE 1: INTERACTIVE (Simplified Dialogs to prevent argument errors) ---
    if dialog.yesno("Setup (1/4): Subtitles", "Would you like to enable subtitles by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    device_name = dialog.input("Setup (2/4): Name this device", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    if dialog.yesno("Setup (3/4): Weather", "Would you like to configure your weather location?"):
        dialog.ok("Weather Hint", "Search for your city manually. Do NOT use 'Current Location'.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    if dialog.yesno("Setup (4/4): Trakt", "Would you like to authorize the Trakt application now?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- PHASE 2: LIVE TV SYNC (130s ALIGNMENT) ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Finalizing Build Configurations...")
    
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(3000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    # 130 Second Countdown (Aligned to your 3:42 total timing)
    total_wait = 130
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        dp.update(percent, "Syncing Channels & EPG Guide...", f"Time Remaining: {i}s")

    dp.update(98, "Refreshing TV Database...", "Almost there!")
    xbmc.executebuiltin('UpdatePVR')
    xbmc.sleep(5000)

    # Clean up the trigger file
    try: os.remove(trigger_file)
    except: pass
    
    dp.close()
    
    # --- FINAL REBOOT (Simplified to 2 arguments to fix line 84 error) ---
    msg = "Setup complete! Kodi must restart now to apply the new TV Guide and Weather settings."
    if dialog.yesno("Success!", msg):
        xbmc.executebuiltin('ShutDown')
        xbmc.sleep(2000)
        import os as python_os
        python_os._exit(1)

if __name__ == '__main__':
    run_first_run_setup()