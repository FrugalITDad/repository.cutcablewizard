import xbmc, xbmcaddon, xbmcvfs, os, json, xbmcgui

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')
SKIN_ID = 'skin.aeonnox.silvo'

def run_json(method, params):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return xbmc.executeJSONRPC(json.dumps(query))

def apply_total_recovery():
    xbmc.log("--- [Wizard Service] Starting Global Addon Recovery...", xbmc.LOGINFO)
    
    # 1. GET A LIST OF ALL INSTALLED ADDONS
    # We ask Kodi for everything currently sitting in the addons folder
    result = run_json("Addons.GetAddons", {"installed": True})
    data = json.loads(result)
    
    if 'result' in data and 'addons' in data['result']:
        all_addons = data['result']['addons']
        
        # 2. THE GLOBAL ENABLE LOOP
        # This turns ON every addon (Skin, PVR, Scripts, etc.)
        for item in all_addons:
            a_id = item['addonid']
            run_json("Addons.SetAddonEnabled", {"addonid": a_id, "enabled": True})
    
    xbmc.sleep(2000)

    # 3. FORCE THE SKIN GUI SWITCH
    # Now that the skin addon is definitely enabled, we apply the look
    run_json("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": SKIN_ID})
    
    xbmc.sleep(1000)

    # 4. TRIGGER IPTV MERGE & PVR RELOAD
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.iptvmerge, "merge")')
    
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')
    
    # 5. CLEANUP
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)
    
    xbmcgui.Dialog().notification("Wizard", "All Addons & Skin Restored!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    # 20 seconds is the "Golden Window" for Fire Sticks to finish their background scan
    if monitor.waitForAbort(20): 
        exit()

    if os.path.exists(TRIGGER_FILE):
        apply_total_recovery()
