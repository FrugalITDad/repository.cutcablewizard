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
    if not os.path.exists(trigger_file): return

    monitor = xbmc.Monitor()
    
    # 1. WAIT FOR SKIN & BACKGROUND TASKS
    # Give the skin 45 seconds to start building its menu
    if monitor.waitForAbort(45): return 
    
    # 2. SMART WAIT: Don't pop up if Skin Shortcuts or Library is busy
    while xbmc.getCondVisibility('Window.IsActive(infodialog)') or xbmc.getCondVisibility('Library.IsScanning'):
        if monitor.waitForAbort(5): break
    
    dialog = xbmcgui.Dialog()
    
    # --- TRAKT MAIN ---
    if dialog.yesno("Setup (1/2): Trakt", "Authorize your main Trakt account?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- SCRUBS V2 TRAKT (Direct Trigger) ---
    if xbmc.getCondVisibility('System.HasAddon(plugin.video.scrubsv2)'):
        if dialog.yesno("Setup (2/2): Scrubs V2", "Authorize Trakt for Scrubs V2 (Plus Build)?"):
            # Using the direct action URL to force the PIN popup
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.scrubsv2/?action=authTrakt)')
            xbmc.sleep(8000) # Longer sleep to allow PIN window to generate

    # --- IPTV SYNC ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Finalizing Build: Syncing Live TV Guide...")
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')

    total_wait = 145 
    for i in range(total_wait, 0, -1):
        if monitor.waitForAbort(1): break
        percent = int(((total_wait - i) / float(total_wait)) * 100)
        dp.update(percent, f"Syncing Guide... {i}s remaining.")

    # 3. PVR BUSY CHECK
    while xbmc.getCondVisibility('PVR.IsUpdatingGuide'):
        if monitor.waitForAbort(3): break
        dp.update(99, "Guide is still processing...\nAlmost done.")

    dp.close()
    try: os.remove(trigger_file)
    except: pass
    
    # 4. FINAL REBOOT MESSAGE
    msg = ("Setup complete! All background tasks and guide updates have finished.\n\n"
           "Click YES to Restart Kodi now and apply all changes.")
    if dialog.yesno("Success!", msg):
        xbmc.executebuiltin('ShutDown')

if __name__ == '__main__':
    run_first_run_setup()