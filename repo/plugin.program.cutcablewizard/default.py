import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'firstrun.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
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
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe setup but keep Wizard?"): return False
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
    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    home = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter", "Downloading Build...")
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
                if total > 0: dp.update(int(count*100/total), f"Downloading {name}...")

        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, file in enumerate(files):
                if i % 50 == 0: dp.update(int(i*100/len(files)), "Extracting...")
                target = os.path.join(home, file.filename)
                if not os.path.normpath(target).startswith(os.path.normpath(home)): continue
                if file.is_dir(): os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as f_out: f_out.write(zf.read(file))

        # CREATE TRIGGER FOR SERVICE.PY
        if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("setup_pending")

        dp.close()
        xbmcgui.Dialog().ok("Success", "Build Applied! Restart Kodi to begin setup.")
        os._exit(1)
    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    choice = xbmcgui.Dialog().select("CordCutter Wizard", ["Install Build", "Fresh Start"])
    if choice == 0:
        builds = manifest.get('builds', [])
        names = [f"{b['name']} (v{b['version']})" for b in builds]
        sel = xbmcgui.Dialog().select("Select Build", names)
        if sel != -1: install_build(builds[sel]['download_url'], builds[sel]['name'])
    elif choice == 1:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__': main()
