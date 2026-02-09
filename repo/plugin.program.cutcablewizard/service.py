import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def run_dependencies():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(15): return # Wait for Kodi to initialize

    xbmcgui.Dialog().notification("Wizard", "Enabling IPTV & Dependencies...", xbmcgui.NOTIFICATION_INFO, 5000)
    
    # List of required addons
    deps = [
        'pvr.iptvsimple', 
        'inputstream.adaptive', 
        'inputstream.ffmpegdirect', 
        'inputstream.rtmp'
    ]
    
    # 1. Force Kodi to see local changes
    xbmc.executebuiltin('UpdateLocalAddons')
    xbmc.executebuiltin('UpdateAddonRepos')
    
    # 2. Enable each one
    for d in deps:
        xbmc.executebuiltin(f'EnableAddon("{d}")')
        xbmc.sleep(500)

    # 3. Trigger IPTV Merge
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    
    # 4. Clean up trigger
    try: os.remove(TRIGGER_FILE)
    except: pass

if __name__ == '__main__':
    if os.path.exists(TRIGGER_FILE):
        run_dependencies()
