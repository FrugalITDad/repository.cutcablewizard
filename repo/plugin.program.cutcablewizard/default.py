import xbmcaddon
import xbmcgui
import xbmc

ADDON = xbmcaddon.Addon(id="plugin.program.cutcablewizard")

BUILD_OPTIONS = [
    ("cordcutter_base",        "CordCutter Base\n\n[COLOR gray]Verified Free Services[/COLOR]"),
    ("cordcutter_pro",         "CordCutter Pro\n\n[COLOR gray]Base with third party addons[/COLOR]"), 
    ("cordcutter_plus",        "CordCutter Plus\n\n[COLOR gray]Pro with Jellyfin[/COLOR]"),
    ("cordcutter_basegaming",  "CordCutter Base Gaming\n\n[COLOR gray]Base with gaming[/COLOR]"),
    ("cordcutter_progaming",   "CordCutter Pro Gaming\n\n[COLOR gray]Pro with gaming[/COLOR]"),
    ("cordcutter_plusgaming",  "CordCutter Plus Gaming\n\n[COLOR gray]Plus with gaming[/COLOR]"),
    ("cordcutter_admin",       "CordCutter Admin\n\n[COLOR gray]Admin build only[/COLOR]"),
]

ADMIN_PASSWORD = "cordcutter2026"  # Change this to whatever you want

def check_admin_password():
    dialog = xbmcgui.Dialog()
    password = dialog.input("Admin build password:", type=xbmcgui.ALPHANUM_HIDE_INPUT)
    return password == ADMIN_PASSWORD

def select_build():
    labels = [label for (_id, label) in BUILD_OPTIONS]
    dialog = xbmcgui.Dialog()
    choice = dialog.select("Select CordCutter build", labels)
    if choice == -1:
        return None
    
    build_id = BUILD_OPTIONS[choice][0]
    
    # Password protect admin build
    if build_id == "cordcutter_admin":
        if not check_admin_password():
            dialog.ok("Access Denied", "Incorrect admin password.")
            return None
    
    return build_id

def main():
    build_id = select_build()
    if not build_id:
        return

    dialog = xbmcgui.Dialog()
    dialog.ok(
        "CutCableWizard",
        "You selected build:\n\n[COLOR lime]%s[/COLOR]\n\nNext step: implement download/apply logic."
        % BUILD_OPTIONS[[id for (id, label) in BUILD_OPTIONS].index(build_id)][1]
    )

if __name__ == "__main__":
    main()
