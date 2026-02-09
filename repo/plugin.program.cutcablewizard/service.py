import xbmc, xbmcaddon, xbmcvfs, os, json, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_json(method, params):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return xbmc.executeJSONRPC(json.dumps(query))

def apply_fixes():
    xbmc.log("--- [Wizard Service] Starting Global Enable...", xbmc.LOGINFO)
    
    # 1. ENABLE EVERYTHING DISABLED
    # This turns on the Repo, the Wizard, and all Build Addons
    result = run_json("Addons.GetAddons", {"installed": True, "enabled": False})
    try:
        data = json.loads(result)
        if 'result' in data and 'addons' in data['result']:
            for item in data['result']['addons']:
                a_id = item['addonid']
                run_json("Addons.SetAddonEnabled", {"addonid": a_id, "enabled": True})
                xbmc.executebuiltin(f'EnableAddon("{a_id}")')
    except: pass

    xbmc.sleep(2000)
    
    # 2. FORCE SKIN AND PVR
    run_json("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": "skin.aeonnox.silvo"})
    
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')
    
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    # 20 second wait for Android background tasks to finish
    if monitor.waitForAbort(20): exit()
    if os.path.exists(TRIGGER_FILE):
        apply_fixes()
