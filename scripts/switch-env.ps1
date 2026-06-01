[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("sim", "live")]
    [string]$Profile,
    [switch]$NoBackup
)

$ErrorActionPreference = "Stop"

function Read-EnvFile {
    param([string]$Path)

    $values = @{}
    Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line -split "=", 2
        $values[$key.Trim()] = $value.Trim()
    }
    return $values
}

function Get-Setting {
    param(
        [hashtable]$Values,
        [string]$Key
    )

    if ($Values.ContainsKey($Key)) {
        return $Values[$Key]
    }
    return ""
}

function Get-SecretState {
    param([string]$Value)

    if ($Value -and $Value.Trim().Trim('"')) {
        return "<set>"
    }
    return "<empty>"
}

function Get-DisplayPath {
    param([string]$Path)

    if (-not $Path) {
        return "<empty>"
    }
    $leaf = Split-Path -Leaf $Path
    $parent = Split-Path -Parent $Path
    $parentLeaf = if ($parent) { Split-Path -Leaf $parent } else { "" }
    if ($parentLeaf) {
        return "$parentLeaf\$leaf"
    }
    return $leaf
}

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root ".env.$Profile"
$target = Join-Path $root ".env"
$backup = Join-Path $root ".env.previous"

if (-not (Test-Path -LiteralPath $source)) {
    throw "Profile file not found: $source"
}

$changed = $false
if ($PSCmdlet.ShouldProcess(".env", "switch to profile '$Profile'")) {
    if ((Test-Path -LiteralPath $target) -and -not $NoBackup) {
        Copy-Item -LiteralPath $target -Destination $backup -Force
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
    $changed = $true
}

$settings = Read-EnvFile $source
$userdata = Get-Setting $settings "QMT_USERDATA"
$userdataPath = if ($userdata) { $userdata.Trim('"') } else { "" }
$userdataExists = if ($userdataPath) { Test-Path -LiteralPath $userdataPath } else { $false }

if ($changed) {
    Write-Host "Switched qmtserver env profile: $Profile"
} else {
    Write-Host "Preview qmtserver env profile: $Profile"
}
Write-Host "Active file: .env"
Write-Host "Source file: .env.$Profile"
if ($changed -and -not $NoBackup) {
    Write-Host "Previous backup: .env.previous"
} elseif (-not $NoBackup) {
    Write-Host "Previous backup: .env.previous when applied"
}
Write-Host "userdata: $(Get-DisplayPath $userdataPath)"
Write-Host "userdata exists: $userdataExists"
Write-Host "account id: $(Get-SecretState (Get-Setting $settings 'QMT_ACCOUNT_ID'))"
Write-Host "api token: $(Get-SecretState (Get-Setting $settings 'QMT_API_TOKEN'))"
Write-Host "enable trading: $(Get-Setting $settings 'QMT_ENABLE_TRADING')"
Write-Host "trading dry run: $(Get-Setting $settings 'QMT_TRADING_DRY_RUN')"
Write-Host "connect quote: $(Get-Setting $settings 'QMT_CONNECT_QUOTE')"
Write-Host "connect trader: $(Get-Setting $settings 'QMT_CONNECT_TRADER')"
