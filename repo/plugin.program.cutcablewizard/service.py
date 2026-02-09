import xbmc, xbmcaddon, xbmcvfs, os, json, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')
SKIN_ID = 'skin.aeonnox.silvo'

def run_json(method, params):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return xbmc.executeJSONRPC(json.dumps(query))

def apply_total_recovery():
    # 1. THE BULK ENABLE
    # We fetch every addon and force it ON. This fixes the Repo and Wizard being disabled.
    result = run_json("Addons.GetAddons", {"installed": True})
    data = json.loads(result)
    if 'result' in data and 'addons' in data['result']:
        for item in data['result']['addons']:
            run_json("Addons.SetAddonEnabled", {"addonid": item['addonid'], "enabled": True})
    
    xbmc.sleep(2000)

    # 2. THE SKIN SWITCH
    run_json("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": SKIN_ID})
    
    # 3. PVR & IPTV MERGE
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.iptvmerge, "merge")')
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')
    
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)
    xbmcgui.Dialog().notification("Wizard", "Build fully activated!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    # 30 second wait is now required because we are enabling the WHOLE system.
    if monitor.waitForAbort(30): exit()
    if os.path.exists(TRIGGER_FILE):
        apply_total_recovery()
