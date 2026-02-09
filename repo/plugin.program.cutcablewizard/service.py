import xbmc, xbmcaddon, xbmcvfs, os, xbmcgui, json

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')
SKIN_ID = 'skin.aeonnox.silvo'

def first_run_setup():
    """Interactive sequence for user customization."""
    dialog = xbmcgui.Dialog()
    
    # 1. DEVICE NAME
    if dialog.yesno("Setup: Device Name", "Would you like to give this device a name?", "Required for AirPlay/UPnP."):
        name = dialog.input("Enter Device Name", defaultt="Living Room Firestick")
        if name:
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"services.devicename","value":"%s"},"id":1}' % name)

    # 2. TRAKT
    if dialog.yesno("Setup: Trakt", "Do you want to authorize Trakt now?", "Syncs your movie and show progress."):
        # Opens the Trakt addon settings/authorization
        xbmc.executebuiltin('RunAddon(script.trakt)')
        dialog.ok("Trakt", "Please follow the on-screen prompts to authorize.")

    # 3. SUBTITLES
    if dialog.yesno("Setup: Subtitles", "Would you like to configure your preferred subtitle services?"):
        xbmc.executebuiltin('ActivateWindow(SubtitlesSettings)')
        dialog.ok("Subtitles", "Select your default services, then press back to continue setup.")

    # 4. WEATHER
    if dialog.yesno("Setup: Weather", "Would you like to set your location for the Weather?"):
        xbmc.executebuiltin('ActivateWindow(WeatherSettings)')

    dialog.ok("Wizard", "Setup Complete! Enjoy your build.")

def run_post_install():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(30): return # Wait 30s for Android to settle
    if not os.path.exists(TRIGGER_FILE): return

    # --- STEP 1: SKIN ENFORCEMENT ---
    xbmc.executebuiltin('UpdateLocalAddons')
    skin_applied = False
    for i in range(10):
        if xbmc.getSkinDir() == SKIN_ID: 
            skin_applied = True
            break
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"lookandfeel.skin","value":"%s"},"id":1}' % SKIN_ID)
        xbmc.executebuiltin('SendClick(11)') 
        xbmc.sleep(4000)

    # --- STEP 2: CLEANUP HANDCUFFS ---
    adv = xbmcvfs.translatePath("special://userdata/advancedsettings.xml")
    if os.path.exists(adv):
        try: os.remove(adv)
        except: pass

    # --- STEP 3: RUN SETUP IF SKIN IS READY ---
    if skin_applied:
        first_run_setup()

    # --- FINAL CLEANUP ---
    try: os.remove(TRIGGER_FILE)
    except: pass

if __name__ == '__main__':
    run_post_install()
