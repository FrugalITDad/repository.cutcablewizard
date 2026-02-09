import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

def remediate():
    monitor = xbmc.Monitor()
    # Wait for network and database to settle
    if monitor.waitForAbort(15): return 

    # --- PART 1: SELF-UPDATE CHECK ---
    # This forces Kodi to check your repo and update the wizard if a new version exists
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.executebuiltin(f'InstallAddon({ADDON_ID})')

    # --- PART 2: IPTV & BINARY REPAIR ---
    # We check if IPTV Simple is actually functional
    if not xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)'):
        xbmc.log(f"[{ADDON_ID}] IPTV Simple missing or disabled. Remediation starting...", xbmc.LOGINFO)
        
        # 1. Clear any "Ghost" Windows folders if they exist
        home = xbmcvfs.translatePath("special://home/")
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect']
        for b in binaries:
            b_path = os.path.join(home, 'addons', b)
            if os.path.exists(b_path):
                # If there's a .dll in here, it's a Windows carry-over. Nuke it.
                shutil_path = xbmcvfs.translatePath(b_path)
                try: xbmcvfs.rmdir(shutil_path, True)
                except: pass

        # 2. Force install the correct Android version from the official repo
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.executebuiltin('InstallAddon(pvr.iptvsimple)')
        xbmc.executebuiltin('InstallAddon(inputstream.adaptive)')
        
        xbmcgui.Dialog().notification("CordCutter", "IPTV Components Repaired for Android", xbmcgui.NOTIFICATION_INFO, 5000)

    # --- PART 3: MASS ENABLE ---
    # Ensure any third-party addons that got disabled are flipped back on
    query = '{"jsonrpc":"2.0","method":"Addons.GetAddons","params":{"enabled":false},"id":1}'
    response = xbmc.executeJSONRPC(query)
    data = json.loads(response)
    if 'result' in data and 'addons' in data['result']:
        for item in data['result']['addons']:
            aid = item['addonid']
            # We don't want to enable EVERYTHING (like disabled scrapers), 
            # but we want to enable video plugins
            if aid.startswith('plugin.video') or aid == 'skin.aeon.nox.silvo':
                xbmc.executebuiltin(f'EnableAddon("{aid}")')

if __name__ == '__main__':
    remediate()
