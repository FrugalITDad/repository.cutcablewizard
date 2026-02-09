import xbmc, xbmcaddon, xbmcvfs, os, json, xbmcgui

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_json(method, params):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return xbmc.executeJSONRPC(json.dumps(query))

def final_cleanup():
    xbmc.log("--- [Wizard Service] Running Final Addon Activation...", xbmc.LOGINFO)
    
    # 1. BULK ENABLE LOOP
    # This captures any addon the default.py might have missed or Kodi disabled on boot
    result = run_json("Addons.GetAddons", {"installed": True, "enabled": False})
    data = json.loads(result)
    
    if 'result' in data and 'addons' in data['result']:
        for item in data['result']['addons']:
            a_id = item['addonid']
            # Force enable via JSON and Built-in for redundancy
            run_json("Addons.SetAddonEnabled", {"addonid": a_id, "enabled": True})
            xbmc.executebuiltin(f'EnableAddon("{a_id}")')

    xbmc.sleep(2000)

    # 2. TRIGGER PVR RELOAD
    # Ensures the channels actually show up once the PVR addon is enabled
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')
    
    # 3. SELF-DESTRUCT TRIGGER
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)
    
    xbmcgui.Dialog().notification("Wizard", "Build Optimization Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    # 15-second wait to let the Fire Stick stabilize
    if monitor.waitForAbort(15): 
        exit()

    if os.path.exists(TRIGGER_FILE):
        final_cleanup()
