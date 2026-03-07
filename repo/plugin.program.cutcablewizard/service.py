import xbmc, xbmcvfs, os, xbmcgui

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
    if monitor.waitForAbort(10): return 

    dialog = xbmcgui.Dialog()
    
    # --- STEP 1: TRAKT MAIN ---
    if dialog.yesno("Setup (1/2): Trakt", "Authorize your main Trakt account for history syncing?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- STEP 2: SCRUBS V2 (Plus Build Fix) ---
    if xbmc.getCondVisibility('System.HasAddon(plugin.video.scrubsv2)'):
        if dialog.yesno("Setup (2/2): Scrubs V2", "Authorize Trakt inside Scrubs V2 now?"):
            # Updated trigger: forcing the plugin to open the Trakt Auth window directly
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.scrubsv2/?action=authTrakt)')
            # We give it a long sleep here because Trakt popups can be slow to appear
            xbmc.sleep(5000) 

    # --- PHASE 3: LIVE TV SYNC ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Finalizing Build: Syncing Live TV Guide...")
    
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    # 145s Countdown for IPTV Merge
    total_wait = 145 
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        dp.update(percent, f"Syncing Channels & EPG...\nTime Remaining: {i}s")

    # --- NEW: PVR BUSY CHECK ---
    # This loop waits if Kodi is still internally processing the guide (EPG)
    while xbmc.getCondVisibility('PVR.IsUpdatingGuide'):
        if monitor.waitForAbort(2): break
        dp.update(99, "Kodi is still processing the Guide data...\nPlease wait a moment.")

    try: os.remove(trigger_file)
    except: pass
    
    dp.close()
    
    # --- UPDATED FINAL MESSAGE ---
    final_msg = ("Setup complete! All background tasks and guide updates have finished.\n\n"
                 "Click YES to Restart Kodi now and launch your new build.")
    
    if dialog.yesno("All Done!", final_msg):
        xbmc.executebuiltin('ShutDown')

if __name__ == '__main__':
    run_first_run_setup()