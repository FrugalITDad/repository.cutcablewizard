import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIG ---
ADDON       = xbmcaddon.Addon()
ADDON_ID    = 'plugin.program.cutcablewizard' 
REPO_ID     = 'repository.cutcablewizard'
ADDON_DATA  = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE= os.path.join(ADDON_DATA, 'trigger.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard/1.0'})
        with urllib.request.urlopen(req, context=ctx) as r:
            return json.loads(r.read())
    except: return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe setup but KEEP Wizard?", "This will delete all other builds."): 
            return False
    home = xbmcvfs.translatePath("special://home/")
    keep = [ADDON_ID, REPO_ID, 'packages', 'temp', 'backup', 'addon_data', 'Database']
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            if item in keep: continue
            full_path = os.path.join(path, item)
            try:
                if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                else: os.remove(full_path)
            except: pass
    return True

def install_build(url):
    if xbmcgui.Dialog().yesno("Build Install", "Perform Fresh Start first?", "Highly recommended for Fire Sticks."):
        smart_fresh_start(silent=True)

    zip_path = os.path.join(ADDON_DATA, "temp.zip")
    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
    dp = xbmcgui.DialogProgress()
    dp.create("Wizard", "Downloading...", "Please Wait")

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
                dp.update(int(count*100/total), "Downloading Build...", f"{int(count/1024/1024)}MB / {int(total/1024/1024)}MB")

        home = xbmcvfs.translatePath("special://home/")
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, file_info in enumerate(files):
                if i % 25 == 0: dp.update(int(i*100/len(files)), "Installing...", file_info.filename[:40])
                target = os.path.join(home, file_info.filename)
                if file_info.is_dir():
                    if not os.path.exists(target): os.makedirs(target)
                else:
                    parent = os.path.dirname(target)
                    if not os.path.exists(parent): os.makedirs(parent)
                    with open(target, "wb") as f_out: f_out.write(zf.read(file_info))

        with open(TRIGGER_FILE, "w") as f: f.write("active")
        
        # Override to force the skin on next boot
        adv = os.path.join(home, 'userdata', 'advancedsettings.xml')
        with open(adv, 'w') as f:
            f.write('<advancedsettings><lookandfeel><skin>skin.aeonnox.silvo</skin></lookandfeel></advancedsettings>')

        dp.close()
        xbmcgui.Dialog().ok("Complete", "Build Installed!", "Restart Kodi and WAIT for the Auto-Setup to begin.")
        os._exit(1)
    except Exception as e:
        dp.close()
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    options = ["Install Build", "Smart Fresh Start"]
    choice = xbmcgui.Dialog().select("CutCable Wizard", options)
    if choice == 0:
        manifest = get_json(MANIFEST_URL)
        if manifest:
            builds = manifest.get('builds', [])
            names = [b['name'] for b in builds]
            b_choice = xbmcgui.Dialog().select("Select Build", names)
            if b_choice != -1: install_build(builds[b_choice]['download_url'])
    elif choice == 1:
        if smart_fresh_start():
            xbmcgui.Dialog().ok("Done", "Kodi Cleaned. Restarting...")
            os._exit(1)

if __name__ == '__main__': main()
