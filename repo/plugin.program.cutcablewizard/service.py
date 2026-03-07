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
    
    # 1. Wait 45s for initial skin load
    if monitor.waitForAbort(45): return 
    
    # 2. Safety: Wait if a generic dialog is active (like 'Skin Shortcuts' or 'Scanning Library')
    while xbmc.getCondVisibility('Window.IsActive(infodialog)') or xbmc.getCondVisibility('Library.IsScanning'):
        if monitor.waitForAbort(5): break
    
    dialog = xbmcgui.Dialog()
    
    # --- SETUP DIALOGS ---
    if dialog.yesno("Setup (1/2): Trakt", "Authorize your main Trakt account?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    if xbmc.getCondVisibility('System.HasAddon(plugin.video.scrubsv2)'):
        if dialog.yesno("Setup (2/2): Scrubs V2", "Authorize Trakt inside Scrubs V2?"):
            # Stronger plugin call
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.scrubsv2/?action=authTrakt)')
            xbmc.sleep(10000) # Increased to 10s to ensure pop-up renders

    # --- PVR SYNC ---
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
        dp.update(99, "Kodi is still processing the Guide data...\nPlease wait.")

    dp.close()
    try: os.remove(trigger_file)
    except: pass
    
    if dialog.yesno("All Done!", "Setup complete! Restart Kodi now to finalize changes?"):
        xbmc.executebuiltin('ShutDown')

if __name__ == '__main__': run_first_run_setup()