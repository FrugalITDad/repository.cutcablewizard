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
temp files, the wizard's own settings (tokens) and guide data that is rebuilt on the device (EPG files,
channel thumbnails, guide caches - about 35-40% of a build). Older copies of the build are removed from
GitHub automatically. After publishing, fetch/pull in GitHub Desktop before editing the repo on your PC.

### From a PC

Use `tools/publish-build.ps1`. It uploads the zip to the **Builds** release and updates
`version`, `download_url`, `size_mb`, `sha256` and `changelog` for that build in `builds.json`.

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
4. Older copies of that build are removed from the release automatically. The file you just replaced is
   kept until your next publish of that build, so devices still holding the old link never hit a missing file.

Useful options: `-Changelog "Line one\n- Line two"`, `-ChangelogFile notes.txt`, `-DryRun` (preview only),
`-Push`, `-Yes` (skip the confirm prompt), `-Force` (replace a file with the same name or publish a
version that isn't newer).

The admin build doesn't use this: upload its zip to a new release in the private repo and put the
changelog in the release notes.

## Releasing a new version of the wizard add-on

```powershell
.\tools\package-wizard.ps1               # next patch version, e.g. 2.9.0 -> 2.9.1
.\tools\package-wizard.ps1 -Version 3.0.0
```

It updates the version in both `addon.xml` files, builds the add-on zip, regenerates `addons.xml.md5`
and keeps only the newest two wizard zips. Then commit and push. (Double-click won't work for this one;
run it from PowerShell with `powershell -ExecutionPolicy Bypass -File tools\package-wizard.ps1`.)
