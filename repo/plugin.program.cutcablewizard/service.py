import xbmc, xbmcgui, xbmcvfs, os, json

# Use special://home for the trigger location
HOME = xbmcvfs.translatePath("special://home/")

def is_skin_busy():
    # Check if Kodi is busy loading menus or scanning
    return (xbmc.getCondVisibility("Window.IsActive(busydialog)") or 
            xbmc.getCondVisibility("Window.IsActive(10101)") or 
            xbmc.getCondVisibility("Library.IsScanningVideo"))

def wait_for_settings():
    # Pauses script while the user is interacting with an addon settings window
    monitor = xbmc.Monitor()
    xbmc.sleep(2000)
    while xbmc.getCondVisibility("Window.IsActive(addonsettings)"):
        if monitor.waitForAbort(1): break

def run_service():
    monitor = xbmc.Monitor()
    
    # Wait 60s for FireStick hardware/skin textures to settle
    if monitor.waitForAbort(60): return 

    trigger = os.path.join(HOME, 'firstrun.txt')
    
    if os.path.exists(trigger):
        # Ensure the UI isn't currently blocked by other processes
        while is_skin_busy():
            if monitor.waitForAbort(5): return

        # Force a GUI refresh to make sure the build skin is fully active
        xbmc.executebuiltin('ReplaceWindow(10000)') 
        dialog = xbmcgui.Dialog()
        
        # Step 1: Device Name (Uses JSON-RPC to change core Kodi setting)
        name = dialog.input("Setup (1/5): Device Name", defaultt="Kodi-Firestick").strip()
        if name:
            xbmc.executeJSONRPC(json.dumps({
                "jsonrpc":"2.0",
                "method":"Settings.SetSettingValue",
                "params":{"setting":"services.devicename","value":name},
                "id":1
            }))
        
        # Step 2: Weather
        if dialog.yesno("Setup (2/5)", "Configure Weather?"):
            dialog.ok("Weather", "Search city manually. Do NOT use 'Current Location'.")
            xbmc.executebuiltin("Addon.OpenSettings(weather.gismeteo)")
            wait_for_settings()

        # Step 3: Subtitles
        if dialog.yesno("Setup (3/5)", "Enable automatic subtitles?"):
            xbmc.executeJSONRPC(json.dumps({
                "jsonrpc":"2.0",
                "method":"Settings.SetSettingValue",
                "params":{"setting":"subtitles.enabled","value":True},
                "id":1
            }))

        # Step 4: Trakt
        if dialog.yesno("Setup (4/5)", "Authorize Trakt account?"):
            xbmc.executebuiltin("Addon.OpenSettings(script.trakt)")
            wait_for_settings()

        # Step 5: PVR Sync with 145s Countdown
        if xbmc.getCondVisibility("System.HasAddon(plugin.program.iptvmerge)"):
            xbmc.executebuiltin("RunPlugin(plugin://plugin.program.iptvmerge/?mode=run)")
            
            # Start the countdown timer
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

        # Final Cleanup: Remove the trigger so this doesn't run again
        try: os.remove(trigger)
        except: pass
        
        xbmc.executebuiltin('SaveSceneSettings')
        
        # Final Success Message
        dialog.ok("Setup Complete", "Your CordCutter build is fully configured and ready to use!")

if __name__ == '__main__':
    run_service()