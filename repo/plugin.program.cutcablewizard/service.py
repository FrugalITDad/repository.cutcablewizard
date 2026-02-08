import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os

# --- INITIALIZATION ---
ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_setup():
    # 1. Exit immediately if the trigger file is missing
    if not os.path.exists(TRIGGER_FILE):
        return

    xbmc.log("--- [CutCableWizard] Trigger File Found! Starting First Run Setup. ---", xbmc.LOGINFO)
    
    # 2. Short pause to let the Aeon Nox SiLVO skin finish its startup animations
    xbmc.sleep(3000)
    dialog = xbmcgui.Dialog()
    
    # --- 3. DEVICE NAME ---
    # Heading is the question, second argument is an empty string to keep the box clear
    name = dialog.input("Enter a name for this device (e.g. Living Room):", "", type=xbmcgui.INPUT_ALPHANUM)
    
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # --- 4. WEATHER (GISMETEO) ---
    town = dialog.input("Enter your nearest town for Weather:", "", type=xbmcgui.INPUT_ALPHANUM)
    
    if town:
        gis_path = xbmcvfs.translatePath("special://userdata/addon_data/weather.gismeteo/settings.xml")
        gis_dir = os.path.dirname(gis_path)
        
        # Ensure the addon_data folder exists before writing the file
        if not xbmcvfs.exists(gis_dir): 
            xbmcvfs.mkdirs(gis_dir)
        
        xml = f'<settings version="2"><setting id="Location1">{town}</setting><setting id="Location1id">{town}</setting></settings>'
        
        with open(gis_path, "w") as f: 
            f.write(xml)
        
        # Force Kodi to use Gismeteo as the active provider
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')

    # --- 5. SUBTITLES ---
    subs = dialog.yesno("Subtitles", "Would you like to enable subtitles by default?")
    val = "true" if subs else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # --- 6. CLEANUP ---
    # Delete the trigger file so this setup doesn't run again on the next boot
    try:
        os.remove(TRIGGER_FILE)
    except:
        pass
    
    # Refresh the UI to reflect changes (especially the device name in settings)
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

# --- SERVICE ENTRY POINT ---
if __name__ == "__main__":
    monitor = xbmc.Monitor()
    
    # Wait for the system to settle before checking the trigger
    # 10 seconds is the "sweet spot" for Fire Sticks and Android TV
    if not monitor.abortRequested():
        xbmc.sleep(10000)
        run_setup()
