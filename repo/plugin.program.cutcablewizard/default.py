import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil, sqlite3

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard' 
REPO_ID = 'repository.cutcablewizard'       
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt') 
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
USER_AGENT = "Kodi-CutCableWizard/1.4.7"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

def force_enable_addons():
    """Tells Kodi's GUI to enable specific addons via built-in commands."""
    critical_addons = [REPO_ID, ADDON_ID, 'skin.aeonnox.silvo', 'pvr.iptvsimple', 'plugin.video.iptvmerge']
    for a_id in critical_addons:
        # We use JSON-RPC and Builtin simultaneously to ensure it takes
        xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","params":{{"addonid":"{a_id}","enabled":true}},"id":1}}')
        xbmc.executebuiltin(f'EnableAddon("{a_id}")')

def install_build(zip_path, build_id, version):
    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, 'addons')
    userdata_path = os.path.join(home, 'userdata')
    
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting Build...")
    
    try:
        # 1. Extraction
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, f in enumerate(files):
                if i % 100 == 0: dp.update(int(i*100/len(files)), f"Installing: {f.filename[:30]}")
                zf.extract(f, home)
        
        # 2. Binary Purge
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_p = os.path.join(addons_path, b)
            if os.path.exists(b_p): shutil.rmtree(b_p, ignore_errors=True)

        # 3. THE MAGIC FIX: FORCE ENABLE WHILE WIZARD IS ALIVE
        dp.update(90, "Applying Android compatibility patch...")
        force_enable_addons()
        
        # 4. FORCE SKIN VIA GUISETTINGS OVERWRITE
        # This replaces the skin setting in the XML file directly
        gui_settings = os.path.join(userdata_path, 'guisettings.xml')
        if os.path.exists(gui_settings):
            with open(gui_settings, 'r') as f:
                content = f.read()
            # Find the skin line and replace it
            if '<setting id="lookandfeel.skin"' in content:
                import re
                content = re.sub(r'<setting id="lookandfeel.skin".*?>.*?</setting>', 
                                '<setting id="lookandfeel.skin">skin.aeonnox.silvo</setting>', content)
                with open(gui_settings, 'w') as f:
                    f.write(content)

        # 5. REFRESH AND FINALIZE
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.executebuiltin('UpdateLocalAddons')
        
        # Write trigger for the service as a secondary backup
        if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        ADDON.setSetting(f"ver_{build_id}", version)

        dp.close()
        xbmcgui.Dialog().ok("Complete", "Build Applied Successfully!\n\nKodi will close now. Please wait 10 seconds before relaunching.")
        xbmc.sleep(5000) 
        os._exit(1)
        
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    options = ["Install Build", "Smart Fresh Start"]
    choice = xbmcgui.Dialog().select(ADDON_NAME, options)
    # ... rest of main menu logic ...
