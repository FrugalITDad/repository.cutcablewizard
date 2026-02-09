import xbmc, xbmcaddon, xbmcvfs, os, re, xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')

def cleanup_advanced_settings():
    adv_file = xbmcvfs.translatePath('special://userdata/advancedsettings.xml')
    if os.path.exists(adv_file):
        with open(adv_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove only the lookandfeel block
        new_content = re.sub(r'<lookandfeel>.*?</lookandfeel>', '', content, flags=re.DOTALL)
        
        # If the file is now basically empty, delete it; otherwise, save it
        if '<advancedsettings>' in new_content and len(re.sub(r'<[^>]*>', '', new_content).strip()) == 0:
            os.remove(adv_file)
        else:
            with open(adv_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

def run_fix():
    # 1. CONFIRM SKIN (Clicks "Yes" on hidden prompt)
    xbmc.executebuiltin('SendClick(11)') 
    
    # 2. IPTV MERGE
    if os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.video.iptvmerge, "merge")')
    
    # 3. REMOVE ONLY THE SKIN FORCE (Keep the rest of AdvancedSettings)
    cleanup_advanced_settings()
        
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(15): exit()
    if os.path.exists(TRIGGER_FILE):
        run_fix()
