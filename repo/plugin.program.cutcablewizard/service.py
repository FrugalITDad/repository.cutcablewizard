import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os, json, ssl, urllib.request

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_json(url):
    try:
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(url, context=context, timeout=10) as r:
            return json.loads(r.read().decode('utf-8'))
    except: return None

def is_skin_busy():
    return (xbmc.getCondVisibility("Window.IsActive(busydialog)") or 
            xbmc.getCondVisibility("Window.IsActive(10101)") or 
            xbmc.getCondVisibility("Library.IsScanningVideo"))

def run_service():
    monitor = xbmc.Monitor()
    
    # --- 45 SECOND SAFETY DELAY ---
    if monitor.waitForAbort(45): return 

    # --- PART 1: FIRST RUN SETUP ---
    trigger = os.path.join(ADDON_DATA, 'firstrun.txt')
    if os.path.exists(trigger):
        while is_skin_busy():
            if monitor.waitForAbort(5): return
        
        dialog = xbmcgui.Dialog()
        # Device Name
        name = dialog.input("Step 1: Device Name", defaultt="Kodi-Firestick").strip()
        if name:
            xbmc.executeJSONRPC(json.dumps({"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":name},"id":1}))
        
        # Weather
        if dialog.yesno("Setup", "Configure Weather (Gismeteo)?"):
            dialog.ok("Weather", "Search city manually. Do NOT use 'Current Location'.")
            xbmc.executebuiltin("Addon.OpenSettings(weather.gismeteo)")

        # PVR Sync
        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.iptvmerge/?mode=run)")
        
        try: os.remove(trigger)
        except: pass
        xbmc.executebuiltin('SaveSceneSettings')

    # --- PART 2: UPDATE CHECK ---
    v_file = os.path.join(ADDON_DATA, 'installed_version.txt')
    if os.path.exists(v_file):
        with open(v_file) as f: current = f.read().strip()
        manifest = get_json(MANIFEST_URL)
        if manifest:
            for build in manifest.get('builds', []):
                if build['version'] != current:
                    xbmcgui.Dialog().notification("Wizard", f"New update available: v{build['version']}", xbmcgui.NOTIFICATION_INFO, 5000)
                    break

if __name__ == '__main__':
    run_service()