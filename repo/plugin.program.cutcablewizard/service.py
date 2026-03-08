import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, json, datetime, ssl, urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ADDON      = xbmcaddon.Addon()
HOME       = xbmcvfs.translatePath("special://home/")
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

MANIFEST_URL          = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
FIRSTRUN_FILE         = os.path.join(HOME, 'firstrun.txt')
INSTALLED_FILE        = os.path.join(HOME, 'installed_version.txt')
LAST_CHECK_FILE       = os.path.join(HOME, 'last_update_check.txt')
POST_FRESH_START_FILE = os.path.join(HOME, 'post_fresh_start.txt')

# Addons that must be re-enabled after a fresh start wipes the addon database
PROTECTED_ADDONS = ['plugin.program.cutcablewizard', 'repository.cutcablewizard']

# Seconds to wait after boot before starting First Run Setup.
# Gives Aeon Nox Silvo time to finish building its menu shortcuts.
FIRSTRUN_BOOT_DELAY = 45


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------
def set_kodi_setting(setting, value):
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {"setting": setting, "value": value},
        "id": 1
    }))


def is_addon_installed(addon_id):
    """Returns True if the given addon is installed and enabled in Kodi."""
    result = xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.GetAddonDetails",
        "params": {"addonid": addon_id, "properties": ["enabled"]},
        "id": 1
    }))
    try:
        data = json.loads(result)
        return 'error' not in data and data.get('result', {}).get('addon', {}).get('enabled', False)
    except Exception:
        return False


def is_skin_busy(monitor):
    """
    Returns True while Kodi's skin is still loading or a modal is active.
    Also returns True if Kodi is scanning the library.
    """
    return (
        xbmc.getCondVisibility("Window.IsActive(busydialog)") or
        xbmc.getCondVisibility("Window.IsActive(10101)") or
        xbmc.getCondVisibility("Library.IsScanningVideo")
    )


def wait_for_settings_dialog(monitor):
    """Block until the addon settings dialog is dismissed."""
    xbmc.sleep(2000)
    while xbmc.getCondVisibility("Window.IsActive(addonsettings)"):
        if monitor.waitForAbort(1):
            break


def wait_for_trakt_auth(monitor):
    """
    Trakt-specific wait that handles three phases:

    Phase 1 - Settings window:
        Wait for the Trakt settings dialog to close. The user may close
        it without authorizing (fine), or Trakt may close it automatically
        when the user clicks Authorize.

    Phase 2 - Authorization window:
        After settings close, Trakt opens a custom device-code window.
        We use System.HasModalDialog to detect ANY modal appearing within
        8 seconds - this catches Trakt's auth window regardless of its ID.
        Checking specific window IDs is unreliable as Trakt uses a custom
        addon window that does not match standard Kodi dialog IDs.
        Once detected, we wait for it to fully clear before continuing.

    Phase 3 - Confirmation prompt:
        Trakt authorization requires visiting trakt.tv/activate in a browser.
        We show an OK prompt so the user controls when first-run continues.
    """
    # Phase 1: wait for settings window to close
    xbmc.sleep(2000)
    while xbmc.getCondVisibility("Window.IsActive(addonsettings)"):
        if monitor.waitForAbort(1):
            return

    # Phase 2a: poll for up to 8 seconds for Trakt's auth window to appear.
    # Short 500ms intervals so we react quickly once it opens.
    auth_appeared = False
    for _ in range(16):
        if monitor.waitForAbort(0):
            return
        if xbmc.getCondVisibility("System.HasModalDialog(true)"):
            auth_appeared = True
            break
        xbmc.sleep(500)

    # Phase 2b: auth window appeared - wait for it to fully close.
    # 5 minute timeout matches Trakt device-code expiry.
    if auth_appeared:
        AUTH_TIMEOUT = 300
        elapsed = 0
        while elapsed < AUTH_TIMEOUT:
            if not xbmc.getCondVisibility("System.HasModalDialog(true)"):
                break
            if monitor.waitForAbort(2):
                return
            elapsed += 2

    # Phase 3: show confirmation so the user controls when first-run continues.
    # Trakt requires opening trakt.tv/activate on another device - the user
    # needs time to complete that step before setup moves on.
    xbmcgui.Dialog().ok(
        "Setup (4/5): Trakt",
        "Trakt authorization window has closed.\n\n"
        "If you still need to authorize in your browser, do that now.\n\n"
        "Tap [B]OK[/B] when you are ready to continue setup."
    )


def get_json(url):
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard'})
        with urllib.request.urlopen(req, context=context, timeout=15) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def get_installed_info():
    """
    Returns (build_id, version) from installed_version.txt.
    File format: build_id|version
    Returns (None, None) when no recognised build is installed.
    """
    if not os.path.exists(INSTALLED_FILE):
        return None, None
    try:
        with open(INSTALLED_FILE, 'r') as f:
            data = f.read().strip()
        if '|' in data:
            build_id, version = data.split('|', 1)
            return build_id.strip(), version.strip()
    except Exception:
        pass
    return None, None


# ---------------------------------------------------------------------------
# Post Fresh Start  (runs on first boot after a fresh start wipe)
# ---------------------------------------------------------------------------
def enable_addon(addon_id):
    """Force-enable an addon via JSON-RPC."""
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": True},
        "id": 1
    }))


def run_post_fresh_start(monitor):
    """
    Called on the first Kodi boot after a fresh start wipe.
    At this point Kodi has rebuilt a clean addon database, so:
      1. Re-enable the wizard and its repository (wiped DB marked them disabled)
      2. Apply Unknown Sources ON
      3. Apply addon updates from Any Repositories
    Settings are applied HERE (not during the wipe) because guisettings.xml
    is freshly created by Kodi on this boot and JSON-RPC writes will persist.
    """
    xbmc.log("[CutCableWizard] Post Fresh Start: applying settings.", xbmc.LOGINFO)

    # Wait for Kodi to fully initialise before touching the addon DB
    if monitor.waitForAbort(15):
        return

    # ── Re-enable protected addons ────────────────────────────────────────
    for addon_id in PROTECTED_ADDONS:
        enable_addon(addon_id)
        xbmc.log(f"[CutCableWizard] Re-enabled: {addon_id}", xbmc.LOGINFO)

    # ── Apply system settings ─────────────────────────────────────────────
    # Unknown Sources ON
    set_kodi_setting('addons.unknownsources', True)
    # Addon updates from Any Repositories (0=off, 1=official only, 2=any)
    set_kodi_setting('general.addonupdates', 2)

    # ── Remove trigger ────────────────────────────────────────────────────
    try:
        os.remove(POST_FRESH_START_FILE)
    except Exception:
        pass

    xbmc.log("[CutCableWizard] Post Fresh Start complete.", xbmc.LOGINFO)


# ---------------------------------------------------------------------------
# First Run Setup
# ---------------------------------------------------------------------------
def run_first_time_setup(monitor):
    """
    Runs the interactive setup wizard.
    Called only when firstrun.txt exists (written by install_build).
    The trigger file is deleted ONLY after the full setup completes,
    so a crash mid-setup will re-trigger setup on the next Kodi boot.
    """

    # ── Wait for Aeon Nox Silvo to finish building menu shortcuts ─────────
    xbmc.log("[CutCableWizard] First Run: waiting 45s for skin to settle.", xbmc.LOGINFO)
    if monitor.waitForAbort(FIRSTRUN_BOOT_DELAY):
        return  # Kodi shutting down

    # Re-check trigger in case a force-close happened during the wait
    if not os.path.exists(FIRSTRUN_FILE):
        return

    # ── Wait for any busy/loading states to clear ─────────────────────────
    while is_skin_busy(monitor):
        if monitor.waitForAbort(5):
            return

    xbmc.executebuiltin('ReplaceWindow(10000)')
    dialog = xbmcgui.Dialog()

    # ── Step 1: Device Name ───────────────────────────────────────────────
    name = dialog.input("Setup (1/5): Device Name", defaultt="Kodi-FireTV").strip()
    if name:
        set_kodi_setting("services.devicename", name)

    # ── Step 2: Weather ───────────────────────────────────────────────────
    if dialog.yesno("Setup (2/5): Weather", "Would you like to configure your weather location?"):
        xbmc.executebuiltin("Addon.OpenSettings(weather.gismeteo)")
        wait_for_settings_dialog(monitor)

    # ── Step 3: Subtitles ─────────────────────────────────────────────────
    if dialog.yesno("Setup (3/5): Subtitles", "Enable automatic subtitles?"):
        set_kodi_setting("subtitles.enabled", True)

    # ── Step 4: Trakt (only offered if installed) ─────────────────────────
    if is_addon_installed("script.trakt"):
        if dialog.yesno("Setup (4/5): Trakt", "Would you like to authorize your Trakt account?"):
            xbmc.executebuiltin("Addon.OpenSettings(script.trakt)")
            wait_for_trakt_auth(monitor)  # Handles settings + auth window + confirm
    else:
        xbmc.log("[CutCableWizard] script.trakt not installed – skipping Trakt step.", xbmc.LOGINFO)

    # ── Step 5: IPTV Guide Sync ───────────────────────────────────────────
    xbmc.executebuiltin("RunPlugin(plugin://plugin.program.iptv.merge/?mode=run)")

    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Setup", "Syncing Live TV Guide...")

    total_time = 145
    for i in range(total_time):
        if monitor.waitForAbort(1) or dp.iscanceled():
            break
        percent    = int((i / float(total_time)) * 100)
        remaining  = total_time - i
        dp.update(percent, f"Finalizing IPTV Guide setup...\nTime remaining: {remaining}s")

    dp.close()

    # ── Cleanup & finish ──────────────────────────────────────────────────
    try:
        os.remove(FIRSTRUN_FILE)   # Only removed here – after full completion
    except Exception:
        pass

    xbmc.executebuiltin('SaveSceneSettings')
    dialog.ok(
        "Setup Complete",
        "Your CordCutter build is fully configured and ready to use!\n\n"
        "Enjoy your new setup."
    )
    xbmc.log("[CutCableWizard] First Run setup complete.", xbmc.LOGINFO)


# ---------------------------------------------------------------------------
# Daily Update Check
# ---------------------------------------------------------------------------
def should_check_for_updates():
    """
    Returns True once per day.
    Stores the last-checked date in last_update_check.txt.
    """
    today = datetime.date.today().isoformat()   # e.g. "2025-11-01"
    if os.path.exists(LAST_CHECK_FILE):
        try:
            with open(LAST_CHECK_FILE, 'r') as f:
                last = f.read().strip()
            if last == today:
                return False   # Already checked today
        except Exception:
            pass
    # Write today's date
    try:
        with open(LAST_CHECK_FILE, 'w') as f:
            f.write(today)
    except Exception:
        pass
    return True


def run_update_check():
    """
    Fetches the manifest and prompts the user if a newer version of their
    installed build is available. Runs silently if no build is installed
    or if the manifest cannot be reached.
    """
    build_id, installed_version = get_installed_info()
    if not build_id or not installed_version:
        return   # Nothing installed to compare

    manifest = get_json(MANIFEST_URL)
    if not manifest:
        xbmc.log("[CutCableWizard] Update check: could not reach manifest.", xbmc.LOGWARNING)
        return

    builds = manifest.get('builds', [])
    current_build = next((b for b in builds if b['id'] == build_id), None)
    if not current_build:
        xbmc.log(f"[CutCableWizard] Update check: build '{build_id}' not found in manifest.", xbmc.LOGWARNING)
        return

    latest_version = current_build.get('version', '')
    if not latest_version or latest_version == installed_version:
        xbmc.log(f"[CutCableWizard] Update check: '{build_id}' is up to date (v{installed_version}).", xbmc.LOGINFO)
        return

    xbmc.log(f"[CutCableWizard] Update available: {build_id} v{installed_version} → v{latest_version}", xbmc.LOGINFO)

    # Prompt the user
    if xbmcgui.Dialog().yesno(
        "Build Update Available",
        f"A new version of [B]{current_build['name']}[/B] is available!\n\n"
        f"  Installed : v{installed_version}\n"
        f"  Available : v{latest_version}\n\n"
        "Would you like to update now?\n"
        "(You can also update later via the CutCable Wizard.)"
    ):
        # Launch the wizard so install_build handles the full process
        xbmc.executebuiltin(f"RunAddon(plugin.program.cutcablewizard)")


# ---------------------------------------------------------------------------
# Service Entry Point
# ---------------------------------------------------------------------------
def run_service():
    monitor = xbmc.Monitor()
    xbmc.log("[CutCableWizard] Service started.", xbmc.LOGINFO)

    # ── Post Fresh Start ──────────────────────────────────────────────────
    # Runs on first boot after a manual fresh start wipe. Re-enables the
    # wizard/repo and applies Unknown Sources + Any Repositories settings.
    # Uses its own if (not elif) so that if firstrun.txt also exists somehow
    # it is still caught in the next block.
    if os.path.exists(POST_FRESH_START_FILE):
        run_post_fresh_start(monitor)

    # ── First Run setup (only when a build was just installed) ────────────
    # Separate if (not elif) so it always runs when firstrun.txt is present,
    # regardless of whether post_fresh_start also ran above.
    if os.path.exists(FIRSTRUN_FILE):
        run_first_time_setup(monitor)

    # ── Daily update check ────────────────────────────────────────────────
    # Only runs when neither setup trigger is present.
    elif not os.path.exists(POST_FRESH_START_FILE) and should_check_for_updates():
        # Give Kodi a moment to fully load before showing any dialog
        if not monitor.waitForAbort(15):
            run_update_check()

    # ── Keep the service alive ────────────────────────────────────────────
    # The service must stay running so Kodi doesn't mark the addon as broken.
    while not monitor.waitForAbort(3600):
        pass

    xbmc.log("[CutCableWizard] Service stopped.", xbmc.LOGINFO)


if __name__ == '__main__':
    run_service()