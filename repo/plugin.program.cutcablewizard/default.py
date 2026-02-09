import xbmc, xbmcaddon, xbmcgui, xbmcvfs
import urllib.request, os, json, ssl, zipfile, shutil, re, sqlite3

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
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(url, context=ctx) as r:
            return json.loads(r.read())
    except: return None

def patch_database():
    """Manually enables the Skin, Wizard, and Repo in the SQL database."""
    db_dir = xbmcvfs.translatePath("special://home/userdata/Database")
    db_files = [f for f in os.listdir(db_dir) if f.startswith("Addons") and f.endswith(".db")]
    if not db_files: return
    
    target_db = os.path.join(db_dir, sorted(db_files)[-1])
    try:
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        ids = [ADDON_ID, REPO_ID, 'skin.aeonnox.silvo']
        for a_id in ids:
            cursor.execute("UPDATE addon SET enabled = 1 WHERE addonID = ?", (a_id,))
        conn.commit()
        conn.close()
    except: pass

def install_build(url, build_id, version):
    path = os.path.join(ADDON_DATA, "temp.zip")
    dp = xbmcgui.DialogProgress()
    dp.create("CutCable Wizard", "Downloading Build...")
    
    # Download
    urllib.request.urlretrieve(url, path, lambda nb, bs, fs: dp.update(int(nb*bs*100/fs)))
    
    # Extract
    dp.update(0, "Extracting... Please wait.")
    home = xbmcvfs.translatePath("special://home/")
    with zipfile.ZipFile(path, "r") as zf:
        zf.extractall(home)
    
    # Force Skin in AdvancedSettings
    adv_file = xbmcvfs.translatePath("special://userdata/advancedsettings.xml")
    with open(adv_file, "w") as f:
        f.write('<advancedsettings><lookandfeel><skin>skin.aeonnox.silvo</skin></lookandfeel></advancedsettings>')

    # Database Patching
    patch_database()

    # Trigger File for Service
    if not os.path.exists(ADDON_DATA): os.makedirs(ADDON_DATA)
    with open(TRIGGER_FILE, "w") as f: f.write("active")
    ADDON.setSetting(f"ver_{build_id}", version)

    dp.close()
    xbmcgui.Dialog().ok("Complete", "Build Installed. Restart Kodi now!")
    os._exit(1)

def main():
    manifest = get_json(MANIFEST_URL)
    if not manifest: 
        xbmcgui.Dialog().ok("Error", "Could not reach server.")
        return
        
    builds = manifest.get("builds", [])
    names = [f"{b['name']} (v{b['version']})" for b in builds]
    choice = xbmcgui.Dialog().select("Select a Build", names)
    
    if choice != -1:
        sel = builds[choice]
        install_build(sel['download_url'], sel['id'], sel['version'])

if __name__ == '__main__':
    main()
