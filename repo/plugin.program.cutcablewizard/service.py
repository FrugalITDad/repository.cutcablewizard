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

def is_skin_busy():
    """Check if Skin Shortcuts or typical busy dialogs are active."""
    # Window 10101 is the standard busy/info dialog used by Skin Shortcuts
    return (xbmc.getCondVisibility('Window.IsActive(10101)') or 
            xbmc.getCondVisibility('Library.IsScanning') or
            xbmc.getCondVisibility('Window.IsActive(infodialog)'))

def run_first_run_setup():
    # FORCE UNKNOWN SOURCES ON STARTUP
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')

    addon_data = get_addon_data()
    trigger_file = os.path.join(addon_data, 'firstrun.txt')
    if not os.path.exists(trigger_file): return

    monitor = xbmc.Monitor()
    
    # --- PHASE 1: THE IDLE WAIT ---
    # Give the skin a moment to even start the shortcut process
    xbmc.sleep(15000) 
    
    # Loop indefinitely until the skin is no longer "busy"
    # This prevents the setup from popping up WHILE the 'Building Menu' bar is visible
    while is_skin_busy():
        if monitor.waitForAbort(5): return
        xbmc.log("WIZARD: Waiting for Skin Shortcuts to finish...", xbmc.LOGINFO)

    # Extra buffer to allow the skin to finish its forced 'Reload'
    xbmc.sleep(10000) 

    dialog = xbmcgui.Dialog()
    
    # --- PHASE 2: SETUP DIALOGS ---
    if dialog.yesno("Setup (1/2): Trakt", "Authorize your main Trakt account?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    if xbmc.getCondVisibility('System.HasAddon(plugin.video.scrubsv2)'):
        if dialog.yesno("Setup (2/2): Scrubs V2", "Authorize Trakt inside Scrubs V2?"):
            # Execute direct action
            xbmc.executebuiltin('RunPlugin(plugin://plugin.video.scrubsv2/?action=authTrakt)')
            xbmc.sleep(12000) # Give the PIN popup time to render over the skin

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
    
    # Cleanup trigger
    try: os.remove(trigger_file)
    except: pass
    
    msg = "Setup complete! All background tasks and guide sync finished.\n\nRestart Kodi now?"
    if dialog.yesno("Success!", msg):
        xbmc.executebuiltin('ShutDown')

if __name__ == '__main__':
    run_first_run_setup()