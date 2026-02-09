import xbmc, xbmcaddon, xbmcvfs, os

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

def run_update_check():
    monitor = xbmc.Monitor()
    # Wait for Kodi to initialize and connect to network
    if monitor.waitForAbort(15): return 

    # 1. Force a refresh of all repositories
    xbmc.executebuiltin('UpdateAddonRepos')
    
    # 2. Give the repos a moment to sync metadata
    xbmc.sleep(5000)
    
    # 3. Trigger the update check/install for the Wizard specifically
    # If a newer version is in the repo, Kodi will download and install it now
    xbmc.executebuiltin(f'InstallAddon({ADDON_ID})')

if __name__ == '__main__':
    run_update_check()
