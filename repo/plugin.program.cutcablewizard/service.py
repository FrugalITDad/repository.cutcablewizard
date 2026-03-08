import xbmc, xbmcgui, xbmcvfs, os, json

HOME = xbmcvfs.translatePath("special://home/")

def is_skin_busy():
    return (xbmc.getCondVisibility("Window.IsActive(busydialog)") or 
            xbmc.getCondVisibility("Window.IsActive(10101)") or 
            xbmc.getCondVisibility("Library.IsScanningVideo"))

def wait_for_settings():
    # Helper to pause the script while a settings window is open
    monitor = xbmc.Monitor()
    xbmc.sleep(2000)
    while xbmc.getCondVisibility("Window.IsActive(addonsettings)"):
        if monitor.waitForAbort(1): break

def run_service():
    monitor = xbmc.Monitor()
    
    # Wait 60s for FireStick to initialize
    if monitor.waitForAbort(60): return 

    trigger = os.path.join(HOME, 'firstrun.txt')
    
    if os.path.exists(trigger):
        while is_skin_busy():
            if monitor.waitForAbort(5): return

        xbmc.executebuiltin('ReplaceWindow(10000)') 
        dialog = xbmcgui.Dialog()
        
        # Step 1: Device Name
        name = dialog.input("Setup (1/5): Device Name", defaultt="Kodi-Firestick").strip()
        if name:
            xbmc.executeJSONRPC(json.dumps({"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":name},"id":1}))
        
        # Step 2: Weather
        if dialog.yesno("Setup (2/5)", "Configure Weather?"):
            dialog.ok("Weather", "Search city manually. Do NOT use 'Current Location'.")
            xbmc.executebuiltin("Addon.OpenSettings(weather.gismeteo)")
            wait_for_settings()

        # Step 3: Subtitles
        if dialog.yesno("Setup (3/5)", "Enable automatic subtitles?"):
            xbmc.executeJSONRPC(json.dumps({"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":True},"id":1}))

        # Step 4: Trakt
        if dialog.yesno("Setup (4/5)", "Authorize Trakt account?"):
            xbmc.executebuiltin("Addon.OpenSettings(script.trakt)")
            wait_for_settings()

        # Step 5: PVR Sync
        dialog.notification("Step 5/5", "Syncing Live TV Guide...", xbmcgui.NOTIFICATION_INFO, 5000)
        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.iptvmerge/?mode=run)")
        
        # Final Cleanup
        try: os.remove(trigger)
        except: pass
        
        xbmc.executebuiltin('SaveSceneSettings')
        
        # NOW show the final message
        dialog.ok("Setup Complete", "Your CordCutter build is fully configured and ready to use!")

if __name__ == '__main__':
    run_service()