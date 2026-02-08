import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os

# --- INITIALIZATION ---
ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_setup():
    if not os.path.exists(TRIGGER_FILE):
        return

    xbmc.log("--- [CutCableWizard] Trigger File Found! Starting First Run Setup. ---", xbmc.LOGINFO)
    
    # Wait for the skin to settle
    xbmc.sleep(4000)
    dialog = xbmcgui.Dialog()
    
    # --- 1. DEVICE NAME ---
    name = dialog.input("Enter a name for this device (e.g. Living Room):", "", type=xbmcgui.INPUT_ALPHANUM)
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # --- 2. SUBTITLES ---
    subs = dialog.yesno("Subtitles", "Would you like to enable subtitles by default?")
    val = "true" if subs else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # --- 3. TRAKT CONFIGURATION ---
    if dialog.yesno("Trakt", "Would you like to authorize Trakt now?"):
        xbmc.sleep(1000) # Wait for dialog to close
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')
        
        # Wait until the user closes the Trakt window before moving on
        while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
            xbmc.sleep(1000)

    # --- 4. WEATHER (GISMETEO) ---
    if dialog.yesno("Weather", "Would you like to set your location for Gismeteo weather?"):
        xbmc.log("--- [CutCableWizard] Attempting to launch Gismeteo Settings ---", xbmc.LOGINFO)
        
        # Step A: Force Kodi to set Gismeteo as the active provider
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')
        
        # Step B: Give Kodi a second to update its internal registry
        xbmc.sleep(1500) 
        
        # Step C: Launch the settings specifically
        xbmc.executebuiltin('Addon.OpenSettings(weather.gismeteo)')
        
        # Wait for user to finish weather settings
        while xbmc.getCondVisibility('Window.IsActive(addonsettings)'):
            xbmc.sleep(1000)

    # --- 5. CLEANUP ---
    try:
        os.remove(TRIGGER_FILE)
    except:
        pass
    
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == "__main__":
    monitor = xbmc.Monitor()
    # 10 second delay for system stability on boot
    if not monitor.abortRequested():
        xbmc.sleep(10000)
        run_setup()
