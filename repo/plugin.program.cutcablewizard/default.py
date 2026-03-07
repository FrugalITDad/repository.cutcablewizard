import xbmc, xbmcgui, xbmcvfs, os, shutil, urllib.request, json, ssl, zipfile

ADDON_ID     = 'plugin.program.cutcablewizard'
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
WHITELIST    = [ADDON_ID, 'packages', 'temp', 'Database']

def get_addon_data():
    return xbmcvfs.translatePath('special://profile/addon_data/' + ADDON_ID)

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard'})
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read().decode('utf-8'))
    except: return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe current setup? (Wizard & Repos saved)"): return False
    
    xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Settings.SetSettingValue","params":{"setting":"addons.unknownsources","value":true},"id":1}')
    home = xbmcvfs.translatePath("special://home/")
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            if item in WHITELIST or item.startswith('repository.'): continue
            if item == 'addon_data':
                ad_path = os.path.join(path, item)
                for ad_item in os.listdir(ad_path):
                    if ad_item != ADDON_ID:
                        shutil.rmtree(os.path.join(ad_path, ad_item), ignore_errors=True)
                continue
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
    xbmc.executebuiltin('SaveSceneSettings') 
    if not silent:
        xbmcgui.Dialog().ok("Fresh Start", "Cleanup Complete!")
        os._exit(1)
    return True

def install_build(url, name, version):
    addon_data = get_addon_data()
    if not xbmcvfs.exists(addon_data): xbmcvfs.mkdirs(addon_data)
    smart_fresh_start(silent=True)
    zip_path = os.path.join(addon_data, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", f"Downloading {name}...")
    try:
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
                if total > 0: dp.update(int(count*100/total), f"Downloading...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, file in enumerate(files):
                if i % 100 == 0: dp.update(int(i*100/len(files)), "Extracting Content...")
                target = os.path.join(home, file.filename)
                if file.is_dir(): os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as f_out: f_out.write(zf.read(file))
        with open(os.path.join(addon_data, 'firstrun.txt'), 'w') as f: f.write("setup_pending")
        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Applied! Restarting for Setup.")
        os._exit(1)
    except Exception as e:
        if dp: dp.close()
        xbmcgui.Dialog().ok("Error", f"Failed: {str(e)}")

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    choice = xbmcgui.Dialog().select("CordCutter Wizard", ["Install Build", "Fresh Start"])
    if choice == 0:
        builds = manifest.get('builds', [])
        names = [f"{b['name']} ({b['size_mb']} MB)" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1:
            install_build(builds[sel]['download_url'], builds[sel]['name'], builds[sel]['version'])
    elif choice == 1:
        smart_fresh_start()

if __name__ == '__main__': main()