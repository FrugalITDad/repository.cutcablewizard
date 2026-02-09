import xbmc, xbmcaddon, xbmcvfs, os, json, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_enforcer():
    # 1. Global Enable Addons
    query = {"jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddons", "params": {"installed": True, "enabled": False}}
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
        if 'result' in result and 'addons' in result['result']:
            for addon in result['result']['addons']:
                a_id = addon['addonid']
                xbmc.executebuiltin(f'EnableAddon("{a_id}")')
    except: pass

    # 2. Confirm Skin Switch (Clicks 'Yes' on hidden prompt)
    xbmc.executebuiltin('SendClick(11)') 
    xbmc.executebuiltin('SetProperty(reloadsmooth,true,home)')

    # 3. Clean AdvancedSettings (Remove the force-skin block)
    adv_file = xbmcvfs.translatePath("special://userdata/advancedsettings.xml")
    if os.path.exists(adv_file):
        try: os.remove(adv_file)
        except: pass
    
    # 4. PVR Refresh
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')

    # 5. Remove Trigger
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    # Wait for Kodi to initialize
    if monitor.waitForAbort(20): exit()
    
    if os.path.exists(TRIGGER_FILE):
        run_enforcer()
