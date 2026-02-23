import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json, urllib.request, ssl

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')
VERSION_FILE = os.path.join(ADDON_DATA, 'local_version.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def wait_for_settings_close():
    monitor = xbmc.Monitor()
    xbmc.sleep(1000) 
    while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
        if monitor.waitForAbort(1): break

def run_first_run_setup():
    monitor = xbmc.Monitor()
    # Wait for the skin to settle (12s is safe for Firesticks)
    if monitor.waitForAbort(12): return 

    if not os.path.exists(TRIGGER_FILE): return

    dialog = xbmcgui.Dialog()

    # --- PART 1: THE QUESTIONS (FRONT-LOADED) ---
    # Subtitles
    if dialog.yesno("Setup: Subtitles", "Would you like subtitles to be on by default?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":true},"id":1}')
    else:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"subtitles.enabled","value":false},"id":1}')

    # Device Name
    device_name = dialog.input("Enter a unique name for this device", xbmc.getInfoLabel('System.FriendlyName'), type=xbmcgui.INPUT_ALPHANUM)
    if device_name:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % device_name)

    # Weather
    if dialog.yesno("Setup: Weather", "Configure weather location?"):
        dialog.ok("Weather Hint", "Do NOT use 'Current Location'.\nEnter city manually in the next screen.")
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        wait_for_settings_close()

    # Trakt
    if dialog.yesno("Setup: Trakt", "Configure Trakt?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        wait_for_settings_close()

    # --- PART 2: IPTV SYNC (WITH PROGRESS DIALOG) ---
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Finishing Setup...")
    
    # Setup Simple Client
    dp.update(25, "Configuring IPTV Player...")
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=setup_simple_client)')
    xbmc.sleep(3000) # Give the addon a moment to write settings

    # Run Merge
    dp.update(50, "Merging Live TV Channels...")
    xbmc.executebuiltin('RunPlugin(plugin.program.iptvmerge, ?mode=run)')
    xbmc.sleep(5000) # Wait for initial merge process

    # Refresh PVR
    dp.update(75, "Starting TV Guide Indexing...")
    xbmc.executebuiltin('UpdatePVR')
    
    # Clean up and finish
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    dp.update(100, "Setup Complete!")
    xbmc.sleep(2000)
    dp.close()
    
    dialog.notification("CordCutter", "All set! Enjoy your build.", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == '__main__':
    run_first_run_setup()