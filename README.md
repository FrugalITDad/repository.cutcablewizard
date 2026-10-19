# CutCableWizard & CordCutter Builds

CutCableWizard is a Kodi add-on that installs and maintains the **CordCutter** builds: ready-made
Kodi setups for Live TV, streaming, and (optionally) retro gaming, on Fire TV and Google TV devices
running **Kodi 21 (Omega)**.

- [Available builds](#available-builds)
- [1. Hardware recommendations](#1-hardware-recommendations)
- [2. Installing Kodi](#2-installing-kodi)
- [3. Kodi settings & media source](#3-kodi-settings--media-source)
- [4. Installing CutCableWizard & a build](#4-installing-cutcablewizard--a-build)
- [5. First Run Setup checklist](#5-first-run-setup-checklist)
- [Updates & the wizard menu](#updates--the-wizard-menu)
- [Suggested free apps](#suggested-free-apps)

---

## Available builds

Each build includes everything in the one above it.

| Build | What's included | Live TV | 3rd-party add-ons | Jellyfin | Retro gaming |
|---|---|:-:|:-:|:-:|:-:|
| **CordCutter Base** | Free, verified services only, with Live TV and automatic guide sync | ✅ | | | |
| **CordCutter Plus** | Base + 3rd-party add-ons for music, sports, kids, movies, TV and premium Live TV | ✅ | ✅ | | |
| **CordCutter Plus w Gaming** | Plus + retro gaming (IAGL, games from Archive.org) | ✅ | ✅ | | ✅ |
| **CordCutter Pro** | Plus + Jellyfin (JellyCon) | ✅ | ✅ | ✅ | |
| **CordCutter Pro w Gaming** | Pro + retro gaming (IAGL, games from Archive.org) | ✅ | ✅ | ✅ | ✅ |

**Choosing a build**

- **Gaming builds** need a 4K device with at least **2 GB of RAM**. Don't install them on lower-spec
  hardware (e.g. HD streaming sticks). You'll also need a free **[Archive.org account](https://archive.org/account/signup)**
  during First Run Setup so games can download.
- **Pro builds** are only useful if you have access to a **self-hosted Jellyfin server**. Otherwise choose Plus.
- **Xbox:** choose **Plus** or **Pro**. Kodi on Xbox can't run the game emulators, so the gaming builds
  aren't offered there.
- Current versions and download sizes are shown in the wizard when you pick a build.

---

## 1. Hardware recommendations

As Amazon moves Fire OS toward Vega OS (which restricts installing Android apps from outside the store),
**Google TV / Android TV devices such as the onn. lineup are the preferred choice for long-term
compatibility**. If Google TV hardware goes on sale below onn. prices, it's a solid choice too.

| Brand | Model | RAM | Status |
|---|---|:-:|---|
| onn. | 4K Pro (2024 model) | 3 GB | Preferred ✅ |
| onn. | 4K Pro (2026 model) | 3 GB | Preferred ✅ |
| onn. | 4K Plus | 2 GB | Approved ✅ |
| Google | Chromecast with Google TV 4K | 2 GB | Approved ✅ |
| Google | Google TV Streamer | 4 GB | Approved ✅ |
| Amazon | Fire TV Cube (2nd Gen) | 2 GB | Approved ✅ |
| Amazon | Fire TV Cube (3rd Gen) | 2 GB | Approved ✅ |
| Amazon | Fire TV Stick 4K Max (1st Gen) | 2 GB | Approved ✅ |
| Amazon | Fire TV Stick 4K Max (2nd Gen) | 2 GB | Approved ✅ |
| Amazon | Fire TV Stick 4K (2nd Gen) | 2 GB | Approved ✅ |

---

## 2. Installing Kodi

### Google TV (Play Store)

1. Go to the **Apps** tab on your Google TV home screen.
2. Select **Search for apps** and type **Kodi**.
3. Select **Kodi** in the results and click **Install**.

> The Play Store installs 64-bit Kodi. That's fine: when you install a build, the wizard automatically
> downloads the matching Live TV and streaming components for your device.

### Fire TV (Downloader app)

1. **Install Downloader:** on the Fire TV home screen go to **Find > Search**, type **Downloader**,
   select it and click **Install**.
2. **Enable Developer Options:** go to **Settings > Device & Software** (or **My Fire TV**) **> About**.
   Highlight your device name (or **Your TV**) and press the Select button on your remote **7 times**.
3. **Allow unknown apps:** go back to **Device & Software** (or **My Fire TV**) **> Developer Options >
   Install unknown apps** (or **Apps from Unknown Sources**) and turn it **ON** for **Downloader**.
4. **Download Kodi:** open Downloader, enter `kodi.tv/download/android` and select **ARMV7A (32-BIT)**.
   Click **Install** when prompted.
   *Tip: add this address to your Downloader favorites for future Kodi updates.*
5. **Delete the installer:** when installation finishes, return to Downloader and select **Delete** to
   free up storage.

---

## 3. Kodi settings & media source

### Enable add-on installs

1. Open Kodi and select **Settings** (gear icon, top left).
2. Select **System**.
3. At the bottom left, select the settings level (it says **Basic**) until it shows **Standard**
   (or **Advanced** / **Expert**).
4. Select **Add-ons** on the left.
5. Turn **Unknown sources** **ON** and select **Yes** on the warning.
6. Select **Update official add-ons from** and change it to **Any repositories**.

### Add the media source

1. Press **Back** to return to the main Settings menu.
2. Select **File manager > Add source**.
3. Select **\<None\>** and enter `https://kodi.wcouse3.workers.dev`
4. Under **Enter a name for this media source**, type `ccwiz` and select **OK**.

---

## 4. Installing CutCableWizard & a build

1. **Install the repository:** press **Back** to the main Settings menu and select **Add-ons >
   Install from zip file > ccwiz > repository.cutcablewizard-x.x.x.zip**. Wait for the
   *Add-on installed* notification (top right).
2. **Open the repository:** select **Install from repository > CutCableWizard Repository**.
3. **Install the wizard:** select **Program add-ons > CutCableWizard > Install**, and click **OK** to
   accept any required add-ons.
4. **Fresh Start (only if Kodi isn't a new install):** open **CutCableWizard** from **Program add-ons**,
   choose **Fresh Start** and follow the prompts. Kodi closes itself when it's done; reopen it.
   *Skip this step on a brand-new Kodi install.*
5. **Install a build:** open **CutCableWizard**, choose **Install Build**, and select the build you want
   (see [Available builds](#available-builds)). The wizard downloads, checks and unpacks it.
   If your internet drops during the download, it retries and carries on where it stopped.
6. **Restart Kodi:** select **OK** on the *Install Complete* message. Kodi closes itself;
   reopen it and go to [First Run Setup](#5-first-run-setup-checklist).

---

## 5. First Run Setup checklist

About **45 seconds** after Kodi reopens, First Run Setup starts automatically. Have these ready:

| Step | What you'll need | Builds |
|---|---|---|
| **Subtitles** | Whether you want subtitles on or off | All |
| **Sound** | Whether you listen through the TV's speakers or a soundbar / AV receiver | All |
| **Weather** | Your city or ZIP code for the home-screen weather | All |
| **Device name** | A unique name for this device, e.g. `Kodi-LivingRoom` | All |
| **Simkl** *(optional)* | Your [Simkl](https://simkl.com) account, to track what you've watched | Plus & Pro builds |
| **JellyCon** | Your Jellyfin server address and login | Pro builds |
| **Archive.org** | Your [Archive.org](https://archive.org/account/signup) username and password, so games can download | Gaming builds |
| **Live TV guide sync** | Nothing - runs automatically (about 90 seconds) | All |

The video buffer is sized automatically for your device's memory - there's nothing to set.

### Sound: TV speakers vs. soundbar or receiver

Builds start with standard stereo sound, which works everywhere. If you choose **Soundbar or AV
receiver** in the Sound step, the wizard sends surround sound as **Dolby Digital 5.1**, which almost
every soundbar, receiver and TV (HDMI ARC) connection supports.

- **No sound on a video?** Go to **Settings > System > Audio** and turn off **Allow passthrough**.
- **Have a receiver that supports more?** In the same screen you can also turn on
  **Dolby Digital Plus (E-AC3)**, **DTS**, **TrueHD** or **DTS-HD** passthrough. Only turn on formats
  your equipment supports - an unsupported one plays with no sound. *(Set the settings level at the
  bottom left to **Advanced** or **Expert** if these options aren't shown.)*

You can run First Run Setup again at any time from the wizard.

---

## Updates & the wizard menu

- **Update prompts:** when a new version of your build is published, Kodi asks if you'd like to update
  and shows what's new. Choose **Not Now** to be reminded later (tomorrow, 3 days, 1 or 2 weeks).
- **Your settings are kept:** updating to a new version of the *same* build keeps your First Run Setup
  choices (device name, weather, logins, sound), so you won't have to redo them. You'll only be
  asked about new setup steps.
- **Your favourites are kept:** favourites you've added stay when you update or switch builds. When
  switching builds, any favourite for an add-on the new build doesn't include is removed.
  (Fresh Start removes everything, including favourites.)
- **Wizard menu:** the top of the menu shows which build and version you have installed, and whether an
  update is available.

| Menu option | What it does |
|---|---|
| **Install Build** | Install or switch builds (switching to a different build replaces your setup) |
| **Fresh Start** | Wipes Kodi back to a clean slate with only the wizard installed |
| **First Run Setup** | Runs the setup steps again |
| **Admin Settings** | For the maintainer only - not needed for normal use |

---

## Suggested free apps

These apps work alongside Kodi on Fire TV and Google TV devices. Everything listed has free content
(some also sell an optional upgrade). Install them from your device's app store unless noted.

**Key:** 📺 = Live TV channels · 🎬 = On demand (watch any time)

> **Tip:** Your device has free live channels built in too: **Google TV Freeplay** (the *Live* tab on
> Google TV) and **Fire TV Channels** (the *Live* tab on Fire TV).

### Movies & TV

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **Tubi** | One of the largest free libraries of movies and shows | ✅ | ✅ |
| **Pluto TV** | Hundreds of themed channels: classic TV, movies, news | ✅ | ✅ |
| **The Roku Channel** | Free movies, shows and 100+ live channels (works on Fire TV and Google TV too) | ✅ | ✅ |
| **Plex** | Free movies, shows and live channels | ✅ | ✅ |
| **Xumo Play** | Free channels and movies, no sign-in | ✅ | ✅ |
| **Airy TV** | Live channels and movies | ✅ | ✅ |
| **Zone·ify** | Channels, movies, shows and a kids zone | ✅ | ✅ |
| **Fawesome** | Free movies and shows across many genres | ✅ | ✅ |
| **FilmRise** | Movies, classic TV, true crime and documentaries | | ✅ |
| **NASA+** | Space documentaries and live launch coverage | ✅ | ✅ |

### Free live TV services

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **Sling TV (Freestream)** | Free channel guide - no account needed | ✅ | ✅ |
| **Philo (free channels)** | Free channels with a free account, no credit card | ✅ | ✅ |
| **MyFree DIRECTV** | Free channels in the DIRECTV app with a free account, no credit card | ✅ | ✅ |
| **TCLtv+** | Free channels and movies *(made for TCL TVs; may not appear on other devices)* | ✅ | ✅ |

### Local news & weather

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **Local Now** | Local news, weather and free channels for your area | ✅ | ✅ |
| **Zeam** | Live local news and community programming | ✅ | ✅ |
| **Haystack News** | Local and national news channels and clips | ✅ | ✅ |
| **NewsON** | Live and recent newscasts from local stations | ✅ | ✅ |
| **FOX LOCAL** | Live news and weather from FOX stations | ✅ | ✅ |
| **WeatherNation** | 24/7 weather coverage and local forecasts | ✅ | |
| **PBS** | Your local PBS station live, plus PBS shows and documentaries | ✅ | ✅ |

### Sports

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **CBS Sports** | Free CBS Sports HQ and Golazo (soccer) channels, highlights | ✅ | ✅ |
| **Red Bull TV** | Extreme sports, motorsports, events and documentaries | ✅ | ✅ |
| **Your leagues' own apps** | Most leagues have free apps with highlights and news | | ✅ |

### Family friendly

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **PBS Kids** | PBS Kids shows plus the live PBS Kids channel | ✅ | ✅ |
| **HappyKids** | Thousands of kids' shows and movies | | ✅ |
| **Kidoodle.TV** | Kids' shows screened for younger viewers | | ✅ |
| **BYUtv** | Family shows, game shows and sports | ✅ | ✅ |
| **RedeemTV** | Ad-free Christian and family movies and series *(free account; donor-supported)* | | ✅ |
| **Angel Studios** | Faith and family films and series *(some titles free; most need a paid Guild membership)* | | ✅ |
| **iHeartRadio Family** | Kid-friendly music and radio stations *(Fire TV)* | — | — |

### Free with your library card

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **Kanopy** | Films, documentaries and Kanopy Kids | | ✅ |
| **Hoopla** | Movies, TV, music and audiobooks *(Fire TV app; on Google TV, cast from your phone)* | | ✅ |

### Music & radio

| App | What's on it |
|---|---|
| **Spotify** | Music and podcasts (free with ads) |
| **Pandora** | Personalized music stations |
| **iHeartRadio** | Live local radio stations, podcasts and playlists |
| **TuneIn Radio** | Radio stations from around the world |
| **Vevo** | Music video channels (📺) and videos on demand (🎬) |

### Spanish-language

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **ViX** | Free tier with Spanish-language channels, novelas, movies and news | ✅ | ✅ |

### YouTube

| App | What's on it | 📺 Live | 🎬 On demand |
|---|---|:-:|:-:|
| **YouTube** | The official app | ✅ | ✅ |
| **SmartTube** | Ad-free YouTube for TV. Install with Downloader **only from the official [GitHub page](https://github.com/yuliskov/SmartTube)** - copies from other sites may be unsafe | ✅ | ✅ |

### Tools

| App | What it does |
|---|---|
| **Kodi** | Runs the CordCutter builds |
| **Downloader** | Installs apps that aren't in the app store (e.g. Kodi on Fire TV, SmartTube) |
| **VLC** | Plays almost any video or audio file, from USB drives or your network |
| **LocalSend** | Sends files between your phone, computer and TV over Wi-Fi |
| **X-plore File Explorer** | File manager for USB drives, network shares and clearing out downloads |

*App availability and free content can change. This list was last checked in October 2026.*

---

## For the maintainer

### Publishing a build update

#### From the Fire TV (in the wizard)

Admin Settings > **Package & Publish Build** (shown only on devices with the Admin URL + Token set).
It zips this device's `addons` and `userdata`, uploads the zip and updates `builds.json` on GitHub.
For the Admin build it creates a new release in the private repo with the changelog as release notes.

Needs a **Publishing Token** (Admin Settings > Publishing Token): a fine-grained GitHub token limited to
this repo and the private admin repo, with **Contents: Read and write** only, and an expiry date.
Add it only on the device(s) you build on. It is never included in a build.

To change a build, install it with **Install Build > Build maintenance** (only offered on devices
with a Publishing Token): it installs the build exactly as published, without First Run Setup or
carrying over the previous build's settings. Make your changes, then Package & Publish. The changelog
is entered one line at a time (leave an entry empty to finish).

Public builds leave out the addon settings you tick (logins, weather location - your choice is
remembered per build), reset the device name, and run a privacy check: any login, password, key or
token in the included settings that differs from the add-on's own default is blanked in the zip
(it stays on the device). Every build also gets a fresh Kodi device ID. Every build leaves out thumbnails, package caches,
temp files, the wizard's own settings (tokens) and guide data that is rebuilt on the device (EPG files,
channel thumbnails, guide caches - about 35-40% of a build). Older copies of the build are removed from
GitHub automatically. After publishing, fetch/pull in GitHub Desktop before editing the repo on your PC.

#### From a PC

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

If you ever replace a build zip by hand on GitHub, update or remove its `sha256` in `builds.json`,
or installs of that build will fail the checksum check.

The admin build doesn't use this: upload its zip to a new release in the private repo and put the
changelog in the release notes (or use Package & Publish on the Fire TV).

### Releasing a new version of the wizard add-on

```powershell
.\tools\package-wizard.ps1               # next patch version, e.g. 2.9.0 -> 2.9.1
.\tools\package-wizard.ps1 -Version 3.0.0
```

It updates the version in both `addon.xml` files, builds the add-on zip, regenerates `addons.xml.md5`
and keeps only the newest two wizard zips. Then commit and push. (Double-click won't work for this one;
run it from PowerShell with `powershell -ExecutionPolicy Bypass -File tools\package-wizard.ps1`.)
