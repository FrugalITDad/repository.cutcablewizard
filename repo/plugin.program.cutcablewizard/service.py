import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def run_setup():
    if not os.path.exists(TRIGGER_FILE):
        return

    xbmc.sleep(5000) # Wait for skin
    dialog = xbmcgui.Dialog()
    
    # 1. Device Name (Heading fix)
    name = dialog.input("Enter a name for this device:", "", type=xbmcgui.INPUT_ALPHANUM)
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # 2. Subtitles
    subs = dialog.yesno("Subtitles", "Enable subtitles by default?")
    val = "true" if subs else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # 3. Trakt
    if dialog.yesno("Trakt", "Authorize Trakt now?"):
        xbmc.executebuiltin('ActivateWindow(addonsettings, "script.trakt")')
        while xbmc.getCondVisibility('Window.IsActive(addonsettings)'): xbmc.sleep(1000)

    # 4. Weather (Gismeteo)
    if dialog.yesno("Weather", "Set Gismeteo location now?"):
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')
        xbmc.sleep(1000)
        xbmc.executebuiltin('ActivateWindow(addonsettings, "weather.gismeteo")')
        while xbmc.getCondVisibility('Window.IsActive(addonsettings)'): xbmc.sleep(1000)

    # --- IPTV MERGE & PVR FIX ---
    xbmc.log("--- [Wizard] Running IPTV Merge for Android paths ---", xbmc.LOGINFO)
    # Force Enable the PVR first
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true},"id":1}')
    # Tell IPTV Merge to rebuild the playlist specifically for this device
    xbmc.executebuiltin('RunScript(script.iptv.merge, mode=merge)')
    xbmc.executebuiltin('PVR.TriggerFullReload')

    # Cleanup
    try: os.remove(TRIGGER_FILE)
    except: pass
    
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 5000)

if __name__ == "__main__":
    monitor = xbmc.Monitor()
    if not monitor.abortRequested():
        xbmc.sleep(12000) # Long sleep for Fire Sticks
        run_setup()
