# repository.cutcablewizard
Kodi repository for CutCableWizard and CordCutter builds

## Publishing a build update

### From the Fire TV (in the wizard)

Admin Settings > **Package & Publish Build** (shown only on devices with the Admin URL + Token set).
It zips this device's `addons` and `userdata`, uploads the zip and updates `builds.json` on GitHub.
For the Admin build it creates a new release in the private repo with the changelog as release notes.

Needs a **Publishing Token** (Admin Settings > Publishing Token): a fine-grained GitHub token limited to
this repo and the private admin repo, with **Contents: Read and write** only, and an expiry date.
Add it only on the device(s) you build on. It is never included in a build.

Public builds leave out the addon settings you tick (logins, weather location - your choice is
remembered per build) and reset the device name. Every build leaves out thumbnails, package caches,
temp files and the wizard's own settings (tokens). After publishing, fetch/pull in GitHub Desktop
before editing the repo on your PC.

### From a PC

Use `tools/publish-build.ps1`. It uploads the zip to the **Builds** release and updates
`version`, `download_url`, `size_mb` and `changelog` for that build in `builds.json`.

**One-time setup** (PowerShell):

```powershell
winget install --id GitHub.cli
gh auth login
```

**Each release:**

1. Name the zip like the current one with the new version, e.g. `cordcutter_plus-build-1.1.2.zip`.
2. Double-click `tools\publish-build.cmd` (or run it with `-Zip <path>`), then follow the prompts:
   drag the zip in, type the changelog (most important change first), confirm.
3. Commit and push `builds.json`, or add `-Push` to have the script do it.
4. After about 10 minutes, delete the previous zip from the release (the script prints the command).

Useful options: `-Changelog "Line one\n- Line two"`, `-ChangelogFile notes.txt`, `-DryRun` (preview only),
`-Push`, `-Yes` (skip the confirm prompt), `-Force` (replace a file with the same name or publish a
version that isn't newer).

The admin build doesn't use this: upload its zip to a new release in the private repo and put the
changelog in the release notes.
