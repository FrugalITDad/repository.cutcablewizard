import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def wait_for_settings_close():
    """Wait loop for non-blocking settings windows"""
    monitor = xbmc.Monitor()
    xbmc.sleep(1500) # Increased delay to let window fully focus
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1): break
    xbmc.sleep(2000) # Buffer to ensure Kodi UI is stable after closing

def run_first_run_setup():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(10): return 

    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    
    # 1. SUBTITLES
    if dialog.yesno("Setup (1/4): Subtitles", "Would you like subtitles on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    # 2. DEVICE NAME
    device_name = dialog.input("Setup (2/4): Name this device", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # 3. WEATHER
    if dialog.yesno("Setup (3/4): Weather", "Would you like to configure the weather location?"):
        dialog.ok("Weather Hint", "HINT: Please do NOT turn on 'Current Location'.\nEnter city manually in the next screen.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    # 4. TRAKT
    if dialog.yesno("Setup (4/4): Trakt", "Would you like to configure the Trakt application?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- FINAL PHASE: IPTV MERGE & COUNTDOWN ---
    # We wrap this in a try block to prevent an 'AttributeError' if the UI is busy
    dp = xbmcgui.DialogProgress()
    try:
        dp.create("CordCutter", "Starting Live TV Merge...")
        
        # Trigger the commands
        xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
        xbmc.sleep(2000)
        xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

        # 60 Second Countdown
        for i in range(60, 0, -1):
            if monitor.waitForAbort(1): break
            percent = int(((60 - i) / 60.0) * 100)
            dp.update(percent, f"Finalizing Live TV Setup... {i}s remaining", "Please do not touch your remote.")

        dp.close()
    except:
        # Fallback if the Dialog fails: use standard notifications
        xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
        xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')
        dialog.notification("CordCutter", "Running Live TV Sync in background (60s)...", xbmcgui.NOTIFICATION_INFO, 10000)
        xbmc.sleep(60000)

    # Update PVR after the merge should be finished
    xbmc.executebuiltin('UpdatePVR')
    xbmc.sleep(3000)

    # Cleanup trigger file
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    # Final Restart Prompt
    msg = "All configurations applied!\nTo see your new Weather and TV Guide, Kodi needs a quick restart."
    if dialog.yesno("Success!", msg, "Restart Kodi now?", "Later"):
        xbmc.executebuiltin('Quit')

if __name__ == '__main__':
    run_first_run_setup()