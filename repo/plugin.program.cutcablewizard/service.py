import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard'
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_post_install():
    # Wait for Kodi to initialize fully
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(5): return

    # Check if we just installed a build
    if not os.path.exists(TRIGGER_FILE): return

    xbmcgui.Dialog().notification("CutCable Wizard", "Finishing Setup...", xbmcgui.NOTIFICATION_INFO, 5000)
    
    # 1. Force update repos
    xbmc.executebuiltin('UpdateLocalAddons')
    xbmc.executebuiltin('UpdateAddonRepos')
    
    # 2. Switch Skin (Try up to 5 times)
    target_skin = 'skin.aeonnox.silvo' # CHANGE THIS to your skin ID
    
    for i in range(5):
        current = xbmc.getSkinDir()
        if current == target_skin:
            xbmcgui.Dialog().notification("Success", "Skin Loaded!", xbmcgui.NOTIFICATION_INFO, 3000)
            break
            
        # Send command to switch
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"lookandfeel.skin","value":"%s"},"id":1}' % target_skin)
        xbmc.sleep(2000)
        
        # Blindly click "Yes" (ID 11) to confirm "Keep this change?" dialog
        xbmc.executebuiltin('SendClick(11)') 
        xbmc.sleep(3000)

    # 3. Cleanup
    try: os.remove(TRIGGER_FILE)
    except: pass

if __name__ == '__main__':
    run_post_install()
