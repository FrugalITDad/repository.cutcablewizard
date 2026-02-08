import xbmcaddon, xbmcgui, xbmcvfs, xbmc
import urllib.request, os, json, ssl, zipfile, shutil, sqlite3

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
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
    db_path = xbmcvfs.translatePath("special://home/userdata/Database")
    db_files = [f for f in os.listdir(db_path) if f.startswith("Addons") and f.endswith(".db")]
    if not db_files: return
    latest_db = sorted(db_files)[-1]
    full_db_path = os.path.join(db_path, latest_db)
    try:
        conn = sqlite3.connect(full_db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE installed SET enabled = 1")
        conn.commit()
        conn.close()
    except: pass

def install_build(zip_path, build_id, version):
    dest = xbmcvfs.translatePath("special://home/")
    dp = xbmcgui.DialogProgress()
    dp.create(ADDON_NAME, "Extracting Build...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.infolist()
            for i, f in enumerate(files):
                if i % 100 == 0: dp.update(int(i*100/len(files)), f"Installing: {f.filename[:30]}")
                zf.extract(f, dest)
        dp.close()
        
        # --- ANDROID BINARY FIX ---
        # We trigger the install of the correct Android versions from the official repo
        xbmc.executebuiltin('InstallAddon(pvr.iptvsimple)')
        xbmc.executebuiltin('InstallAddon(inputstream.adaptive)')
        xbmc.executebuiltin('InstallAddon(inputstream.ffmpegdirect)')
        
        if not xbmcvfs.exists(ADDON_DATA): xbmcvfs.mkdirs(ADDON_DATA)
        with open(TRIGGER_FILE, "w") as f: f.write("active")
            
        force_enable_addons()
        ADDON.setSetting(f"ver_{build_id}", version)

        xbmcgui.Dialog().ok("Success", "Build Applied! PLEASE RESTART KODI NOW.")
        xbmc.sleep(2000)
        os._exit(1)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", str(e))

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: return
    builds = manifest["builds"]
    choice = xbmcgui.Dialog().select("Select Build", [f"{b['name']} (v{b['version']})" for b in builds])
    if choice != -1:
        sel = builds[choice]
        path = os.path.join(ADDON_DATA, "temp.zip")
        dp = xbmcgui.DialogProgress()
        dp.create(ADDON_NAME, "Downloading...")
        urllib.request.urlretrieve(sel['download_url'], path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs)))
        dp.close()
        install_build(path, sel['id'], sel['version'])

if __name__ == "__main__":
    main()
