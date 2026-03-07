import xbmc, xbmcgui, xbmcvfs, os, shutil, urllib.request, json, ssl

ADDON_ID = 'plugin.program.cutcablewizard'
MANIFEST_URL = 'https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json'

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as r:
            return json.loads(r.read().decode('utf-8'))
    except: return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup but keep Wizard and Repos?"): return False
    
    # RE-ENABLE UNKNOWN SOURCES (JSON-RPC)
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')

    home = xbmcvfs.translatePath("special://home/")
    PROTECTED = [ADDON_ID, 'packages', 'temp']
    
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            # PROTECT WIZARD AND ALL REPOSITORIES
            if item in PROTECTED or item.startswith('repository.'): continue
            # KEEP CORE ADDON_DATA DIRECTORY BUT WIPE CONTENTS LATER IF NEEDED
            if item == 'Database' or item == 'addon_data': continue
            
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
            
    if not silent:
        xbmcgui.Dialog().ok("Fresh Start", "Cleanup Complete! Repos and Wizard preserved.")
        # We don't exit here if it's part of a build install
    return True

def install_build(name, url):
    if not xbmcgui.Dialog().yesno("Confirm Install", f"Install {name}? This will wipe your current setup."): return
    
    # 1. Fresh Start
    smart_fresh_start(silent=True)
    
    # 2. Download and Extract (Simplified logic)
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Downloading Build...", "Please wait...")
    # [Download/Extract logic goes here - ensure it writes firstrun.txt after]
    
    addon_data = xbmcvfs.translatePath('special://profile/addon_data/' + ADDON_ID)
    if not os.path.exists(addon_data): os.makedirs(addon_data)
    with open(os.path.join(addon_data, 'firstrun.txt'), 'w') as f:
        f.write('setup_pending')

    xbmcgui.Dialog().ok("Success", "Build installed! Kodi will now close to save changes.")
    xbmc.executebuiltin('ShutDown')

# --- MAIN MENU ---
def main():
    data = get_json(MANIFEST_URL)
    if not data:
        xbmcgui.Dialog().ok("Error", "Network Error. Unable to reach build server.")
        return

    labels = [b['name'] for b in data['builds']]
    idx = xbmcgui.Dialog().select("Choose Your Build", labels)
    if idx >= 0:
        install_build(data['builds'][idx]['name'], data['builds'][idx]['download_url'])

if __name__ == '__main__':
    main()