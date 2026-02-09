import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def run_dependencies():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(20): return # Give Kodi time to connect to Wi-Fi

    xbmcgui.Dialog().notification("CordCutter", "Finalizing IPTV Components...", xbmcgui.NOTIFICATION_INFO, 5000)
    
    # 1. Force Kodi to refresh its repository list
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.executebuiltin('UpdateLocalAddons')
    xbmc.sleep(2000)

    deps = [
        'inputstream.adaptive', 
        'inputstream.ffmpegdirect', 
        'inputstream.rtmp',
        'pvr.iptvsimple'
    ]
    
    for d in deps:
        # This command attempts to install from the repo if missing, or enable if present
        xbmc.executebuiltin(f'InstallAddon("{d}")')
        xbmc.sleep(1000)

    # 2. Trigger IPTV Merge
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    
    # 3. Cleanup trigger
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    xbmcgui.Dialog().ok("Wizard", "IPTV Components Restored!\nYou may need to restart Kodi one last time.")

if __name__ == '__main__':
    if os.path.exists(TRIGGER_FILE):
        run_dependencies()
