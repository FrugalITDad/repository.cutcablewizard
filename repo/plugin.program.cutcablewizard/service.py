import xbmc, xbmcgui, xbmcvfs, os, json, ssl, urllib.request

# Look in HOME (root) for the trigger
HOME = xbmcvfs.translatePath("special://home/")
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def is_skin_busy():
    return (xbmc.getCondVisibility("Window.IsActive(busydialog)") or 
            xbmc.getCondVisibility("Window.IsActive(10101)") or 
            xbmc.getCondVisibility("Library.IsScanningVideo"))

def run_service():
    monitor = xbmc.Monitor()
    
    # Wait 45s for hardware to settle
    if monitor.waitForAbort(45): return 

    trigger = os.path.join(HOME, 'firstrun.txt')
    
    if os.path.exists(trigger):
        # Wait for any background skin loading to finish
        while is_skin_busy():
            if monitor.waitForAbort(5): return

        # Force GUI refresh to ensure Aeon Nox Silvo is active
        xbmc.executebuiltin('ReplaceWindow(10000)') 
        
        dialog = xbmcgui.Dialog()
        
        # Step 1: Device Name
        name = dialog.input("Setup (1/3): Device Name", defaultt="Kodi-Firestick").strip()
        if name:
            xbmc.executeJSONRPC(json.dumps({
                "jsonrpc":"2.0",
                "method":"Settings.SetSettingValue",
                "params":{"setting":"services.devicename","value":name},
                "id":1
            }))
        
        # Step 2: Weather
        if dialog.yesno("Setup (2/3)", "Configure Weather?"):
            dialog.ok("Weather", "Search city manually. Do NOT use 'Current Location'.")
            xbmc.executebuiltin("Addon.OpenSettings(weather.gismeteo)")

        # Step 3: PVR/IPTV Sync
        if xbmc.getCondVisibility("System.HasAddon(plugin.program.iptvmerge)"):
            dialog.notification("PVR Sync", "Synchronizing Live TV Guide...", xbmcgui.NOTIFICATION_INFO, 5000)
            xbmc.executebuiltin("RunPlugin(plugin://plugin.program.iptvmerge/?mode=run)")
        
        # Cleanup
        try: os.remove(trigger)
        except: pass
        
        xbmc.executebuiltin('SaveSceneSettings')
        dialog.ok("Setup Complete", "Your CordCutter build is ready to use!")

if __name__ == '__main__':
    run_service()