<#
.SYNOPSIS
factordesk bootstrap for Windows PowerShell 5.1 and PowerShell 7.

.DESCRIPTION
What it does, in order:
  1. optionally checks its own SHA-256 against the value published with the release;
  2. installs uv with uv's official installer, only if uv is missing;
  3. runs the pinned release: uvx --from factordesk==VERSION factordesk serve --open

Read it before you run it. It is short on purpose. See docs/release-checklist.md for how the
release checksum is made and docs/dashboard.md for how to use it.

.PARAMETER Version
Release to run (required; there is no "latest", so a run is repeatable).

.PARAMETER ExpectSha256
SHA-256 of this file, copied from the release page; the script stops on a mismatch.

.PARAMETER UvSha256
SHA-256 of uv's installer for the pinned uv version, if you have it.

.PARAMETER DryRun
Print what would happen and change nothing.

.PARAMETER NoOpen
Do not open the browser.

.PARAMETER ServeArgs
Extra arguments for "factordesk serve", for example: -ServeArgs '--port','8080'

.EXAMPLE
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Version 0.1.0 -ExpectSha256 <hash>
#>
param(
    [string]$Version = "",
    [string]$ExpectSha256 = "",
    [string]$UvSha256 = "",
    [switch]$DryRun,
    [switch]$NoOpen,
    [string[]]$ServeArgs = @()
)

$ErrorActionPreference = "Stop"

# uv version whose installer this script downloads (documented form:
# https://docs.astral.sh/uv/getting-started/installation/ ). Change it with a new release.
$UvVersion = "0.11.28"
$UvInstallerUrl = "https://astral.sh/uv/$UvVersion/install.ps1"

function Stop-Install([string]$Message) {
    [Console]::Error.WriteLine("install.ps1: error: $Message")
    exit 1
}

function Test-Sha256([string]$Value) {
    return $Value -match '^[0-9a-fA-F]{64}$'
}

if ($Version -eq "") { Stop-Install "-Version is required, for example: -Version 0.1.0" }
if ($Version -notmatch '^[0-9]+(\.[0-9]+)*([.-]?[A-Za-z0-9]+)*$') {
    Stop-Install "version '$Version' does not look like a release number"
}
if ($ExpectSha256 -ne "" -and -not (Test-Sha256 $ExpectSha256)) { Stop-Install "-ExpectSha256 must be 64 hex digits" }
if ($UvSha256 -ne "" -and -not (Test-Sha256 $UvSha256)) { Stop-Install "-UvSha256 must be 64 hex digits" }

# 1. Check this file against the published checksum. This catches a damaged or swapped download.
# It cannot protect you if the place you got both the script and the checksum from is hacked, so
# take the checksum from the release page and the script from the same tagged release.
if ($ExpectSha256 -ne "") {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $PSCommandPath).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectSha256.ToLowerInvariant()) {
        Stop-Install "checksum mismatch for ${PSCommandPath}: expected $($ExpectSha256.ToLowerInvariant()), got $actual"
    }
    Write-Host "Checksum of this script matches the published value."
}

# 2. Find uv. The uv installer puts it in ~\.local\bin, which may not be on PATH yet.
$env:Path = "$HOME\.local\bin;$env:Path"
$uvx = Get-Command uvx -ErrorAction SilentlyContinue

$openFlag = @()
if (-not $NoOpen) { $openFlag = @("--open") }
$serveLine = (@("uvx", "--from", "factordesk==$Version", "factordesk", "serve") + $openFlag + $ServeArgs) -join " "

Write-Host "This script will:"
if ($uvx) {
    Write-Host "  1. keep your existing uv ($($uvx.Source))"
} else {
    Write-Host "  1. download uv's installer from $UvInstallerUrl"
    if ($UvSha256 -ne "") { Write-Host "     and check its SHA-256 against the value you gave" }
    Write-Host "     and run it (puts uv in ~\.local\bin and adds that folder to your user PATH)"
}
Write-Host "  2. run: $serveLine"
Write-Host "     (uv downloads factordesk $Version from PyPI into its cache; nothing else is installed)"
Write-Host "     The dashboard stays running until you press Ctrl+C."

if ($DryRun) {
    Write-Host "Dry run: nothing was downloaded, installed or started."
    exit 0
}

if (-not $uvx) {
    # Windows PowerShell 5.1 may default to old TLS versions.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("uv-install-" + [Guid]::NewGuid().ToString("N") + ".ps1")
    try {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $UvInstallerUrl -OutFile $tmp
        } catch {
            Stop-Install "could not download ${UvInstallerUrl}: $($_.Exception.Message)"
        }
        if ($UvSha256 -ne "") {
            $got = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp).Hash.ToLowerInvariant()
            if ($got -ne $UvSha256.ToLowerInvariant()) {
                Stop-Install "uv installer checksum mismatch: expected $($UvSha256.ToLowerInvariant()), got $got"
            }
        }
        & powershell -NoProfile -ExecutionPolicy Bypass -File $tmp
        if ($LASTEXITCODE -ne 0) { Stop-Install "the uv installer failed (exit code $LASTEXITCODE)" }
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
        Stop-Install "uv was installed but uvx is not on PATH; open a new terminal and run this script again"
    }
}

# 3. Run the pinned release.
& uvx --from "factordesk==$Version" factordesk serve @openFlag @ServeArgs
exit $LASTEXITCODE
