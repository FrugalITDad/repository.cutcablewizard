import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def run_activation():
    monitor = xbmc.Monitor()
    # Wait 30 seconds for Fire Stick to rebuild Addons.db
    if monitor.waitForAbort(30): return 

    xbmcgui.Dialog().notification("CordCutter", "Activating Build Components...", xbmcgui.NOTIFICATION_INFO, 5000)
    
    # 1. Update Check (Force Kodi to check for new Wizard version)
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.sleep(2000)
    xbmc.executebuiltin(f'InstallAddon({ADDON_ID})')

    # 2. Mass Enable All Addons (Fixes "Disabled" state after DB nuke)
    query = '{"jsonrpc":"2.0","method":"Addons.GetAddons","params":{"enabled":false},"id":1}'
    response = xbmc.executeJSONRPC(query)
    data = json.loads(response)
    
    if 'result' in data and 'addons' in data['result']:
        for item in data['result']['addons']:
            aid = item['addonid']
            xbmc.executebuiltin(f'EnableAddon("{aid}")')
            xbmc.sleep(200)

    # 3. Restore Binary Addons from Repo (Official Android versions)
    deps = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
    for d in deps:
        xbmc.executebuiltin(f'InstallAddon("{d}")')
        xbmc.sleep(500)

    # 4. Set the Skin (Forces the UI to switch)
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"lookandfeel.skin","value":"skin.aeon.nox.silvo"},"id":1}')

    # 5. Clean up
    if os.path.exists(TRIGGER_FILE):
        try: os.remove(TRIGGER_FILE)
        except: pass
    
    xbmcgui.Dialog().notification("CordCutter", "Build Fully Activated!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    if os.path.exists(TRIGGER_FILE):
        run_activation()
