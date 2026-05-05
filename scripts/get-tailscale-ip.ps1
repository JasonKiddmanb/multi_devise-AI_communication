<#
.SYNOPSIS
    查看本机 Tailscale IP 地址
.DESCRIPTION
    显示 PC 的 Tailscale IP，供 iOS Safari 连接使用。
#>

$ip = tailscale ip -4 2>$null
if ($ip) {
    Write-Host "`n  Tailscale IP: " -NoNewline
    Write-Host "$ip" -ForegroundColor Green
    Write-Host "  iOS Safari 打开: " -NoNewline
    Write-Host "http://${ip}:8080" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "  Tailscale 未连接。请先运行 tailscale up 登录。" -ForegroundColor Red
}
