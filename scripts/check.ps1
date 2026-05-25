param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Token = $env:QMT_API_TOKEN
)

$ErrorActionPreference = "Stop"

$headers = @{}
if ($Token) {
    $headers["Authorization"] = "Bearer $Token"
}

Write-Host "Health:"
Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"

Write-Host "Metrics:"
Invoke-RestMethod -Method Get -Uri "$BaseUrl/metrics" -Headers $headers
