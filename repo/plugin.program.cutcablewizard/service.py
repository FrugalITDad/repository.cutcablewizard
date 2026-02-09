import xbmc, xbmcaddon, xbmcvfs, os, json, urllib.request, ssl, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard'
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_json(method, params):
    query = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return xbmc.executeJSONRPC(json.dumps(query))

def first_run_setup():
    xbmc.log("--- [Wizard] First Run Setup Started", xbmc.LOGINFO)
    
    # Force the skin again just in case
    run_json("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": "skin.aeonnox.silvo"})
    
    # Force Enable Addons
    binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
    for addon_id in binaries:
        run_json("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})
    
    xbmc.sleep(3000)
    
    # IPTV Merge
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.iptvmerge, "merge")')
    
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')
    
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)
    
    xbmcgui.Dialog().notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    # Wait 15 seconds for Android to fully mount the storage and start the GUI
    if monitor.waitForAbort(15): exit()

    if os.path.exists(TRIGGER_FILE):
        first_run_setup()
