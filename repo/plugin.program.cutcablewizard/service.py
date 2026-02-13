import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def wait_for_settings_close():
    """Wait loop for non-blocking settings windows"""
    monitor = xbmc.Monitor()
    xbmc.sleep(1000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1):
            break
    xbmc.sleep(500)

def run_first_run_setup():
    monitor = xbmc.Monitor()
    # Wait for the skin (Aeon Nox Silvo) to fully initialize
    if monitor.waitForAbort(10): return 

    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    
    # 1. SUBTITLES
    if dialog.yesno("Setup: Subtitles", "Would you like subtitles to be on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    # 2. DEVICE NAME
    device_name = dialog.input("HINT: Enter a unique name for this Fire Stick", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # 3. WEATHER
    if dialog.yesno("Setup: Weather", "Would you like to configure the weather location?"):
        dialog.ok("Weather Hint", "HINT: Please do NOT turn on 'Current Location'.\nEnter city manually in the next screen.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    # 4. IPTV MERGE FIX (New Integration)
    # We trigger the IPTV Merge 'Setup Simple Client' feature to fix EPG/Channel paths
    dialog.notification("CordCutter", "Syncing Live TV Components...", xbmcgui.NOTIFICATION_INFO, 3000)
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    
    # Give IPTV Merge 5 seconds to write the new paths to the PVR database
    xbmc.sleep(5000)

    # 5. TRAKT
    if dialog.yesno("Setup: Trakt", "Would you like to configure the Trakt application?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')

    # FINAL CLEANUP
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    # Trigger a PVR database refresh to ensure the new paths are loaded
    xbmc.executebuiltin('UpdatePVR')
    
    dialog.notification("CordCutter", "Setup Complete! Enjoy your build.", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    run_first_run_setup()