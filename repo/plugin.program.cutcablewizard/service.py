import xbmc, xbmcvfs, os, xbmcgui, json

ADDON_ID = 'plugin.program.cutcablewizard'

def get_addon_data():
    return xbmcvfs.translatePath('special://profile/addon_data/' + ADDON_ID)

def wait_for_settings_close():
    monitor = xbmc.Monitor()
    xbmc.sleep(2000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1): break
    xbmc.sleep(1500)

def is_skin_busy():
    # 10101 = Skin Shortcuts, infodialog = Busy/Building notifications
    return (xbmc.getCondVisibility('Window.IsActive(10101)') or 
            xbmc.getCondVisibility('Library.IsScanning') or
            xbmc.getCondVisibility('Window.IsActive(infodialog)'))

def run_first_run_setup():
    monitor = xbmc.Monitor()
    
    # --- PHASE 0: THE 45-SECOND BOOT DELAY ---
    if monitor.waitForAbort(45): return

    # Ensure Unknown Sources is enabled
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')

    addon_data = get_addon_data()
    trigger_file = os.path.join(addon_data, 'firstrun.txt')
    if not os.path.exists(trigger_file): return

    # --- PHASE 1: THE IDLE SAFETY LOOP ---
    while is_skin_busy():
        if monitor.waitForAbort(5): return
        xbmc.log("WIZARD: Waiting for Skin Shortcuts to finish...", xbmc.LOGINFO)

    xbmc.sleep(5000) 
    dialog = xbmcgui.Dialog()

    # --- STEP 1: DEVICE NAME ---
    device_name = dialog.input("Step 1: Set Device Name", defaultt="Kodi-Firestick")
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # --- STEP 2: WEATHER (Restored Logic) ---
    if dialog.yesno("Setup (3/4): Weather", "Would you like to configure your weather location?"):
        dialog.ok("Weather Hint", "Search for your city manually. Do NOT use 'Current Location'.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    # --- STEP 4: TRAKT (Standard Plugin) ---
    if dialog.yesno("Step 4: Trakt", "Authorize your main Trakt account?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- STEP 5: SCRUBS V2 (Updated Logic) ---
    if xbmc.getCondVisibility('System.HasAddon(plugin.video.scrubsv2)'):
        if dialog.yesno("Step 5: Scrubs V2", "Authorize Trakt inside Scrubs V2?"):
            # Guide the user before jumping in
            dialog.ok("Scrubs V2 Trakt", "The Tools menu will now open.\n\nPlease select 'Trakt: Authorize' from the list.")
            # Navigate directly to the Scrubs Tools menu
            xbmc.executebuiltin('ActivateWindow(Videos,"plugin://plugin.video.scrubsv2/?action=tools_menu",return)')
            # This loop waits for the user to finish in the Scrubs menu before continuing
            while xbmc.getCondVisibility('Window.IsActive(videos)'):
                if monitor.waitForAbort(1): break

    # --- PHASE 3: PVR SYNC ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Finalizing Build: Syncing Live TV Guide...")
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    total_wait = 145 
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        dp.update(percent, f"Syncing Guide... {i}s remaining.")

    while xbmc.getCondVisibility('PVR.IsUpdatingGuide'):
        if monitor.waitForAbort(3): break
        dp.update(99, "Guide is still processing...\nAlmost done.")

    dp.close()
    
    try: os.remove(trigger_file)
    except: pass
    
    xbmc.executebuiltin('SaveSceneSettings') 
    if dialog.yesno("Success!", "Setup complete! Restart Kodi now?"):
        xbmc.executebuiltin('ShutDown')

if __name__ == '__main__':
    run_first_run_setup()