param(
    [string]$Userdata = $env:QMT_USERDATA,
    [string]$AccountId = $env:QMT_ACCOUNT_ID,
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$argsList = @("run", "qmtserver", "serve", "--host", $HostName, "--port", "$Port", "--reload")
if ($Userdata) {
    $argsList += @("--userdata", $Userdata)
}
if ($AccountId) {
    $argsList += @("--account-id", $AccountId)
}

uv @argsList
