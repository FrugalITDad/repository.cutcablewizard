import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os

ADDON = xbmcaddon.Addon()

def run_setup():
    # Double check the flag
    if ADDON.getSetting("run_setup") != "true":
        return

    xbmc.log("CutCableWizard: First run flag detected. Starting setup.", xbmc.LOGINFO)
    dialog = xbmcgui.Dialog()
    
    # 1. Device Name
    name = dialog.input("Setup", "Device name (for Services screen):", type=xbmcgui.INPUT_ALPHANUM)
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # 2. Weather
    town = dialog.input("Setup", "Enter town for Gismeteo weather:", type=xbmcgui.INPUT_ALPHANUM)
    if town:
        gis_path = xbmcvfs.translatePath("special://userdata/addon_data/weather.gismeteo/settings.xml")
        gis_dir = os.path.dirname(gis_path)
        if not xbmcvfs.exists(gis_dir): xbmcvfs.mkdirs(gis_dir)
        xml = f'<settings version="2"><setting id="Location1">{town}</setting><setting id="Location1id">{town}</setting></settings>'
        with open(gis_path, "w") as f: f.write(xml)
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')

    # 3. Subtitles
    subs = dialog.yesno("Setup", "Enable subtitles by default?")
    val = "true" if subs else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # Clear flag and refresh
    ADDON.setSetting("run_setup", "false")
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Setup Complete!", xbmcgui.NOTIFICATION_INFO, 3000)

if __name__ == "__main__":
    # Monitor keeps the script alive until the GUI is ready
    monitor = xbmc.Monitor()
    
    # Wait for the system to settle (10 seconds is safest for Fire Sticks)
    if not monitor.abortRequested():
        xbmc.sleep(10000) 
        run_setup()
