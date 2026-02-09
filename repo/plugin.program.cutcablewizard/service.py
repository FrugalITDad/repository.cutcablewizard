import xbmc, xbmcaddon, xbmcvfs, os, json, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_enforcer():
    # 1. ENABLE ALL ADDONS
    xbmc.executebuiltin('UpdateLocalAddons')
    query = {"jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddons", "params": {"installed": True, "enabled": False}}
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
        if 'result' in result and 'addons' in result['result']:
            for addon in result['result']['addons']:
                xbmc.executebuiltin(f'EnableAddon("{addon["addonid"]}")')
    except: pass

    # 2. THE PERSISTENT SKIN FLIP
    # Tries to flip the skin and clicks 'Yes' every 5 seconds until it works
    for i in range(10): 
        if xbmc.getSkinDir() == 'skin.aeonnox.silvo':
            xbmc.log("--- [Wizard] Skin verify success!", xbmc.LOGINFO)
            break
        
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"lookandfeel.skin","value":"skin.aeonnox.silvo"},"id":1}')
        xbmc.executebuiltin('SendClick(11)') 
        xbmc.sleep(5000)

    # 3. CLEANUP ADVANCEDSETTINGS
    adv_file = xbmcvfs.translatePath("special://userdata/advancedsettings.xml")
    if os.path.exists(adv_file):
        try: os.remove(adv_file)
        except: pass
    
    # 4. FIRST RUN (IPTV MERGE)
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')

    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)
    
    xbmcgui.Dialog().notification("Wizard", "Build fully activated!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    # 30 second lead-time for Fire Stick stability
    if monitor.waitForAbort(30): exit()
    if os.path.exists(TRIGGER_FILE):
        run_enforcer()
