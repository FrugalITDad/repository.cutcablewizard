import xbmc, xbmcaddon, xbmcvfs, os, json, urllib.request, ssl

# --- CONFIGURATION ---
ADDON = xbmcaddon.Addon()
ADDON_ID = 'plugin.program.cutcablewizard'
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TRIGGER_FILE = os.path.join(ADDON_DATA, 'trigger.txt')
MANIFEST_URL = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"

def log(msg):
    xbmc.log(f"--- [Wizard Service] {msg}", xbmc.LOGINFO)

def get_json(url):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard-Service'})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read())
    except: return None

def check_for_updates():
    """Compares local version setting with GitHub manifest."""
    manifest = get_json(MANIFEST_URL)
    if not manifest: return

    for build in manifest.get("builds", []):
        build_id = build['id']
        online_version = str(build['version'])
        local_version = ADDON.getSetting(f"ver_{build_id}")

        # If local version is empty (new install) or lower than online
        if local_version and online_version > local_version:
            msg = f"A new version (v{online_version}) of {build['name']} is available!\nWould you like to open the Wizard and update now?"
            if xbmcgui.Dialog().yesno("Update Available", msg):
                xbmc.executebuiltin(f'RunAddon({ADDON_ID})')
            break # Only alert for the first matching build update found

def first_run_setup():
    log("New Build Detected! Starting Android Optimization...")
    
    # 1. Force Enable Binary Addons
    binaries = ['pvr.iptvsimple', 'inputstream.adaptive', 'inputstream.ffmpegdirect', 'inputstream.rtmp']
    for addon_id in binaries:
        query = {"jsonrpc": "2.0", "id": 1, "method": "Addons.SetAddonEnabled", "params": {"addonid": addon_id, "enabled": True}}
        xbmc.executeJSONRPC(json.dumps(query))
    
    xbmc.sleep(2000)

    # 2. Trigger IPTV Merge
    if xbmcvfs.exists(xbmcvfs.translatePath('special://home/addons/plugin.iptvmerge')):
        xbmc.executebuiltin('RunAddon(plugin.iptvmerge, "merge")')
    
    xbmc.executebuiltin('UpdatePVRByAddon(pvr.iptvsimple)')
    
    try:
        os.remove(TRIGGER_FILE)
        log("First run setup complete.")
    except: pass

if __name__ == '__main__':
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(10): exit()

    # Priority 1: Handle fresh install logic
    if os.path.exists(TRIGGER_FILE):
        first_run_setup()
    
    # Priority 2: Check for build updates
    check_for_updates()
