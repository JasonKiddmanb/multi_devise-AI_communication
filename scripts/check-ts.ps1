$tsPath = "$env:ProgramFiles\Tailscale\tailscale.exe"
if (Test-Path $tsPath) {
    Write-Host "tailscale.exe found at: $tsPath"
    $env:Path += ";$env:ProgramFiles\Tailscale"
    tailscale status
} else {
    Write-Host "tailscale.exe NOT found"
    # Check other locations
    Get-ChildItem "$env:ProgramFiles\Tailscale" -ErrorAction SilentlyContinue
}
