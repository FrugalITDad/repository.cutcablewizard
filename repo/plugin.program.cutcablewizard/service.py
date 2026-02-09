import xbmc, xbmcaddon, xbmcvfs, os, json, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')
SKIN_ID = 'skin.aeonnox.silvo'

def apply_fixes():
    # 1. FORCE THE SKIN (Visual First)
    # We do this twice: once via JSON and once via Built-in
    xbmc.log("--- [Wizard Service] Forcing Skin...", xbmc.LOGINFO)
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"lookandfeel.skin","value":"{SKIN_ID}"}},"id":1}}')
    xbmc.executebuiltin(f'SetProperty(reloadsmooth,true,home)')
    
    xbmc.sleep(2000)
    
    # 2. TRIGGER IPTV MERGE & PVR
    xbmc.log("--- [Wizard Service] Rebuilding PVR...", xbmc.LOGINFO)
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')
    
    # 3. CLEANUP
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)
    
    xbmcgui.Dialog().notification("Wizard", "Optimization Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    # Initial wait to let the Android UI finish loading
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(15): exit()

    if os.path.exists(TRIGGER_FILE):
        apply_fixes()
