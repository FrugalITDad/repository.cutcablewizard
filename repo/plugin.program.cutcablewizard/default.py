import xbmc, xbmcgui, xbmcaddon, os, sys, shutil, urllib.request, json, ssl, zipfile, xbmcvfs, re
from resources.lib import updates, buildtools, binaries

# ---------------------------------------------------------------------------
# Addon Constants
# ---------------------------------------------------------------------------
ADDON    = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
HOME     = xbmcvfs.translatePath("special://home/")

MANIFEST_URL        = "https://raw.githubusercontent.com/FrugalITDad/repository.cutcablewizard/main/builds.json"
ADDON_PROFILE       = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
ADMIN_CONFIG_FILE   = os.path.join(ADDON_PROFILE, 'admin_config.json')
FIRSTRUN_STEPS_FILE = os.path.join(HOME, 'firstrun_steps.txt')

BUILD_NAMES = {
    'cordcutter_base':         'CordCutter Base',
    'cordcutter_plus':         'CordCutter Plus',
    'cordcutter_plus_gaming':  'CordCutter Plus w Gaming',
    'cordcutter_pro':          'CordCutter Pro',
    'cordcutter_pro_gaming':   'CordCutter Pro w Gaming',
    'cordcutter_admin':        'CordCutter Admin',
}

HIDDEN_BUILD_IDS = {'cordcutter_fresh_start'}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_json(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Kodi-Wizard'})
        with urllib.request.urlopen(req, context=updates.ssl_context(), timeout=15) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        if updates.is_cert_error(e):
            xbmc.log(f"[CutCableWizard] Certificate check failed for {url}: {e}", xbmc.LOGWARNING)
        return None


def set_kodi_setting(setting, value):
    xbmc.executeJSONRPC(json.dumps({
        "jsonrpc": "2.0",
        "method": "Settings.SetSettingValue",
        "params": {"setting": setting, "value": value},
        "id": 1
    }))


def get_installed_info():
    path = os.path.join(HOME, 'installed_version.txt')
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, 'r') as f:
            data = f.read().strip()
        if '|' in data:
            build_id, version = data.split('|', 1)
            return build_id.strip(), version.strip()
        return None, data.strip()
    except Exception:
        return None, None


github_api_request = updates.github_api_request


def resolve_github_release_url(url, token):
    """
    For private GitHub release download URLs, resolves the direct API download
    URL for the asset. GitHub private release assets cannot be downloaded via
    the browser URL with a token — they must go through the API.

    Parses: https://github.com/OWNER/REPO/releases/download/TAG/FILENAME
    Returns: (api_asset_url, headers) or raises an exception on failure.
    """
    m = re.match(
        r'https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)',
        url
    )
    if not m:
        return url, {'Authorization': f'Bearer {token}', 'User-Agent': 'Kodi-Wizard',
                     'Accept': 'application/octet-stream'}

    owner, repo, tag, filename = m.groups()
    xbmc.log(f"[CutCableWizard] Resolving GitHub release asset: {owner}/{repo}@{tag}/{filename}", xbmc.LOGINFO)

    api_url      = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
    release_data = github_api_request(api_url, token)

    assets = release_data.get('assets', [])
    asset  = next((a for a in assets if a['name'] == filename), None)
    if not asset:
        asset_names = [a['name'] for a in assets]
        raise Exception(f"Asset '{filename}' not found in release '{tag}'.\n\n"
                        f"Available assets: {asset_names}")

    asset_api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{asset['id']}"
    dl_headers    = {
        'Authorization':        f'Bearer {token}',
        'Accept':               'application/octet-stream',
        'User-Agent':           'Kodi-Wizard',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    xbmc.log(f"[CutCableWizard] Resolved asset ID {asset['id']} — downloading via API.", xbmc.LOGINFO)
    return asset_api_url, dl_headers


# Admin credentials live in resources/lib/updates.py so the service can use them too.
load_admin_settings = updates.load_admin_settings
save_admin_settings = updates.save_admin_settings


# ---------------------------------------------------------------------------
# Fresh Start
# ---------------------------------------------------------------------------
FRESH_START_BUILD_ID = 'cordcutter_fresh_start'


def wipe_kodi():
    for folder in ['addons', 'userdata', 'packages', 'temp', 'Database']:
        path = os.path.join(HOME, folder)
        if os.path.exists(path):
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass
    for trigger in ['firstrun.txt', 'firstrun_steps.txt', 'installed_version.txt',
                    'last_update_check.txt', 'post_fresh_start.txt',
                    'firstrun_completed.json', 'post_update.json',
                    'update_snooze.json']:
        path = os.path.join(HOME, trigger)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def smart_fresh_start(manifest):
    if not xbmcgui.Dialog().yesno(
        "Fresh Start",
        "This will completely wipe your Kodi installation and restore a "
        "clean base with only the CutCableWizard installed.\n\n"
        "Are you absolutely sure?"
    ):
        return False

    if not manifest:
        xbmcgui.Dialog().ok(
            "Fresh Start Error",
            "Could not reach the build server to download the clean slate.\n\n"
            "Please check your internet connection and try again."
        )
        return False

    builds      = manifest.get('builds', [])
    fresh_build = next((b for b in builds if b['id'] == FRESH_START_BUILD_ID), None)
    if not fresh_build:
        xbmcgui.Dialog().ok(
            "Fresh Start Error",
            "The clean slate build was not found in the manifest.\n\n"
            "Please update the CutCableWizard to the latest version."
        )
        return False

    zip_path = os.path.join(HOME, "freshstart.zip")
    admin_config = None
    dp = xbmcgui.DialogProgress()
    dp.create("Fresh Start", "Downloading clean slate...")

    try:
        context = updates.ssl_context()
        with urllib.request.urlopen(fresh_build['download_url'], context=context) as r, \
             open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                count += len(chunk)
                if total > 0:
                    dp.update(int(count * 100 / total), "Downloading clean slate...")
                if dp.iscanceled():
                    dp.close()
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    return False

        dp.update(0, "Verifying download...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad_file = zf.testzip()
        if bad_file:
            raise zipfile.BadZipFile(f"Corrupt file in zip: {bad_file}")

        dp.update(0, "Wiping Kodi...")
        # Keep admin URL / tokens on devices that have them, and never let an
        # older wizard inside the clean-slate zip replace this one.
        admin_config = updates.backup_admin_config()
        updates.stash_running_wizard()
        wipe_kodi()

        dp.update(0, "Restoring clean slate...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files       = zf.infolist()
            total_files = len(files)
            for i, zipped_file in enumerate(files):
                if i % 100 == 0:
                    dp.update(
                        int(i * 100 / total_files),
                        f"Restoring: {zipped_file.filename[:35]}"
                    )
                zf.extract(zipped_file, HOME)

        updates.restore_admin_config(admin_config)
        updates.restore_newest_wizard()

        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return True

    except Exception as e:
        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        updates.restore_admin_config(admin_config)   # no-op if nothing was saved
        updates.restore_newest_wizard()
        xbmcgui.Dialog().ok(
            "Fresh Start Error",
            f"Fresh Start failed:\n\n{updates.CERT_ERROR_HELP if updates.is_cert_error(e) else str(e)}\n\n"
            "Your existing setup has not been modified."
        )
        return False


# ---------------------------------------------------------------------------
# Build Installation
# ---------------------------------------------------------------------------
def install_build(url, name, version, build_id,
                  firstrun_steps=None, extra_headers=None):
    zip_path = os.path.join(HOME, "build.zip")

    installed_id, installed_version = get_installed_info()

    # Same build, first run already finished -> this is an update. Carry the
    # user's First Run choices over instead of asking them all again.
    is_update = (installed_id == build_id
                 and not os.path.exists(updates.FIRSTRUN_FILE))
    carried, pending = ([], firstrun_steps)
    if is_update:
        carried, pending = updates.plan_same_build_update(build_id, firstrun_steps)

    if installed_id and installed_id != build_id:
        installed_name = BUILD_NAMES.get(installed_id, installed_id)
        if not xbmcgui.Dialog().yesno(
            "Replace Existing Build?",
            f"You currently have [B]{installed_name} v{installed_version}[/B] installed.\n\n"
            f"Installing [B]{name} v{version}[/B] will completely replace it and "
            f"wipe your current setup.\n\n"
            "Are you sure you want to continue?"
        ):
            return

    admin_config = None
    dp = xbmcgui.DialogProgress()
    dp.create("CordCutter Wizard", f"Downloading {name}...")

    try:
        context = updates.ssl_context()
        headers = {'User-Agent': 'Kodi-Wizard', 'Accept': 'application/octet-stream'}
        if extra_headers:
            headers.update(extra_headers)

        # Private GitHub release assets must be downloaded via the API rather
        # than the browser download URL — resolve to the API endpoint first.
        download_url = url
        bearer_token = (extra_headers or {}).get('Authorization', '').replace('Bearer ', '')
        if bearer_token and 'github.com' in url and '/releases/download/' in url:
            try:
                download_url, headers = resolve_github_release_url(url, bearer_token)
            except Exception as resolve_err:
                dp.close()
                xbmcgui.Dialog().ok(
                    "Download Error",
                    f"Could not locate the admin build asset.\n\n"
                    f"{updates.CERT_ERROR_HELP if updates.is_cert_error(resolve_err) else str(resolve_err)}"
                )
                return

        xbmc.log(f"[CutCableWizard] Downloading: {download_url[:80]}", xbmc.LOGINFO)
        try:
            req = urllib.request.Request(download_url, headers=headers)
            r   = urllib.request.urlopen(req, context=context)
        except urllib.error.HTTPError as http_err:
            dp.close()
            xbmc.log(f"[CutCableWizard] Download HTTP {http_err.code}: {url}", xbmc.LOGWARNING)
            xbmcgui.Dialog().ok(
                "Download Error",
                f"Could not download [B]{name}[/B].\n\n"
                f"HTTP Error {http_err.code}: {http_err.reason}\n\n"
                "For the Admin build verify:\n"
                "  - The Build URL is correct\n"
                "  - The Access Token has [B]Contents: Read[/B] permission\n"
                "  - The token has not expired"
            )
            return
        with r, open(zip_path, 'wb') as f:
            total = int(r.info().get('Content-Length', 0))
            count = 0
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                count += len(chunk)
                if total > 0:
                    dp.update(int(count * 100 / total), f"Downloading {name}...")
                if dp.iscanceled():
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    dp.close()
                    return

        dp.update(0, "Verifying download...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad_file = zf.testzip()
        if bad_file:
            raise zipfile.BadZipFile(f"Corrupt file in zip: {bad_file}")

        # Different kind of device than the Fire TV the build was made on?
        # Fetch the right Live TV / InputStream add-ons now, before wiping.
        dp.update(0, "Checking this device...")
        replacements, _ = binaries.prepare(zip_path, progress=lambda p, m: dp.update(p, m))
        skip_prefixes = tuple(f"addons/{a}/" for a in replacements)

        dp.update(0, "Preparing for installation...")
        admin_config = updates.backup_admin_config()
        updates.stash_running_wizard()
        keep_state   = None
        if is_update:
            dp.update(0, "Saving your current setup settings...")
            keep_state = updates.snapshot_user_settings(carried)
        wipe_kodi()

        dp.update(0, "Extracting build files...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            files       = zf.infolist()
            total_files = len(files)
            for i, zipped_file in enumerate(files):
                if i % 300 == 0:
                    dp.update(
                        int(i * 100 / total_files),
                        f"Extracting: {zipped_file.filename[:35]}"
                    )
                if skip_prefixes and zipped_file.filename.startswith(skip_prefixes):
                    continue            # replaced by this device's version below
                zf.extract(zipped_file, HOME)

        if replacements:
            dp.update(100, "Installing add-ons for this device...")
            binaries.install(replacements)

        with open(os.path.join(HOME, 'installed_version.txt'), 'w') as f:
            f.write(f"{build_id}|{version}")

        # Admin URL/token live under userdata, which wipe_kodi() removes.
        updates.restore_admin_config(admin_config)
        # Don't let an older wizard bundled in the build replace this one.
        updates.restore_newest_wizard()

        if keep_state is not None:
            dp.update(0, "Restoring your setup settings...")
            updates.restore_user_files(keep_state)
            updates.write_post_update(keep_state, name, version)
            updates.write_completed_firstrun(build_id, carried)

        if keep_state is None or pending:
            with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f:
                f.write("pending")
            steps_to_run = pending if keep_state is not None else firstrun_steps
            if steps_to_run:
                with open(FIRSTRUN_STEPS_FILE, 'w') as f:
                    f.write(','.join(steps_to_run))

        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)

        if keep_state is None:
            done_msg = ("[B]IMPORTANT:[/B] After you re-open Kodi, please wait "
                        "approximately 45 seconds for the First Run Setup to begin automatically.")
        elif pending:
            done_msg = ("Your previous setup choices will be kept. This version adds "
                        "new setup steps, so after you re-open Kodi please wait about "
                        "45 seconds and you will be asked only about those.")
        else:
            done_msg = ("Your previous setup choices (device name, weather, accounts, "
                        "buffer, etc.) will be kept - no First Run Setup needed.\n\n"
                        "After you re-open Kodi, wait about 45 seconds while your "
                        "settings are re-applied.")

        xbmcgui.Dialog().ok(
            "Update Complete" if keep_state is not None else "Install Complete",
            f"[B]{name} v{version}[/B] has been applied!\n\n"
            "Kodi must now FORCE CLOSE to load the new skin.\n\n" + done_msg
        )
        os._exit(1)

    except Exception as e:
        dp.close()
        if os.path.exists(zip_path):
            os.remove(zip_path)
        updates.restore_admin_config(admin_config)   # no-op if nothing was saved
        updates.restore_newest_wizard()
        binaries.cleanup()
        xbmcgui.Dialog().ok(
            "Installation Error",
            f"Installation failed:\n\n{updates.CERT_ERROR_HELP if updates.is_cert_error(e) else str(e)}\n\n"
            "Your existing setup has not been modified."
        )


# ---------------------------------------------------------------------------
# Re-run First Run Setup
# ---------------------------------------------------------------------------
def trigger_first_run_setup(manifest):
    build_id, version = get_installed_info()
    if not build_id:
        xbmcgui.Dialog().ok(
            "First Run Setup",
            "No build is currently installed.\n\n"
            "Please install a build first before running setup."
        )
        return

    firstrun_steps = None
    if manifest:
        builds        = manifest.get('builds', [])
        current_build = next((b for b in builds if b['id'] == build_id), None)
        if current_build:
            firstrun_steps = current_build.get('firstrun_steps')

    if build_id == 'cordcutter_admin' and not firstrun_steps:
        firstrun_steps = ['device_name', 'iptv_sync', 'buffer']

    build_name = BUILD_NAMES.get(build_id, build_id)
    if not xbmcgui.Dialog().yesno(
        "Re-run First Run Setup",
        f"This will restart Kodi and run the First Run Setup wizard for "
        f"[B]{build_name}[/B].\n\n"
        "Any settings previously configured during setup can be updated.\n\n"
        "Are you sure you want to continue?"
    ):
        return

    for addon_id in ['script.simkl', 'plugin.program.iptv.merge']:
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Addons.SetAddonEnabled",
            "params": {"addonid": addon_id, "enabled": False},
            "id": 1
        }))
        xbmc.log(f"[CutCableWizard] Pre-setup: disabled {addon_id}", xbmc.LOGINFO)

    try:
        with open(os.path.join(HOME, 'firstrun.txt'), 'w') as f:
            f.write("pending")
        if firstrun_steps:
            with open(FIRSTRUN_STEPS_FILE, 'w') as f:
                f.write(','.join(firstrun_steps))
        elif os.path.exists(FIRSTRUN_STEPS_FILE):
            os.remove(FIRSTRUN_STEPS_FILE)
    except Exception as e:
        xbmcgui.Dialog().ok("Error", f"Could not write setup trigger files:\n\n{str(e)}")
        return

    xbmcgui.Dialog().ok(
        "First Run Setup Scheduled",
        "Setup has been scheduled.\n\n"
        "Kodi will now close. After you reopen it, please wait approximately "
        "45 seconds for the First Run Setup wizard to appear."
    )
    os._exit(1)


# ---------------------------------------------------------------------------
# Admin Settings
# ---------------------------------------------------------------------------
def _mask(token):
    return f"****{token[-4:]}" if token and len(token) > 8 else ("Set" if token else "Not set")


def _input_token(heading):
    """Hidden input. Returns '' if left blank or cancelled."""
    return xbmcgui.Dialog().input(heading, option=xbmcgui.ALPHANUM_HIDE_INPUT).strip()


def configure_admin_settings():
    """Admin build URL + read token. Blank/Back keeps the current value."""
    data          = updates._read_config()
    current_url   = (data.get('admin_build_url') or '').strip()
    current_token = (data.get('admin_token') or '').strip()
    dialog        = xbmcgui.Dialog()

    choice = dialog.select("Admin Build Access", [
        f"Build URL: {current_url or 'Not set'}",
        f"Access Token: {_mask(current_token)}",
        "Clear URL and Token from this device",
    ])
    if choice == 0:
        url = dialog.input("Admin Build URL (leave blank to keep current)",
                           defaultt=current_url).strip()
        if url and url != current_url:
            updates.save_admin_settings(url, current_token)
            dialog.ok("Admin Settings Saved", "Build URL saved.")
    elif choice == 1:
        token = _input_token("Access Token (hidden - leave blank to keep current)")
        if token:
            updates.save_admin_settings(current_url, token)
            dialog.ok("Admin Settings Saved",
                      "Access Token saved." + ("" if current_url else
                      "\n\nAdd the Build URL too for the Admin build to appear."))
    elif choice == 2:
        if dialog.yesno("Clear Admin Access",
                        "Remove the Admin Build URL and Access Token from this device?"):
            updates.save_admin_settings('', '')
            dialog.ok("Admin Settings", "Admin URL and Token removed.")


def configure_publish_token():
    """Write-capable token used only by Package & Publish."""
    dialog  = xbmcgui.Dialog()
    current = updates.load_publish_token()
    choice  = dialog.select(f"Publishing Token: {_mask(current)}", [
        "Set / replace Publishing Token",
        "Remove Publishing Token from this device",
        "What permissions does it need?",
    ])
    if choice == 0:
        token = _input_token("Publishing Token (hidden)")
        if token:
            updates.set_config_value('publish_token', token)
            dialog.ok("Publishing Token", "Saved on this device only. It is never included in any build.")
    elif choice == 1:
        if dialog.yesno("Publishing Token", "Remove the Publishing Token from this device?"):
            updates.set_config_value('publish_token', None)
            dialog.ok("Publishing Token", "Removed.")
    elif choice == 2:
        dialog.textviewer("Publishing Token", (
            "Create a fine-grained personal access token on GitHub:\n"
            "Settings > Developer settings > Fine-grained tokens > Generate new token\n\n"
            "Repository access: Only select repositories\n"
            "  - repository.cutcablewizard\n"
            "  - your private admin build repository\n\n"
            "Permissions: Contents = Read and write (nothing else)\n"
            "Expiration: set one (e.g. 90 days) and replace it when it expires.\n\n"
            "Only add it on the device(s) you build on. It is stored in the wizard's "
            "settings file on this device, is never put in a build, and is kept through build installs and Fresh Start. Use Remove above to take it off a device."))


def admin_menu(manifest):
    admin_url, admin_token = load_admin_settings()
    publish_token          = updates.load_publish_token()
    options = [("Admin Build Access (URL & Token)", configure_admin_settings),
               (f"Publishing Token  [{_mask(publish_token)}]", configure_publish_token)]
    # Build packaging only on devices already set up for the admin build
    if admin_url and admin_token:
        options.append(("Package & Publish Build",
                        lambda: buildtools.package_and_publish(manifest)))
    choice = xbmcgui.Dialog().select("Admin Settings", [o[0] for o in options])
    if choice >= 0:
        options[choice][1]()


# ---------------------------------------------------------------------------
# Update Check
# ---------------------------------------------------------------------------
def find_available_update(manifest):
    """
    Returns (build_dict, installed_version, extra_headers) when a newer version
    of the installed build is published, otherwise None.

    The admin build is only checked when an admin URL + token are configured
    and the admin build is the one installed.
    """
    build_id, installed_version = get_installed_info()
    if not build_id or not installed_version:
        return None

    if build_id == updates.ADMIN_BUILD_ID:
        admin_build, admin_token = updates.get_admin_build(manifest)
        if not admin_build or not admin_build.get('version_known'):
            return None
        if updates.is_newer(admin_build['version'], installed_version):
            return admin_build, installed_version, {'Authorization': f'Bearer {admin_token}'}
        return None

    if not manifest:
        return None
    builds        = manifest.get('builds', [])
    current_build = next((b for b in builds if b['id'] == build_id), None)
    if not current_build:
        return None
    if updates.is_newer(current_build.get('version', ''), installed_version):
        return current_build, installed_version, None
    return None


def check_for_updates(manifest, ask=True):
    found = find_available_update(manifest)
    if not found:
        if not ask:
            xbmcgui.Dialog().ok("No Update Available",
                                "Your build is already up to date.")
        return

    build, installed_version, extra_headers = found
    if ask:
        # Respect "remind me later" for the automatic prompt; the menu heading
        # still shows the update and Install Build still offers it.
        if updates.is_snoozed(build['id'], build['version']):
            return
        if not updates.prompt_update(build['name'], installed_version,
                                     build['version'], build.get('changelog')):
            updates.ask_snooze(build['id'], build['version'])
            return

    install_build(
        url            = build['download_url'],
        name           = build['name'],
        version        = build['version'],
        build_id       = build['id'],
        firstrun_steps = build.get('firstrun_steps'),
        extra_headers  = extra_headers
    )


# ---------------------------------------------------------------------------
# Main Menu
# ---------------------------------------------------------------------------
def installed_build_status(manifest, admin_build=None):
    """
    One-line status for the main menu heading, e.g.
      Installed: CordCutter Plus v1.2.0
      Installed: CordCutter Plus v1.1.0  (v1.2.0 available)
      No build installed
    Uses data already fetched for the menu, so it adds no extra network calls.
    """
    build_id, version = get_installed_info()
    if not build_id:
        return "No build installed"

    latest = None
    if build_id == updates.ADMIN_BUILD_ID:
        name = updates.ADMIN_BUILD_NAME
        if admin_build and admin_build.get('version_known'):
            latest = admin_build['version']
    else:
        entry = next((b for b in (manifest or {}).get('builds', [])
                      if b.get('id') == build_id), None)
        name   = entry['name'] if entry else BUILD_NAMES.get(build_id, build_id)
        latest = entry.get('version') if entry else None

    status = f"Installed: {name} v{version}"
    if latest and updates.is_newer(latest, version):
        status += f"  [COLOR yellow](v{latest} available)[/COLOR]"
    return status


def main_menu():
    manifest = get_json(MANIFEST_URL)

    # Launched from the service's "Update Available" prompt:
    # plugin://plugin.program.cutcablewizard/?action=update
    if 'action=update' in ' '.join(sys.argv[1:]):
        check_for_updates(manifest, ask=False)
        return

    admin_build, admin_token = updates.get_admin_build(manifest)

    options = ["Install Build", "Fresh Start", "First Run Setup", "Admin Settings"]
    choice  = xbmcgui.Dialog().select(
        f"CutCable Wizard  -  {installed_build_status(manifest, admin_build)}", options)

    if choice == 0:
        if not manifest and not admin_build:
            xbmcgui.Dialog().ok(
                "Error",
                "Could not reach the build server.\n"
                "Please check your internet connection."
            )
            return

        builds = []
        if manifest:
            builds = [b for b in manifest.get('builds', [])
                      if b['id'] not in HIDDEN_BUILD_IDS
                      and not b.get('admin_only', False)]

        if admin_build:
            builds.append(admin_build)

        items = []
        for b in builds:
            size_mb  = b.get('size_mb', 0)
            size_str = f"{size_mb} MB" if size_mb else "N/A"
            item = xbmcgui.ListItem(
                label  = f"{b['name']}  |  v{b['version']}  |  {size_str}",
                label2 = b.get('description', '')
            )
            items.append(item)

        sel = xbmcgui.Dialog().select("CutCable Wizard", items, useDetails=True)
        if sel != -1:
            selected       = builds[sel]
            is_admin_build = selected['id'] == updates.ADMIN_BUILD_ID
            install_build(
                url            = selected['download_url'],
                name           = selected['name'],
                version        = selected['version'],
                build_id       = selected['id'],
                firstrun_steps = selected.get('firstrun_steps'),
                extra_headers  = {'Authorization': f'Bearer {admin_token}'}
                                 if is_admin_build else None
            )

    elif choice == 1:
        if smart_fresh_start(manifest):
            xbmcgui.Dialog().ok(
                "Fresh Start Complete",
                "Kodi has been wiped and restored to a clean slate.\n\n"
                "Unknown Sources are enabled and the CutCableWizard is ready.\n\n"
                "Kodi will now close. Reopen it when you are ready to install a build."
            )
            os._exit(1)

    elif choice == 2:
        trigger_first_run_setup(manifest)

    elif choice == 3:
        admin_menu(manifest)

    check_for_updates(manifest)


if __name__ == '__main__':
    main_menu()
