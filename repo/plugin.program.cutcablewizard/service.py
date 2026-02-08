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
    
    # 2. Short pause for skin/system stability
    xbmc.sleep(4000)
    dialog = xbmcgui.Dialog()
    
    # --- 3. DEVICE NAME ---
    # Heading = Question, Second Arg = Empty Default
    name = dialog.input("Enter a name for this device (e.g. Living Room):", "", type=xbmcgui.INPUT_ALPHANUM)
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # --- 4. SUBTITLES ---
    subs = dialog.yesno("Subtitles", "Would you like to enable subtitles by default?")
    val = "true" if subs else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # --- 5. TRAKT CONFIGURATION ---
    if dialog.yesno("Trakt", "Would you like to authorize Trakt now?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        # Small wait to allow the user to see the Trakt pin screen
        xbmc.sleep(2000)

    # --- 6. WEATHER (GISMETEO INTERFACE) ---
    if dialog.yesno("Weather", "Would you like to set your location for Gismeteo weather?"):
        # This opens the Gismeteo settings directly so the user can use the official search
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        
        # Ensure Gismeteo is set as the active provider
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')

    # --- 7. CLEANUP ---
    try:
        os.remove(TRIGGER_FILE)
    except:
        pass
    
    # Force the UI to update with new settings
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

# --- SERVICE ENTRY POINT ---
if __name__ == "__main__":
    monitor = xbmc.Monitor()
    
    # Wait 10 seconds for the Fire Stick services/keyboard to be ready
    if not monitor.abortRequested():
        xbmc.sleep(10000)
        run_setup()
