import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def wait_for_settings_close():
    """Wait loop for non-blocking settings windows"""
    monitor = xbmc.Monitor()
    xbmc.sleep(1000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1):
            break
    xbmc.sleep(500)

def run_first_run_setup():
    monitor = xbmc.Monitor()
    # Wait for the skin (Aeon Nox Silvo) to fully initialize
    if monitor.waitForAbort(10): return 

    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    
    # 1. SUBTITLES
    if dialog.yesno("Setup (1/4): Subtitles", "Would you like subtitles to be on by default?"):
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

    # --- FINAL PHASE: IPTV & PVR (With Progress Dialog) ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Finishing Final Configurations...")
    
    # A. Setup Simple Client Paths
    dp.update(25, "Mapping Live TV Components...")
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(4000)

    # B. Trigger the Merge
    dp.update(50, "Merging Channels and EPG...")
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')
    xbmc.sleep(4000)

    # C. Update PVR Database
    dp.update(75, "Indexing Live TV Guide...")
    xbmc.executebuiltin('UpdatePVR')
    xbmc.sleep(2000)

    # FINAL CLEANUP
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    dp.update(100, "Setup Complete!")
    xbmc.sleep(1000)
    dp.close()
    
    # --- REBOOT PROMPT ---
    # Closing and reopening is essential for EPG and Weather refresh
    if dialog.yesno("All Set!", "Setup is complete! To ensure the TV Guide and Weather are fully loaded, you must restart Kodi.\n\nRestart now?"):
        # This triggers a Quit which, on Fire TV, usually requires a manual relaunch
        xbmc.executebuiltin('Quit')

if __name__ == '__main__':
    run_first_run_setup()