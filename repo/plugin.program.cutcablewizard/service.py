import xbmc, xbmcaddon, xbmcgui, xbmcvfs, os, json

ADDON = xbmcaddon.Addon()

def run_setup():
    if ADDON.getSetting("first_run_setup") != "true":
        return

    dialog = xbmcgui.Dialog()
    config = {}

    # 1. Subtitles
    config['subs'] = dialog.yesno("Setup", "Turn subtitles on by default?")
    val = "true" if config['subs'] else "false"
    xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"subtitles.enabled","value":{val}}},"id":1}}')

    # 2. Device Name
    name = dialog.input("Setup", "What is the name of this device?", type=xbmcgui.INPUT_ALPHANUM)
    if name:
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{{"setting":"services.devicename","value":"{name}"}},"id":1}}')

    # 3. Weather
    town = dialog.input("Setup", "Enter your town for weather:", type=xbmcgui.INPUT_ALPHANUM)
    if town:
        gis_path = xbmcvfs.translatePath("special://userdata/addon_data/weather.gismeteo/settings.xml")
        xml = f'<settings version="2"><setting id="Location1">{town}</setting><setting id="Location1id">{town}</setting></settings>'
        if not xbmcvfs.exists(os.path.dirname(gis_path)): xbmcvfs.mkdirs(os.path.dirname(gis_path))
        with open(gis_path, "w") as f: f.write(xml)
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"weather.addon","value":"weather.gismeteo"},"id":1}')

    # 4. Trakt
    if dialog.yesno("Setup", "Configure Trakt now?"):
        xbmc.executebuiltin('Addon.OpenSettings(script.trakt)')

    # Clear flag and refresh
    ADDON.setSetting("first_run_setup", "false")
    xbmc.executebuiltin('ReloadSkin()')
    dialog.notification("Wizard", "Personalization Complete!", xbmcgui.NOTIFICATION_INFO, 3000)

if __name__ == "__main__":
    # Give the skin 5 seconds to load before popping up questions
    xbmc.sleep(5000)
    run_setup()