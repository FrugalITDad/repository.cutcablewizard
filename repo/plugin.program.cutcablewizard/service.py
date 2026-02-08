import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os

# --- INITIALIZATION ---
ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_setup():
    # 1. Exit if the trigger file is missing
    if not os.path.exists(TRIGGER_FILE):
        return

    xbmc.log("--- [CutCableWizard] Trigger File Found! Starting First Run Setup. ---", xbmc.LOGINFO)
    
    # 2. Pause for system stability
    xbmc.sleep(4000)
    dialog = xbmcgui.Dialog()
    
    # --- 3. DEVICE NAME ---
    name = dialog.input("Enter a name for this device (e.g. Living Room):", "", type=xbmcgui.INPUT_ALPHANUM)
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # --- 4. SUBTITLES ---
    subs = dialog.yesno("Subtitles", "Would you like to enable subtitles by default?")
    val = "true" if subs else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # --- 5. TRAKT CONFIGURATION ---
    if dialog.yesno("Trakt", "Would you like to authorize Trakt now?"):
        xbmc.sleep(500) # GUI Breath
        # Using ActivateWindow is often more reliable than Addon.OpenSettings
        xbmc.executebuiltin('ActivateWindow(addonsettings, "script.trakt")')
        
        # We wait until the user closes the Trakt window before moving to weather
        while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
            xbmc.sleep(1000)

    # --- 6. WEATHER (GISMETEO) ---
    if dialog.yesno("Weather", "Would you like to set your location for Gismeteo weather?"):
        xbmc.sleep(500) # GUI Breath
        
        # Ensure Gismeteo is set as active first via JSON
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')
        
        # Force the settings window open
        xbmc.executebuiltin('ActivateWindow(addonsettings, "weather.gismeteo")')

    # --- 7. CLEANUP ---
    try:
        os.remove(TRIGGER_FILE)
    except:
        pass
    
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

# --- SERVICE ENTRY POINT ---
if __name__ == "__main__":
    monitor = xbmc.Monitor()
    
    # 10 second sleep to ensure Aeon Nox SiLVO is fully loaded
    if not monitor.abortRequested():
        xbmc.sleep(10000)
        run_setup()
