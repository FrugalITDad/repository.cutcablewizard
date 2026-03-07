import xbmc, xbmcvfs, os, xbmcgui

# --- CONFIGURATION (Zero-ID Approach) ---
ADDON_ID = 'plugin.program.cutcablewizard'

def get_addon_data():
    """Bypasses xbmcaddon.Addon() to prevent startup crashes"""
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

    # Exit immediately if the wizard hasn't just finished an install
    if not os.path.exists(trigger_file): 
        return

    monitor = xbmc.Monitor()
    # Initial 12s buffer to let the skin and network load
    if monitor.waitForAbort(12): return 

    dialog = xbmcgui.Dialog()
    
    # --- PHASE 1: PERSONALIZATION ---
    if dialog.yesno("Setup (1/5): Subtitles", "Enable subtitles by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    device_name = dialog.input("Setup (2/5): Device Name", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    if dialog.yesno("Setup (3/5): Weather", "Configure your local weather?"):
        dialog.ok("Weather Hint", "Search for your city manually. Do NOT use 'Current Location'.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    # --- PHASE 2: AUTHORIZATION ---
    if dialog.yesno("Setup (4/5): Trakt", "Authorize your Trakt account?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- PLUS BUILD SPECIAL CHECK ---
    # Only shows if Scrubs V2 is detected on the system
    if xbmc.getCondVisibility('System.HasAddon(plugin.video.scrubsv2)'):
        if dialog.yesno("Setup (5/5): Scrubs V2", "Authorize Trakt inside Scrubs V2 (Plus Build Feature)?"):
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.scrubsv2/?action=authTrakt)')
            # Small sleep to let the PIN popup appear
            xbmc.sleep(3000)

    # --- PHASE 3: LIVE TV SYNC (145s Countdown) ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Finalizing Build: Syncing Live TV Guide...")
    
    # Trigger IPTV Merge
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(3000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    total_wait = 145 
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        msg = f"Syncing Channels & EPG Guide...\nTime Remaining: {i}s"
        dp.update(percent, msg)

    dp.update(99, "Refreshing TV Database... almost done.")
    xbmc.executebuiltin('UpdatePVR')
    xbmc.sleep(5000)

    # Cleanup trigger
    try: os.remove(trigger_file)
    except: pass
    
    dp.close()
    
    # --- FINAL REBOOT ---
    if dialog.yesno("Success!", "Setup complete! Restart Kodi now to apply all changes?"):
        xbmc.executebuiltin('ShutDown')

if __name__ == '__main__':
    run_first_run_setup()