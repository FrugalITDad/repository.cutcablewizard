<#
.SYNOPSIS
    Publishes a CordCutter build update: uploads the zip to the GitHub "Builds"
    release and updates version, download_url, size_mb, sha256 and changelog in builds.json.

.DESCRIPTION
    Order of operations (nothing in builds.json changes unless the upload succeeds):
      1. Works out which build the zip belongs to from its file name
         (cordcutter_plus-build-1.1.2.zip -> cordcutter_plus, version 1.1.2)
      2. Checks the version is newer than the one in builds.json
      3. Asks for the changelog (unless -Changelog / -ChangelogFile is given)
      4. Shows a summary and asks to confirm
      5. Uploads the zip to the release and verifies the uploaded size
      6. Updates only that build's four fields in builds.json (formatting kept)
      7. With -Push: commits builds.json and pushes to GitHub

    Requires the GitHub CLI (gh), signed in once with:  gh auth login

.EXAMPLE
    .\tools\publish-build.ps1 -Zip "C:\Builds\cordcutter_plus-build-1.1.2.zip"

.EXAMPLE
    .\tools\publish-build.ps1 -Zip "C:\Builds\cordcutter_plus-build-1.1.2.zip" `
        -Changelog "Added Pluto TV to Live TV\n- Fixed guide sync on Fire TV" -Push
#>
[CmdletBinding()]
param(
    # Path to the build zip. Prompted for if omitted.
    [string]$Zip,
    # Build id in builds.json. Normally worked out from the zip name.
    [string]$BuildId,
    # Version to publish. Normally taken from the zip name.
    [string]$Version,
    # What's new. Use \n for a new line. Prompted for if omitted.
    [string]$Changelog,
    # Read the changelog from a text file instead.
    [string]$ChangelogFile,
    # Release tag the zips live under.
    [string]$Tag = 'Builds',
    # GitHub repository (owner/name).
    [string]$Repo = 'FrugalITDad/repository.cutcablewizard',
    # Commit builds.json and push to GitHub when done.
    [switch]$Push,
    # Skip the "Proceed?" confirmation.
    [switch]$Yes,
    # Allow re-uploading an existing file name or publishing a version that isn't newer.
    [switch]$Force,
    # Show what would happen without uploading or changing anything.
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$BuildsJson = Join-Path $RepoRoot 'builds.json'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Fail([string]$msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}
function Step([string]$msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Warn([string]$msg) { Write-Host "WARNING: $msg" -ForegroundColor Yellow }

# "cordcutter_plus-build-1.1.2.zip" -> prefix "cordcutter_plus-build", version "1.1.2"
# (same rule the wizard uses for the admin build)
function Split-AssetName([string]$name) {
    if ($name -match '^(.*?)[-_]?v?(\d+(?:\.\d+)+)\.zip$') {
        return @($Matches[1].ToLower(), $Matches[2])
    }
    return @(([IO.Path]::GetFileNameWithoutExtension($name)).ToLower(), $null)
}

# 1 if a > b, 0 if equal, -1 if a < b (same rule the wizard uses)
function Compare-Version([string]$a, [string]$b) {
    $pa = @([regex]::Matches([string]$a, '\d+') | ForEach-Object { [int]$_.Value })
    $pb = @([regex]::Matches([string]$b, '\d+') | ForEach-Object { [int]$_.Value })
    $n  = [Math]::Max($pa.Count, $pb.Count)
    for ($i = 0; $i -lt $n; $i++) {
        $x = 0; if ($i -lt $pa.Count) { $x = $pa[$i] }
        $y = 0; if ($i -lt $pb.Count) { $y = $pb[$i] }
        if ($x -gt $y) { return 1 }
        if ($x -lt $y) { return -1 }
    }
    return 0
}

function ConvertTo-JsonString([string]$s) {
    $s = $s -replace "`r`n", "`n" -replace "`r", "`n"
    $s = $s.Replace('\', '\\').Replace('"', '\"').Replace("`n", '\n').Replace("`t", '\t')
    $s = [regex]::Replace($s, '[\x00-\x1f]', { param($m) '\u{0:x4}' -f [int][char]$m.Value })
    return '"' + $s + '"'
}

# Finds the { ... } text of the build whose "id" matches, respecting JSON
# strings so braces inside a changelog can't confuse it. Returns @(start, length).
function Find-BuildBlock([string]$text, [string]$id) {
    $idMatch = [regex]::Match($text, '"id"\s*:\s*"' + [regex]::Escape($id) + '"')
    if (-not $idMatch.Success) { return $null }
    $depth = 0; $inStr = $false; $esc = $false; $start = -1
    for ($i = 0; $i -lt $text.Length; $i++) {
        $c = $text[$i]
        if ($inStr) {
            if ($esc) { $esc = $false }
            elseif ($c -eq '\') { $esc = $true }
            elseif ($c -eq '"') { $inStr = $false }
            continue
        }
        if ($c -eq '"') { $inStr = $true; continue }
        if ($c -eq '{') {
            $depth++
            if ($depth -eq 2) { $start = $i }
        }
        elseif ($c -eq '}') {
            if ($depth -eq 2 -and $start -le $idMatch.Index -and $i -gt $idMatch.Index) {
                return @($start, ($i - $start + 1))
            }
            $depth--
        }
    }
    return $null
}

# Replaces the value of "key" inside a build block with a raw JSON literal.
function Set-JsonField([string]$block, [string]$key, [string]$raw) {
    $pattern = '("' + [regex]::Escape($key) + '"\s*:\s*)("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?|true|false|null)'
    $re = New-Object System.Text.RegularExpressions.Regex $pattern
    if (-not $re.IsMatch($block)) { return $null }
    $evaluator = { param($m) $m.Groups[1].Value + $raw }.GetNewClosure()
    return $re.Replace($block, $evaluator, 1)
}

# Adds "key": raw right after the "version" field (used if a build has no changelog yet).
function Add-JsonFieldAfterVersion([string]$block, [string]$key, [string]$raw, [string]$nl) {
    $m = [regex]::Match($block, '(?m)^([ \t]*)"version"\s*:\s*"(?:[^"\\]|\\.)*"')
    if (-not $m.Success) { return $null }
    $insert = ',' + $nl + $m.Groups[1].Value + '"' + $key + '": ' + $raw
    return $block.Insert($m.Index + $m.Length, $insert)
}

function Invoke-Gh([string[]]$ghArgs) {
    # Windows PowerShell 5.1 turns captured stderr into terminating errors when
    # ErrorActionPreference is Stop, and gh writes normal status text to stderr.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out  = & gh @ghArgs 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    # Keep stdout (data) apart from stderr (messages such as gh's update notice)
    $stdout = @($out | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })
    $stderr = @($out | Where-Object { $_ -is    [System.Management.Automation.ErrorRecord] })
    $text   = ($stdout | ForEach-Object { "$_" }) -join "`n"
    $msgs   = ($stderr | ForEach-Object { "$_" }) -join "`n"
    if ($code -ne 0 -and $msgs) { $text = ($text + "`n" + $msgs).Trim() }
    return @{ Code = $code; Out = $text }
}

function Get-ReleaseAssets {
    $r = Invoke-Gh @('release', 'view', $Tag, '--repo', $Repo, '--json', 'assets,isDraft')
    if ($r.Code -ne 0) { Fail "Could not read release '$Tag' in $Repo.`n$($r.Out)" }
    return ($r.Out | ConvertFrom-Json)
}

# ---------------------------------------------------------------------------
# 1. Pre-flight checks
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "CordCutter build publisher" -ForegroundColor Green
Write-Host "Repo: $Repo   Release tag: $Tag"
Write-Host ""

if (-not (Test-Path $BuildsJson)) { Fail "builds.json not found at $BuildsJson" }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Fail ("The GitHub CLI (gh) is not installed.`n" +
          "Install it with:  winget install --id GitHub.cli`n" +
          "Then sign in once with:  gh auth login")
}
$auth = Invoke-Gh @('auth', 'status')
if ($auth.Code -ne 0) { Fail "The GitHub CLI is not signed in. Run:  gh auth login" }

$git = Get-Command git -ErrorAction SilentlyContinue
if ($Push -and -not $git) {
    Fail "git is not on PATH, so -Push can't be used. Run without -Push and commit/push with GitHub Desktop."
}
if ($Push -and -not $DryRun) {
    Step "Pulling latest changes so the push won't be rejected"
    & git -C $RepoRoot pull --ff-only
    if ($LASTEXITCODE -ne 0) { Fail "git pull failed. Sync the repo (e.g. in GitHub Desktop) and try again." }
}

# ---------------------------------------------------------------------------
# 2. Zip, build and version
# ---------------------------------------------------------------------------
if (-not $Zip) { $Zip = Read-Host "Path to the build zip (you can drag the file into this window)" }
$Zip = $Zip.Trim().Trim('"').Trim("'")
if (-not (Test-Path -LiteralPath $Zip -PathType Leaf)) { Fail "Zip not found: $Zip" }
$zipItem  = Get-Item -LiteralPath $Zip
$zipName  = $zipItem.Name
if ($zipName -notmatch '\.zip$') { Fail "$zipName is not a .zip file." }
$sizeMb   = [int][Math]::Round($zipItem.Length / 1MB)
$sha256   = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipItem.FullName).Hash.ToLower()
$nameParts = Split-AssetName $zipName
$zipPrefix = $nameParts[0]; $zipVersion = $nameParts[1]

$manifestText = [IO.File]::ReadAllText($BuildsJson)
try { $manifest = $manifestText | ConvertFrom-Json } catch { Fail "builds.json is not valid JSON: $_" }
$builds = @($manifest.builds)

if ($BuildId) {
    $build = $builds | Where-Object { $_.id -eq $BuildId } | Select-Object -First 1
    if (-not $build) { Fail "No build with id '$BuildId' in builds.json. Ids: $(($builds | ForEach-Object id) -join ', ')" }
} else {
    # Match the zip to the build whose current file has the same name pattern
    $found = @($builds | Where-Object {
        $current = ($_.download_url -split '/')[-1]
        (Split-AssetName $current)[0] -eq $zipPrefix
    })
    if ($found.Count -eq 0) {
        Fail ("Couldn't tell which build '$zipName' belongs to.`n" +
              "Name it like the current file (e.g. cordcutter_plus-build-1.1.2.zip) or pass -BuildId.`n" +
              "Ids: $(($builds | ForEach-Object id) -join ', ')")
    }
    if ($found.Count -gt 1) { Fail "'$zipName' matches more than one build. Pass -BuildId." }
    $build = $found[0]
}

if ($Version) {
    if ($zipVersion -and $zipVersion -ne $Version) {
        Warn "-Version $Version differs from the version in the file name ($zipVersion). Using $Version."
    }
} elseif ($zipVersion) {
    $Version = $zipVersion
} else {
    Fail "No version number in '$zipName'. Add one to the file name or pass -Version."
}

if ((Compare-Version $Version $build.version) -le 0) {
    $msg = "v$Version is not newer than the published v$($build.version); devices would not be prompted to update."
    if ($Force) { Warn $msg } else { Fail "$msg`nUse -Force to publish it anyway." }
}

$downloadUrl = "https://github.com/$Repo/releases/download/$Tag/$zipName"

# ---------------------------------------------------------------------------
# 3. Changelog
# ---------------------------------------------------------------------------
if ($ChangelogFile) {
    if (-not (Test-Path -LiteralPath $ChangelogFile)) { Fail "Changelog file not found: $ChangelogFile" }
    $Changelog = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $ChangelogFile))
} elseif ($Changelog) {
    $Changelog = $Changelog.Replace('\n', "`n")
} else {
    Write-Host ""
    Write-Host "Current changelog:" -ForegroundColor DarkGray
    Write-Host "  $($build.changelog)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Type what's new in v$Version, one line at a time. Put the most important change first."
    Write-Host "Press Enter on an empty line to finish (Enter straight away keeps the current text)."
    $lines = @()
    while ($true) {
        $line = Read-Host "  "
        if ([string]::IsNullOrWhiteSpace($line)) { break }
        $lines += $line
    }
    if ($lines.Count -gt 0) { $Changelog = $lines -join "`n" }
}
$Changelog = ([string]$Changelog).Trim()
$keepChangelog = [string]::IsNullOrEmpty($Changelog)
if ($keepChangelog) { Warn "No changelog entered; keeping the current text." }

# ---------------------------------------------------------------------------
# 4. Release checks and summary
# ---------------------------------------------------------------------------
$release = Get-ReleaseAssets
if ($release.isDraft) { Fail "Release '$Tag' is a draft. Publish it on GitHub first, or devices can't download from it." }
$existing = @($release.assets | Where-Object { $_.name -eq $zipName })
if ($existing.Count -gt 0 -and -not $Force) {
    Fail "'$zipName' is already in the '$Tag' release. Bump the version in the file name, or use -Force to replace it."
}

Write-Host ""
Write-Host "Build        : $($build.name) ($($build.id))"
Write-Host "Version      : $($build.version)  ->  $Version"
Write-Host "Size         : $($build.size_mb) MB  ->  $sizeMb MB"
Write-Host "SHA-256      : $sha256"
Write-Host "Upload       : $zipName  ->  release '$Tag'$(if ($existing.Count) { '  (REPLACING existing file)' })"
Write-Host "download_url : $downloadUrl"
if ($keepChangelog) { Write-Host "Changelog    : (unchanged)" }
else {
    Write-Host "Changelog    :"
    $Changelog -split "`n" | ForEach-Object { Write-Host "    $_" }
}
Write-Host "Push         : $(if ($Push) { 'commit builds.json and push' } else { 'no (commit/push yourself)' })"
Write-Host ""

if ($DryRun) { Write-Host "Dry run - nothing uploaded or changed." -ForegroundColor Yellow; exit 0 }
if (-not $Yes) {
    $answer = Read-Host "Proceed? (y/N)"
    if ($answer -notmatch '^(y|yes)$') { Write-Host "Cancelled."; exit 0 }
}

# ---------------------------------------------------------------------------
# 5. Upload and verify
# ---------------------------------------------------------------------------
Step "Uploading $zipName ($sizeMb MB) - this can take a few minutes"
$uploadArgs = @('release', 'upload', $Tag, $zipItem.FullName, '--repo', $Repo)
if ($existing.Count -gt 0) { $uploadArgs += '--clobber' }
& gh @uploadArgs
if ($LASTEXITCODE -ne 0) { Fail "Upload failed. builds.json has NOT been changed." }

Step "Verifying the upload"
$uploaded = @((Get-ReleaseAssets).assets | Where-Object { $_.name -eq $zipName }) | Select-Object -First 1
if (-not $uploaded) { Fail "Upload finished but '$zipName' isn't listed in the release. builds.json has NOT been changed." }
if ([int64]$uploaded.size -ne [int64]$zipItem.Length) {
    Fail "Uploaded size ($($uploaded.size) bytes) doesn't match the local file ($($zipItem.Length) bytes). builds.json has NOT been changed."
}

# ---------------------------------------------------------------------------
# 6. Update builds.json (only this build's fields; formatting kept)
# ---------------------------------------------------------------------------
Step "Updating builds.json"
$nl  = "`n"; if ($manifestText.Contains("`r`n")) { $nl = "`r`n" }
$loc = Find-BuildBlock $manifestText $build.id
if (-not $loc) { Fail "Couldn't locate '$($build.id)' in builds.json text. Update it by hand: version $Version, size_mb $sizeMb, download_url $downloadUrl" }
$block = $manifestText.Substring($loc[0], $loc[1])

$fields = [ordered]@{
    'version'      = (ConvertTo-JsonString $Version)
    'download_url' = (ConvertTo-JsonString $downloadUrl)
    'size_mb'      = [string]$sizeMb
}
foreach ($key in $fields.Keys) {
    $new = Set-JsonField $block $key $fields[$key]
    if ($null -eq $new) { Fail "Field '$key' not found for $($build.id) in builds.json. Update it by hand." }
    $block = $new
}
# SHA-256 lets the wizard verify the download before installing
$new = Set-JsonField $block 'sha256' (ConvertTo-JsonString $sha256)
if ($null -eq $new) { $new = Add-JsonFieldAfterVersion $block 'sha256' (ConvertTo-JsonString $sha256) $nl }
if ($null -eq $new) { Fail "Couldn't record the SHA-256 for $($build.id). Update it by hand: $sha256" }
$block = $new

if (-not $keepChangelog) {
    $raw = ConvertTo-JsonString $Changelog
    $new = Set-JsonField $block 'changelog' $raw
    if ($null -eq $new) { $new = Add-JsonFieldAfterVersion $block 'changelog' $raw $nl }
    if ($null -eq $new) { Fail "Couldn't set the changelog for $($build.id). Update it by hand." }
    $block = $new
}

$newText = $manifestText.Substring(0, $loc[0]) + $block + $manifestText.Substring($loc[0] + $loc[1])

# Validate before writing
try { $check = ($newText | ConvertFrom-Json).builds | Where-Object { $_.id -eq $build.id } }
catch { Fail "The edited builds.json would not be valid JSON; nothing was written. ($_)" }
if ($check.version -ne $Version -or $check.download_url -ne $downloadUrl -or [int]$check.size_mb -ne $sizeMb -or
    $check.sha256 -ne $sha256 -or
    (-not $keepChangelog -and $check.changelog -ne ($Changelog -replace "`r`n", "`n"))) {
    Fail "The edited builds.json didn't read back as expected; nothing was written."
}

[IO.File]::WriteAllText($BuildsJson, $newText, (New-Object System.Text.UTF8Encoding $false))
Write-Host "builds.json updated." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 7. Commit and push
# ---------------------------------------------------------------------------
if ($Push) {
    Step "Committing and pushing builds.json"
    & git -C $RepoRoot add -- builds.json
    & git -C $RepoRoot commit -m "Publish $($build.name) v$Version" -- builds.json
    if ($LASTEXITCODE -ne 0) { Fail "git commit failed. The zip is uploaded and builds.json is updated; commit and push it yourself." }
    & git -C $RepoRoot push
    if ($LASTEXITCODE -ne 0) { Fail "git push failed. The commit is saved locally; push it with GitHub Desktop." }
    Write-Host "Pushed. Devices will see v$Version within about 5 minutes." -ForegroundColor Green
} else {
    Write-Host "Next: commit and push builds.json (e.g. in GitHub Desktop)." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 8. Remove older copies of this build from the release
# ---------------------------------------------------------------------------
# Keeps the new file and the one it replaced (devices can see the previous
# builds.json for a few minutes) and deletes anything older for this build.
$oldFile = ($build.download_url -split '/')[-1]
$prefix  = (Split-AssetName $zipName)[0]
$older   = @((Get-ReleaseAssets).assets | Where-Object {
    $_.name -ne $zipName -and $_.name -ne $oldFile -and $_.name -match '\.zip$' -and
    (Split-AssetName $_.name)[0] -eq $prefix
})
foreach ($a in $older) {
    $r = Invoke-Gh @('release', 'delete-asset', $Tag, $a.name, '--repo', $Repo, '--yes')
    if ($r.Code -eq 0) { Write-Host "Removed older copy: $($a.name)" -ForegroundColor DarkGray }
    else { Warn "Could not remove $($a.name): $($r.Out)" }
}
if ($oldFile -ne $zipName) {
    Write-Host "Kept the previous file ($oldFile) for now; it is removed automatically on your next publish of this build." -ForegroundColor DarkGray
}
