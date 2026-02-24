import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

# --- HARDCODED ID TO PREVENT RUNTIME ERROR ---
ADDON_ID = 'plugin.program.cutcablewizard'
try:
    ADDON = xbmcaddon.Addon(ADDON_ID)
    ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
except:
    ADDON_DATA = xbmcvfs.translatePath('special://profile/addon_data/' + ADDON_ID)

TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def wait_for_settings_close():
    monitor = xbmc.Monitor()
    xbmc.sleep(2000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1): break
    xbmc.sleep(1500)

def run_first_run_setup():
    monitor = xbmc.Monitor()
    # Initial wait for hardware/skin to settle
    if monitor.waitForAbort(12): return 

    if not os.path.exists(TRIGGER_FILE): return

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
    # Aligned to your 1m 14s observation + small buffer
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Starting Live TV Merge...")
    
    # Fire the IPTV Merge background tasks
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(3000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    # 80 Second Countdown (covers the 74s merge time)
    total_wait = 80
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        dp.update(percent, f"Syncing Channels & EPG... {i}s remaining", "Please wait for this background process to finish.")

    dp.update(98, "Refreshing TV Guide database...", "Almost finished...")
    xbmc.executebuiltin('UpdatePVR')
    xbmc.sleep(5000)

    # Cleanup the trigger so it doesn't run again
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    dp.close()
    
    # --- FINAL REBOOT ---
    msg = "All configurations applied!\nTo see your new Guide and Weather, Kodi must restart."
    if dialog.yesno("Success!", msg, "Restart Now?", "Later"):
        # Powerdown/Shutdown is the most effective exit for Android
        xbmc.executebuiltin('ShutDown')
        xbmc.sleep(2000)
        os._exit(1)

if __name__ == '__main__':
    run_first_run_setup()