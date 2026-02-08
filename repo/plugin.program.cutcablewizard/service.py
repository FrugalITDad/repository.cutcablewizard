import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_setup():
    # If the file doesn't exist, stop immediately (saves resources)
    if not os.path.exists(TRIGGER_FILE):
        return

    xbmc.log("--- [CutCableWizard] Trigger File Found! Starting First Run Setup. ---", xbmc.LOGINFO)
    
    # Wait a moment for Skin to settle
    xbmc.sleep(3000)
    dialog = xbmcgui.Dialog()
    
    # 1. Device Name
    name = dialog.input("Setup", "Enter a name for this device:", type=xbmcgui.INPUT_ALPHANUM)
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # 2. Weather
    town = dialog.input("Setup", "Enter town for Weather:", type=xbmcgui.INPUT_ALPHANUM)
    if town:
        gis_path = xbmcvfs.translatePath("special://userdata/addon_data/weather.gismeteo/settings.xml")
        gis_dir = os.path.dirname(gis_path)
        if not xbmcvfs.exists(gis_dir): xbmcvfs.mkdirs(gis_dir)
        
        xml = f'<settings version="2"><setting id="Location1">{town}</setting><setting id="Location1id">{town}</setting></settings>'
        with open(gis_path, "w") as f: f.write(xml)
        
        # Set Gismeteo as active
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')

    # 3. Subtitles
    subs = dialog.yesno("Setup", "Enable subtitles by default?")
    val = "true" if subs else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # --- CLEANUP ---
    # Delete the trigger file so this doesn't run again
    try:
        os.remove(TRIGGER_FILE)
        xbmc.log("--- [CutCableWizard] Trigger file deleted. Setup complete. ---", xbmc.LOGINFO)
    except: pass
    
    # Refresh Skin to show new settings
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == "__main__":
    monitor = xbmc.Monitor()
    
    # Wait 10 seconds for Kodi to fully load before checking (Vital for Fire Sticks)
    if not monitor.abortRequested():
        xbmc.sleep(10000)
        run_setup()
