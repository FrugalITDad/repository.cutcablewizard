import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil

# --- CONFIG ---
ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard'
REPO_ID = 'repository.cutcablewizard'
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as r:
            return json.loads(r.read())
    except: return None

def smart_fresh_start(silent=False):
    if not silent:
        if not xbmcgui.Dialog().yesno("Fresh Start", "Wipe all builds but KEEP Wizard and Repo?"):
            return False
    home = xbmcvfs.translatePath("special://home/")
    for folder in ['addons', 'userdata']:
        path = os.path.join(home, folder)
        if not os.path.exists(path): continue
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if item not in [ADDON_ID, REPO_ID, 'addon_data', 'Database', 'packages']:
                if os.path.isdir(item_path): shutil.rmtree(item_path, ignore_errors=True)
                else: os.remove(item_path)
    return True

def install_build(url, build_id, version):
    do_fresh = xbmcgui.Dialog().yesno("Build Install", "Perform Fresh Start first? (Recommended)")
    if do_fresh: smart_fresh_start(silent=True)

    path = os.path.join(ADDON_DATA, "temp.zip")
    dp = xbmcgui.DialogProgress()
    dp.create("CutCable Wizard", "Downloading Build...", "Please wait...")
    
    try:
        # DOWNLOAD WITH PROGRESS
        urllib.request.urlretrieve(url, path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs), "Downloading Build...", f"Transferred: {int(nb*bs/1024/1024)}MB / {int(fs/1024/1024)}MB"))
        
        # EXTRACT WITH PROGRESS
        home = xbmcvfs.translatePath("special://home/")
        with zipfile.ZipFile(path, "r") as zf:
            list = zf.infolist()
            total_files = len(list)
            for i, file in enumerate(list):
                # Update every 5 files to keep the UI smooth but fast
                if i % 5 == 0:
                    percent = int((i / total_files) * 100)
                    dp.update(percent, "Extracting Build...", f"File: {file.filename[:40]}")
                zf.extract(file, home)

        # FORCE CONFIGS
        adv_file = xbmcvfs.translatePath("special://userdata/advancedsettings.xml")
        with open(adv_file, "w") as f:
            f.write('<advancedsettings><lookandfeel><skin>skin.aeonnox.silvo</skin></lookandfeel></advancedsettings>')

        if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
        ADDON.setSetting(f"ver_{build_id}", version)

        dp.close()
        xbmcgui.Dialog().ok("Complete", "Build Installed! Restart Kodi and WAIT 30 seconds for the skin to flip.")
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
            builds = manifest.get("builds", [])
            names = [f"{b['name']} (v{b['version']})" for b in builds]
            b_choice = xbmcgui.Dialog().select("Select Build", names)
            if b_choice != -1: install_build(builds[b_choice]['download_url'], builds[b_choice]['id'], builds[b_choice]['version'])
    elif choice == 1:
        if smart_fresh_start(): os._exit(1)

if __name__ == '__main__': main()
