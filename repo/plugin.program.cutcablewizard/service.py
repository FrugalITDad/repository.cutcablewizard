import xbmc, xbmcgui, xbmcaddon, xbmcvfs, os, json, datetime, ssl, urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ADDON      = xbmcaddon.Addon()
HOME       = xbmcvfs.translatePath("special://home/")
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

MANIFEST_URL        = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
FIRSTRUN_FILE       = os.path.join(HOME, 'firstrun.txt')
INSTALLED_FILE      = os.path.join(HOME, 'installed_version.txt')
LAST_CHECK_FILE     = os.path.join(HOME, 'last_update_check.txt')
FIRSTRUN_STEPS_FILE = os.path.join(HOME, 'firstrun_steps.txt')

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


def enable_addon(addon_id):
    """Enables an addon via JSON-RPC."""
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": True},
        "id": 1
    }))
    xbmc.log(f"[CutCableWizard] Enabled addon: {addon_id}", xbmc.LOGINFO)


def disable_addon(addon_id):
    """Disables an addon via JSON-RPC so it no longer prompts on startup."""
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.SetAddonEnabled",
        "params": {"addonid": addon_id, "enabled": False},
        "id": 1
    }))
    xbmc.log(f"[CutCableWizard] Disabled addon: {addon_id}", xbmc.LOGINFO)


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


def is_addon_present(addon_id):
    """Returns True if the addon exists in Kodi regardless of enabled state."""
    result = xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Addons.GetAddonDetails",
        "params": {"addonid": addon_id, "properties": ["enabled"]},
        "id": 1
    }))
    try:
        data = json.loads(result)
        return 'error' not in data and 'addon' in data.get('result', {})
    except Exception:
        return False


def is_skin_busy(monitor):
    """Returns True while the skin is still loading or library is scanning."""
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


def wait_for_simkl_auth(monitor, step_label):
    """
    Simkl-specific auth wait.

    Simkl shows a device-code screen within its settings window.
    We wait for settings to close, detect any follow-on auth modal,
    then show a confirmation prompt so the user can complete the
    simkl.com/activate step in a browser before setup continues.
    """
    # Phase 1: wait for settings window to close
    xbmc.sleep(2000)
    while xbmc.getCondVisibility("Window.IsActive(addonsettings)"):
        if monitor.waitForAbort(1):
            return

    # Phase 2: poll briefly for any follow-on auth modal
    auth_appeared = False
    for _ in range(16):
        if monitor.abortRequested():
            return
        if xbmc.getCondVisibility("System.HasModalDialog(true)"):
            auth_appeared = True
            break
        xbmc.sleep(500)

    if auth_appeared:
        elapsed = 0
        while elapsed < 300:
            if not xbmc.getCondVisibility("System.HasModalDialog(true)"):
                break
            if monitor.waitForAbort(2):
                return
            elapsed += 2

    # Phase 3: confirmation — user controls when setup continues
    xbmcgui.Dialog().ok(
        step_label,
        "Simkl settings have closed.\n\n"
        "If you still need to authorize at [B]simkl.com/activate[/B] "
        "in your browser, do that now.\n\n"
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
# First Run Setup
# ---------------------------------------------------------------------------
def read_firstrun_steps():
    """
    Reads firstrun_steps.txt and returns a set of allowed step names,
    or None if the file does not exist (meaning run all steps).

    Step names used in run_first_time_setup():
      subtitles, weather, device_name, simkl, jellycon, iagl, iptv_sync, buffer
    """
    if not os.path.exists(FIRSTRUN_STEPS_FILE):
        return None
    try:
        with open(FIRSTRUN_STEPS_FILE, 'r') as f:
            steps = {s.strip() for s in f.read().strip().split(',') if s.strip()}
        xbmc.log(f"[CutCableWizard] firstrun_steps filter: {steps}", xbmc.LOGINFO)
        return steps if steps else None
    except Exception:
        return None


def run_first_time_setup(monitor):
    """
    Runs the interactive setup wizard.
    Called when firstrun.txt exists (written by install_build or Re-run Setup).
    The trigger file is deleted ONLY after full completion so a crash
    mid-setup re-triggers setup on the next Kodi boot.

    If firstrun_steps.txt exists, only the listed steps are shown.
    The step counter (X/Y) is computed from the active steps.
    """

    # ── Wait for Aeon Nox Silvo to finish building menu shortcuts ─────────
    xbmc.log("[CutCableWizard] First Run: waiting 45s for skin to settle.", xbmc.LOGINFO)
    if monitor.waitForAbort(FIRSTRUN_BOOT_DELAY):
        return

    if not os.path.exists(FIRSTRUN_FILE):
        return

    # ── Wait for any busy/loading states to clear ─────────────────────────
    while is_skin_busy(monitor):
        if monitor.waitForAbort(5):
            return

    # ── Wait for any addon auth prompts to clear ──────────────────────────
    AUTH_WAIT_CEILING = 600
    auth_wait_elapsed = 0
    while xbmc.getCondVisibility("System.HasModalDialog(true)"):
        if monitor.waitForAbort(2):
            return
        auth_wait_elapsed += 2
        if auth_wait_elapsed % 30 == 0:
            xbmc.log(
                f"[CutCableWizard] First Run: waiting for modal dialog to clear "
                f"({auth_wait_elapsed}s elapsed).", xbmc.LOGINFO
            )
        if auth_wait_elapsed >= AUTH_WAIT_CEILING:
            xbmc.log(
                "[CutCableWizard] First Run: modal dialog wait exceeded 10 minutes, "
                "proceeding anyway.", xbmc.LOGWARNING
            )
            break

    xbmc.executebuiltin('ReplaceWindow(10000)')
    dialog = xbmcgui.Dialog()

    # ── Determine which steps are active for this build ───────────────────
    # ALL_STEPS defines the canonical order — builds.json firstrun_steps
    # lists which of these to include per build.
    ALL_STEPS = ['subtitles', 'weather', 'device_name', 'simkl',
                 'jellycon', 'iagl', 'iptv_sync', 'buffer']

    allowed = read_firstrun_steps()
    active  = [s for s in ALL_STEPS if allowed is None or s in allowed]
    total   = len(active)

    def n(step_name):
        return active.index(step_name) + 1 if step_name in active else 0

    xbmc.log(f"[CutCableWizard] First Run active steps ({total}): {active}", xbmc.LOGINFO)

    # ── Step: Subtitles ───────────────────────────────────────────────────
    if 'subtitles' in active:
        if dialog.yesno(
            f"Setup ({n('subtitles')}/{total}): Subtitles",
            "Enable automatic subtitles?"
        ):
            set_kodi_setting("subtitles.enabled", True)

    # ── Step: Weather ─────────────────────────────────────────────────────
    # Multi Weather uses a zip code or city name — no GPS lookup.
    if 'weather' in active:
        if dialog.yesno(
            f"Setup ({n('weather')}/{total}): Weather",
            "Would you like to configure your weather location?"
        ):
            dialog.ok(
                "Weather Setup",
                "The Multi Weather settings will now open.\n\n"
                "Enter your [B]zip code[/B] or [B]city name[/B] in the "
                "location field, then close settings to continue."
            )
            xbmc.executebuiltin("Addon.OpenSettings(weather.multi)")
            wait_for_settings_dialog(monitor)

    # ── Step: Device Name ─────────────────────────────────────────────────
    if 'device_name' in active:
        dialog.ok(
            f"Setup ({n('device_name')}/{total}): Device Name",
            "Setting a unique device name helps identify this Kodi instance "
            "on your network.\n\n"
            "This is especially important if you plan to [B]cast media[/B] to "
            "this device or if you have [B]multiple Kodi devices[/B] in your "
            "home — each device should have its own name (e.g. Kodi-LivingRoom, "
            "Kodi-Bedroom) so they can be told apart.\n\n"
            "You will be prompted to enter a name on the next screen."
        )
        name = dialog.input(
            f"Setup ({n('device_name')}/{total}): Device Name",
            defaultt="Kodi-LivingRoom"
        ).strip()
        if name:
            set_kodi_setting("services.devicename", name)

    # ── Step: Simkl ───────────────────────────────────────────────────────
    # Enable the addon if accepted, disable if declined so it does not
    # prompt on every Kodi launch.
    if 'simkl' in active:
        if is_addon_present("script.simkl"):
            step_label = f"Setup ({n('simkl')}/{total}): Simkl"
            if dialog.yesno(
                step_label,
                "Would you like to authorize your Simkl account?\n\n"
                "Simkl tracks your watched movies, TV shows, and anime."
            ):
                enable_addon("script.simkl")
                xbmc.sleep(1000)
                xbmc.executebuiltin("Addon.OpenSettings(script.simkl)")
                wait_for_simkl_auth(monitor, step_label)
            else:
                disable_addon("script.simkl")
                xbmc.log("[CutCableWizard] Simkl declined — addon disabled.", xbmc.LOGINFO)
        else:
            xbmc.log("[CutCableWizard] script.simkl not found – skipping Simkl step.", xbmc.LOGINFO)

    # ── Step: JellyCon ───────────────────────────────────────────────────
    # Pro builds include JellyCon for Jellyfin server integration.
    # The user needs their Jellyfin server URL and credentials ready.
    if 'jellycon' in active:
        if is_addon_present("plugin.video.jellycon"):
            if dialog.yesno(
                f"Setup ({n('jellycon')}/{total}): JellyCon",
                "Would you like to connect to your Jellyfin server?\n\n"
                "Have your Jellyfin server address and login credentials ready."
            ):
                dialog.ok(
                    "JellyCon Setup",
                    "The JellyCon settings will now open.\n\n"
                    "Enter your [B]Jellyfin server address[/B] and sign in "
                    "with your credentials, then close settings to continue."
                )
                xbmc.executebuiltin("Addon.OpenSettings(plugin.video.jellycon)")
                wait_for_settings_dialog(monitor)
        else:
            xbmc.log("[CutCableWizard] plugin.video.jellycon not found – skipping JellyCon step.", xbmc.LOGINFO)

    # ── Step: IAGL Archive.org ────────────────────────────────────────────
    if 'iagl' in active:
        if is_addon_present("plugin.program.iagl"):
            if dialog.yesno(
                f"Setup ({n('iagl')}/{total}): IAGL Gaming",
                "Would you like to configure Archive.org for the IAGL Gaming addon?\n\n"
                "You will need your Archive.org account credentials."
            ):
                dialog.ok(
                    "IAGL - Archive.org Setup",
                    "The IAGL addon settings will now open.\n\n"
                    "Navigate to the [B]Downloading[/B] section on the left and "
                    "enter your Archive.org username and password, then close "
                    "settings to continue."
                )
                xbmc.executebuiltin("Addon.OpenSettings(plugin.program.iagl)")
                wait_for_settings_dialog(monitor)
        else:
            xbmc.log("[CutCableWizard] plugin.program.iagl not found – skipping IAGL step.", xbmc.LOGINFO)

    # ── Step: IPTV Guide Sync ─────────────────────────────────────────────
    # Enable the addon first in case it was disabled, then trigger the merge.
    if 'iptv_sync' in active:
        enable_addon("plugin.program.iptv.merge")
        xbmc.sleep(1000)
        xbmc.executebuiltin("RunPlugin(plugin://plugin.program.iptv.merge/?_=merge)")
        dp = xbmcgui.DialogProgress()
        dp.create(
            f"Setup ({n('iptv_sync')}/{total}): IPTV Guide Sync",
            "Syncing Live TV Guide..."
        )
        total_time = 60
        for i in range(total_time):
            if monitor.waitForAbort(1) or dp.iscanceled():
                break
            percent   = int((i / float(total_time)) * 100)
            remaining = total_time - i
            dp.update(percent, f"Finalizing IPTV Guide setup...\nTime remaining: {remaining}s")
        dp.close()

    # ── Step: EZ Maintenance+ Buffer Optimization ─────────────────────────
    if 'buffer' in active:
        if is_addon_present("script.ezmaintenanceplus"):
            if dialog.yesno(
                f"Setup ({n('buffer')}/{total}): Buffer Optimization",
                "Would you like to optimize the buffer size for this device?\n\n"
                "This is recommended for the best streaming performance."
            ):
                dialog.ok(
                    "Buffer Optimization",
                    "The EZ Maintenance+ menu will now open.\n\n"
                    "Select [B]ADVANCED SETTINGS (BUFFER SIZE)[/B] from the menu, "
                    "then choose [B]USE OPTIMAL[/B] to apply the best buffer "
                    "settings for this device.\n\n"
                    "Close the menu when done to complete setup."
                )
                xbmc.executebuiltin("RunAddon(script.ezmaintenanceplus)")
                xbmc.sleep(2000)
                while (xbmc.getCondVisibility("Window.IsActive(programs)") or
                       xbmc.getCondVisibility("System.HasModalDialog(true)")):
                    if monitor.waitForAbort(1):
                        break
        else:
            xbmc.log("[CutCableWizard] script.ezmaintenanceplus not found – skipping buffer step.", xbmc.LOGINFO)

    # ── Cleanup & finish ──────────────────────────────────────────────────
    for trigger in [FIRSTRUN_FILE, FIRSTRUN_STEPS_FILE]:
        try:
            if os.path.exists(trigger):
                os.remove(trigger)
        except Exception:
            pass

    xbmc.executebuiltin('SaveSceneSettings')
    dialog.ok(
        "Setup Complete",
        "Your CordCutter build is fully configured and ready to use!\n\n"
        "[B]Note:[/B] Your weather location will not appear until the next "
        "time you restart Kodi.\n\n"
        "Enjoy your new setup."
    )
    xbmc.log("[CutCableWizard] First Run setup complete.", xbmc.LOGINFO)


# ---------------------------------------------------------------------------
# Daily Update Check
# ---------------------------------------------------------------------------
def should_check_for_updates():
    """Returns True once per day, storing the date in last_update_check.txt."""
    today = datetime.date.today().isoformat()
    if os.path.exists(LAST_CHECK_FILE):
        try:
            with open(LAST_CHECK_FILE, 'r') as f:
                if f.read().strip() == today:
                    return False
        except Exception:
            pass
    try:
        with open(LAST_CHECK_FILE, 'w') as f:
            f.write(today)
    except Exception:
        pass
    return True


def run_update_check():
    """
    Fetches the manifest and prompts the user if a newer version of their
    installed build is available. Runs silently on any failure.
    """
    build_id, installed_version = get_installed_info()
    if not build_id or not installed_version:
        return

    manifest = get_json(MANIFEST_URL)
    if not manifest:
        xbmc.log("[CutCableWizard] Update check: could not reach manifest.", xbmc.LOGWARNING)
        return

    builds        = manifest.get('builds', [])
    current_build = next((b for b in builds if b['id'] == build_id), None)
    if not current_build:
        xbmc.log(f"[CutCableWizard] Update check: build '{build_id}' not found in manifest.", xbmc.LOGWARNING)
        return

    latest_version = current_build.get('version', '')
    if not latest_version or latest_version == installed_version:
        xbmc.log(f"[CutCableWizard] Update check: '{build_id}' is up to date (v{installed_version}).", xbmc.LOGINFO)
        return

    xbmc.log(f"[CutCableWizard] Update available: {build_id} v{installed_version} → v{latest_version}", xbmc.LOGINFO)

    if xbmcgui.Dialog().yesno(
        "Build Update Available",
        f"A new version of [B]{current_build['name']}[/B] is available!\n\n"
        f"  Installed : v{installed_version}\n"
        f"  Available : v{latest_version}\n\n"
        "Would you like to update now?\n"
        "(You can also update later via the CutCable Wizard.)"
    ):
        xbmc.executebuiltin("RunAddon(plugin.program.cutcablewizard)")


# ---------------------------------------------------------------------------
# Service Entry Point
# ---------------------------------------------------------------------------
def run_service():
    monitor = xbmc.Monitor()
    xbmc.log("[CutCableWizard] Service started.", xbmc.LOGINFO)

    if os.path.exists(FIRSTRUN_FILE):
        run_first_time_setup(monitor)
    elif should_check_for_updates():
        if not monitor.waitForAbort(15):
            run_update_check()

    while not monitor.waitForAbort(3600):
        pass

    xbmc.log("[CutCableWizard] Service stopped.", xbmc.LOGINFO)


if __name__ == '__main__':
    run_service()
