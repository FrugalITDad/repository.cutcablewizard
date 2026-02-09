import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil, sqlite3, re

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

def smart_fresh_start():
    if not xbmcgui.Dialog().yesno("Smart Fresh Start", "Wipe everything but KEEP Wizard and Repo?"):
        return
    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, 'addons')
    userdata_path = os.path.join(home, 'userdata')
    keep_list = [REPO_ID, ADDON_ID, 'packages', 'temp']
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Cleaning...")
    try:
        for folder in os.listdir(addons_path):
            if folder not in keep_list:
                shutil.rmtree(os.path.join(addons_path, folder), ignore_errors=True)
        for folder in os.listdir(userdata_path):
            if folder not in ['addon_data', 'Database']:
                shutil.rmtree(os.path.join(userdata_path, folder), ignore_errors=True)
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')
        dp.close()
        xbmcgui.Dialog().ok("Done", "Cleaned. Restarting...")
        os._exit(1)
    except: dp.close()

def install_build(zip_path, build_id, version):
    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, 'addons')
    userdata_path = os.path.join(home, 'userdata')
    
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting...")
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, f in enumerate(files):
                if i % 100 == 0: dp.update(int(i*100/len(files)), f"Writing: {f.filename[:30]}")
                zf.extract(f, home)
        
        # 1. PURGE BINARIES
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_p = os.path.join(addons_path, b)
            if os.path.exists(b_p): shutil.rmtree(b_p, ignore_errors=True)

        # 2. PATCH SKIN MANUALLY (Regex)
        gui_xml = os.path.join(userdata_path, 'guisettings.xml')
        if os.path.exists(gui_xml):
            with open(gui_xml, 'r', encoding='utf-8') as f:
                xml_data = f.read()
            xml_data = re.sub(r'<setting id="lookandfeel.skin".*?>.*?</setting>', 
                              '<setting id="lookandfeel.skin">skin.aeonnox.silvo</setting>', xml_data)
            with open(gui_xml, 'w', encoding='utf-8') as f:
                f.write(xml_data)

        # 3. FORCE ENABLE CRITICAL ADDONS VIA JSON
        for a_id in [REPO_ID, ADDON_ID, 'skin.aeonnox.silvo']:
            xbmc.executeJSONRPC(f'{{"jsonrpc":"2.0","method":"Addons.SetAddonEnabled","params":{{"addonid":"{a_id}","enabled":true}},"id":1}}')

        # 4. FINALIZE
        if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        ADDON.setSetting(f"ver_{build_id}", version)
        
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.executebuiltin('UpdateLocalAddons')
        
        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Applied! Restarting Kodi...")
        xbmc.sleep(5000) 
        os._exit(1)
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    options = ["Install Build", "Smart Fresh Start"]
    choice = xbmcgui.Dialog().select(ADDON_NAME, options)
    if choice == 0:
        manifest = get_json(MANIFEST_URL)
        if not manifest: return
        builds = manifest["builds"]
        b_choice = xbmcgui.Dialog().select("Select Build", [f"{b['name']} (v{b['version']})" for b in builds])
        if b_choice != -1:
            sel = builds[b_choice]
            path = os.path.join(ADDON_DATA, "temp.zip")
            dp = xbmcgui.DialogProgress()
            dp.create(ADDON_NAME, "Downloading...")
            urllib.request.urlretrieve(sel['download_url'], path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs)))
            dp.close()
            install_build(path, sel['id'], sel['version'])
    elif choice == 1:
        smart_fresh_start()

if __name__ == "__main__":
    main()
