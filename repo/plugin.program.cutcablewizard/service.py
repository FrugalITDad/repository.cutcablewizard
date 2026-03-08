import xbmc, xbmcgui, xbmcvfs, os, json

HOME = xbmcvfs.translatePath("special://home/")

def is_skin_busy():
    return (xbmc.getCondVisibility("Window.IsActive(busydialog)") or 
            xbmc.getCondVisibility("Window.IsActive(10101)") or 
            xbmc.getCondVisibility("Library.IsScanningVideo"))

def wait_for_settings():
    monitor = xbmc.Monitor()
    xbmc.sleep(2000)
    while xbmc.getCondVisibility("Window.IsActive(addonsettings)"):
        if monitor.waitForAbort(1): break

def run_service():
    monitor = xbmc.Monitor()
    
    # Wait 60s for background services to stabilize
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
            xbmc.executebuiltin("Addon.OpenSettings(weather.gismeteo)")
            wait_for_settings()

        # Step 3: Subtitles
        if dialog.yesno("Setup (3/5)", "Enable automatic subtitles?"):
            xbmc.executeJSONRPC(json.dumps({"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":True},"id":1}))

        # Step 4: Trakt
        if dialog.yesno("Setup (4/5)", "Authorize Trakt account?"):
            xbmc.executebuiltin("Addon.OpenSettings(script.trakt)")
            wait_for_settings()

        # Step 5: Forced PVR Sync & Mandatory Timer
        # We fire the merge command and force the timer regardless of boolean checks
        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.iptvmerge/?mode=run)")
        
        dp = xbmcgui.DialogProgress()
        dp.create("CordCutter", "Syncing Live TV Guide...")
        
        total_time = 145
        for i in range(total_time):
            if monitor.waitForAbort(1) or dp.iscanceled():
                break
            
            percent = int((i / float(total_time)) * 100)
            remaining = total_time - i
            dp.update(percent, f"Finalizing IPTV Guide setup...\nTime remaining: {remaining}s")
        
        dp.close()

        # Final Cleanup: Remove trigger only after timer finishes
        try: os.remove(trigger)
        except: pass
        
        xbmc.executebuiltin('SaveSceneSettings')
        
        # Final Success Message - Now physically impossible to show before timer
        dialog.ok("Setup Complete", "Your CordCutter build is fully configured and ready to use!")

if __name__ == '__main__':
    run_service()