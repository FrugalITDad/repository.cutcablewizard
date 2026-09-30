<#
.SYNOPSIS
    Packages a new version of the CutCableWizard add-on for the Kodi repository.

.DESCRIPTION
    1. Sets the new version in repo/plugin.program.cutcablewizard/addon.xml and
       in repo/zips/addons.xml (defaults to the next patch number, e.g. 2.9.0 -> 2.9.1)
    2. Zips repo/plugin.program.cutcablewizard into
       repo/zips/plugin.program.cutcablewizard/plugin.program.cutcablewizard-<version>.zip
       (Kodi-style: forward slashes, no __pycache__ / .pyc)
    3. Regenerates repo/zips/addons.xml.md5 over the exact bytes GitHub will serve
    4. Keeps only the newest -Keep wizard zips (default 2) and deletes older ones

    Then commit and push. Kodi devices pick up the new wizard from your repository.

.EXAMPLE
    .\tools\package-wizard.ps1              # next patch version
.EXAMPLE
    .\tools\package-wizard.ps1 -Version 3.0.0
#>
[CmdletBinding()]
param(
    [string]$Version,
    [int]$Keep = 2,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$RepoRoot  = Split-Path -Parent $PSScriptRoot
$AddonId   = 'plugin.program.cutcablewizard'
$AddonDir  = Join-Path $RepoRoot "repo\$AddonId"
$AddonXml  = Join-Path $AddonDir 'addon.xml'
$ZipsDir   = Join-Path $RepoRoot 'repo\zips'
$RepoXml   = Join-Path $ZipsDir 'addons.xml'
$RepoMd5   = Join-Path $ZipsDir 'addons.xml.md5'
$OutDir    = Join-Path $ZipsDir $AddonId
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Fail([string]$m) { Write-Host "ERROR: $m" -ForegroundColor Red; exit 1 }
function Step([string]$m) { Write-Host "==> $m" -ForegroundColor Cyan }

function Get-VersionParts([string]$v) { @([regex]::Matches($v, '\d+') | ForEach-Object { [int]$_.Value }) }
function Compare-Version([string]$a, [string]$b) {
    $pa = Get-VersionParts $a; $pb = Get-VersionParts $b
    $n = [Math]::Max($pa.Count, $pb.Count)
    for ($i = 0; $i -lt $n; $i++) {
        $x = 0; if ($i -lt $pa.Count) { $x = $pa[$i] }
        $y = 0; if ($i -lt $pb.Count) { $y = $pb[$i] }
        if ($x -gt $y) { return 1 }; if ($x -lt $y) { return -1 }
    }
    return 0
}

# Replaces version="..." on the <addon id="plugin.program.cutcablewizard" ...> element only
function Set-AddonVersion([string]$text, [string]$newVersion) {
    $re = New-Object System.Text.RegularExpressions.Regex ('(<addon\b[^>]*\bid="' + [regex]::Escape($AddonId) + '"[^>]*?\bversion=")([^"]+)(")')
    if (-not $re.IsMatch($text)) { return $null }
    $ev = { param($m) $m.Groups[1].Value + $newVersion + $m.Groups[3].Value }.GetNewClosure()
    return $re.Replace($text, $ev, 1)
}

foreach ($f in @($AddonXml, $RepoXml)) { if (-not (Test-Path $f)) { Fail "Not found: $f" } }

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
$addonText = [IO.File]::ReadAllText($AddonXml)
$m = [regex]::Match($addonText, '<addon\b[^>]*\bid="' + [regex]::Escape($AddonId) + '"[^>]*?\bversion="([^"]+)"')
if (-not $m.Success) { Fail "Couldn't read the current version from addon.xml" }
$current = $m.Groups[1].Value
if (-not $Version) {
    $p = Get-VersionParts $current
    while ($p.Count -lt 3) { $p += 0 }
    $p[$p.Count - 1]++
    $Version = ($p -join '.')
}
if ($Version -notmatch '^\d+(\.\d+)+$') { Fail "'$Version' isn't a version number like 2.9.1" }
if ((Compare-Version $Version $current) -le 0) { Fail "v$Version is not newer than the current v$current" }

$zipName = "$AddonId-$Version.zip"
$zipPath = Join-Path $OutDir $zipName
Write-Host ""
Write-Host "Wizard version : $current  ->  $Version"
Write-Host "Zip            : repo\zips\$AddonId\$zipName"
Write-Host "Keep           : newest $Keep zips"
if ($DryRun) { Write-Host "Dry run - nothing changed." -ForegroundColor Yellow; exit 0 }

# ---------------------------------------------------------------------------
# Update both addon.xml files (LF line endings, as GitHub serves them)
# ---------------------------------------------------------------------------
Step "Updating version in addon.xml and addons.xml"
$newAddon = Set-AddonVersion $addonText $Version
if ($null -eq $newAddon) { Fail "Couldn't set the version in addon.xml" }
[IO.File]::WriteAllText($AddonXml, ($newAddon -replace "`r`n", "`n"), $Utf8NoBom)

$repoText = [IO.File]::ReadAllText($RepoXml)
$newRepo  = Set-AddonVersion $repoText $Version
if ($null -eq $newRepo) { Fail "Couldn't find $AddonId in repo\zips\addons.xml" }
$newRepo  = $newRepo -replace "`r`n", "`n"
[IO.File]::WriteAllText($RepoXml, $newRepo, $Utf8NoBom)

# ---------------------------------------------------------------------------
# Build the zip (forward slashes, folder entries, no caches)
# ---------------------------------------------------------------------------
Step "Creating $zipName"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
$parent  = Split-Path -Parent $AddonDir
$archive = [System.IO.Compression.ZipFile]::Open($zipPath, 'Create')
try {
    $dirs = @($AddonDir) + @(Get-ChildItem -LiteralPath $AddonDir -Recurse -Directory |
            Where-Object { $_.FullName -notmatch '[\\/]__pycache__([\\/]|$)' } | ForEach-Object FullName)
    foreach ($d in ($dirs | Sort-Object)) {
        $rel = $d.Substring($parent.Length).TrimStart('\', '/').Replace('\', '/') + '/'
        [void]$archive.CreateEntry($rel)
    }
    $files = Get-ChildItem -LiteralPath $AddonDir -Recurse -File |
             Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc' } |
             Sort-Object FullName
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($parent.Length).TrimStart('\', '/').Replace('\', '/')
        [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $f.FullName, $rel, 'Optimal')
    }
} finally {
    $archive.Dispose()
}

# ---------------------------------------------------------------------------
# Checksum over the exact bytes of addons.xml
# ---------------------------------------------------------------------------
Step "Updating addons.xml.md5"
$md5 = (Get-FileHash -Algorithm MD5 -LiteralPath $RepoXml).Hash.ToLower()
[IO.File]::WriteAllText($RepoMd5, $md5, $Utf8NoBom)

# ---------------------------------------------------------------------------
# Keep only the newest $Keep wizard zips
# ---------------------------------------------------------------------------
$zips = @(Get-ChildItem -LiteralPath $OutDir -Filter "$AddonId-*.zip" | ForEach-Object {
    [pscustomobject]@{ File = $_; Version = ($_.BaseName -replace ('^' + [regex]::Escape($AddonId) + '-'), '') }
})
$sorted = [System.Collections.ArrayList]@()
foreach ($z in $zips) {                                      # newest first
    $i = 0
    while ($i -lt $sorted.Count -and (Compare-Version $z.Version $sorted[$i].Version) -le 0) { $i++ }
    $sorted.Insert($i, $z)
}
if ($sorted.Count -gt $Keep) {
    Step "Removing older wizard zips (keeping $Keep)"
    foreach ($z in $sorted[$Keep..($sorted.Count - 1)]) {
        Remove-Item -LiteralPath $z.File.FullName -Force
        Write-Host "  removed $($z.File.Name)" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "Wizard v$Version packaged. Commit and push to publish it to devices." -ForegroundColor Green
