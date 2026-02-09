import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil, re

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

def inject_advanced_settings(userdata_path):
    """Safely merges skin-force into an existing advancedsettings.xml."""
    adv_xml = os.path.join(userdata_path, 'advancedsettings.xml')
    skin_block = "<lookandfeel><skin>skin.aeonnox.silvo</skin></lookandfeel>"
    
    if os.path.exists(adv_xml):
        with open(adv_xml, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # If the skin setting is already there, don't double up
        if 'skin.aeonnox.silvo' in content:
            return
            
        # If lookandfeel exists, replace it; otherwise, insert before closing tag
        if '<lookandfeel>' in content:
            content = re.sub(r'<lookandfeel>.*?</lookandfeel>', skin_block, content, flags=re.DOTALL)
        else:
            content = content.replace('</advancedsettings>', f'  {skin_block}\n</advancedsettings>')
        
        with open(adv_xml, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        # File doesn't exist, create fresh
        with open(adv_xml, 'w', encoding='utf-8') as f:
            f.write(f'<advancedsettings>\n  {skin_block}\n</advancedsettings>')

def install_build(zip_path, build_id, version):
    home = xbmcvfs.translatePath("special://home/")
    addons_path = os.path.join(home, 'addons')
    userdata_path = os.path.join(home, 'userdata')
    
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting Build...")
    
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, f in enumerate(files):
                if i % 100 == 0: dp.update(int(i*100/len(files)), f"Installing: {f.filename[:30]}")
                zf.extract(f, home)
        
        # 1. THE MERGE FIX
        inject_advanced_settings(userdata_path)

        # 2. TRIGGER SETUP
        if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        
        # 3. PURGE AND FINALIZE
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_p = os.path.join(addons_path, b)
            if os.path.exists(b_p): shutil.rmtree(b_p, ignore_errors=True)

        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Applied!\n\nRESTART KODI NOW.")
        xbmc.sleep(1000)
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
        # Include your smart_fresh_start logic here
        pass

if __name__ == "__main__":
    main()
