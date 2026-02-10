import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')

def run_first_run_setup():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(15): return # Wait for skin to load

    # --- AUTO UPDATE CHECK ---
    xbmc.executebuiltin('UpdateAddonRepos')
    xbmc.sleep(2000)
    xbmc.executebuiltin(f'InstallAddon({ADDON_ID})')

    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()
    
    # QUESTION 1: SUBTITLES
    if dialog.yesno("Setup: Subtitles", "Would you like subtitles to be on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
        # This mirrors 'Set as default for all media' in the DB logic
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    # QUESTION 2: DEVICE NAME
    device_name = dialog.input("HINT: Enter a unique name for this Fire Stick", "Kodi-FireStick", type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # QUESTION 3: WEATHER
    if dialog.yesno("Setup: Weather", "Would you like to configure the weather location?"):
        dialog.ok("Weather Hint", "HINT: Please do NOT turn on 'Current Location' in the next menu. Enter your city manually.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')

    # QUESTION 4: TRAKT
    if dialog.yesno("Setup: Trakt", "Would you like to configure the Trakt application?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')

    # FINALIZE
    try: os.remove(TRIGGER_FILE)
    except: pass
    dialog.notification("CordCutter", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    run_first_run_setup()
