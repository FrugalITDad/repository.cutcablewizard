import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIGURATION ---
ADDON       = xbmcaddon.Addon()
ADDON_ID    = ADDON.getAddonInfo('id')
ADDON_NAME  = ADDON.getAddonInfo('name')
ADDON_DATA  = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE= os.path.join(ADDON_DATA, 'firstrun.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

# Whitelist: What we DO NOT delete during a Fresh Start
WHITELIST = [ADDON_ID, 'repository.cutcablewizard', 'packages', 'temp']

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard/1.1'})
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except: return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe setup but keep this Wizard?"): return False
    
    home = xbmcvfs.translatePath("special://home/")
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            if item in WHITELIST or item == 'Database' or item == 'addon_data': continue
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
    return True

def install_build(url, name):
    if not smart_fresh_start(silent=True): return

    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")

    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", "Downloading Build...", "Please Wait")

    try:
        # 1. DOWNLOAD (Using download_url from your JSON)
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as r, open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(16384)
                if not chunk: break
                f.write(chunk)
                count += len(chunk)
                dp.update(int(count*100/total), "Downloading...", f"{int(count/1024/1024)}MB / {int(total/1024/1024)}MB")

        # 2. EXTRACTION (Android-Safe Loop)
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, file in enumerate(files):
                if i % 50 == 0: dp.update(int(i*100/len(files)), "Installing Files...", file.filename[:35])
                target = os.path.join(home, file.filename)
                if file.is_dir():
                    if not os.path.exists(target): os.makedirs(target, exist_ok=True)
                else:
                    parent = os.path.dirname(target)
                    if not os.path.exists(parent): os.makedirs(parent, exist_ok=True)
                    with open(target, "wb") as f_out: f_out.write(zf.read(file))

        # 3. BINARY SANITIZATION (Critical for Windows -> Android)
        # We delete the addon folders for these so Android reinstalls the correct version
        dp.update(98, "Cleaning up...", "Removing Windows binaries")
        binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
        for b in binaries:
            b_path = os.path.join(home, 'addons', b)
            if os.path.exists(b_path): shutil.rmtree(b_path, ignore_errors=True)

        # 4. ENABLE UNKNOWN SOURCES
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')

        with open(TRIGGER_FILE, "w") as f: f.write("active")
        
        dp.close()
        xbmcgui.Dialog().ok("Success", "CordCutter Base Installed!", "Kodi will now close.", "Relaunch to finish IPTV setup.")
        os._exit(1)

    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    
    options = ["Install Build", "Fresh Start Only"]
    choice = xbmcgui.Dialog().select("CordCutter Wizard", options)
    
    if choice == 0:
        builds = manifest.get('builds', [])
        # Matches your JSON labels
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1:
            # Passes download_url from your JSON
            install_build(builds[sel]['download_url'], builds[sel]['name'])
    elif choice == 1:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__':
    main()
