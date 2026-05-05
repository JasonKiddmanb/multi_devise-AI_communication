<#
.SYNOPSIS
    AI Remote Compute Mesh — Windows PC 一键部署 (V1)
.DESCRIPTION
    检查/安装依赖 (Docker, Ollama, Tailscale)，
    配置 Ollama 监听 0.0.0.0，启动 Open WebUI。
    所有流量经 Tailscale WireGuard 加密隧道 — 支持 LAN 直连和远程中继。
#>

Write-Host @"
╔══════════════════════════════════════════════════╗
║   AI Remote Compute Mesh — V1 自动部署           ║
║                                                  ║
║   本脚本会检查依赖、配置网络、启动 Open WebUI     ║
║   请先确认已安装: Tailscale + Ollama + Docker    ║
╚══════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

$ErrorActionPreference = "Stop"
$STEP = 0

function Step($Title) {
    $global:STEP += 1
    Write-Host "`n[$STEP] $Title" -ForegroundColor Cyan
}

function Check-Command($Name) {
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        Write-Host "  ✔ $Name found" -ForegroundColor Green
        return $true
    }
    Write-Host "  ✘ $Name not found" -ForegroundColor Red
    return $false
}

# --------------------------------------------------
Step "Checking prerequisites"
# --------------------------------------------------
$hasDocker = Check-Command "docker"
$hasOllama = Check-Command "ollama"
$hasTailscale = Check-Command "tailscale"

if (-not $hasTailscale) {
    Write-Host "  → Install Tailscale from https://tailscale.com/download" -ForegroundColor Yellow
}

if (-not $hasDocker) {
    Write-Host "  → Install Docker Desktop from https://docs.docker.com/desktop/setup/install/windows-install/" -ForegroundColor Yellow
}

if (-not $hasOllama) {
    Write-Host "  → Install Ollama from https://ollama.com/download" -ForegroundColor Yellow
    Write-Host "  → Then run: ollama pull llama3.2"
}

if (-not ($hasDocker -and $hasOllama -and $hasTailscale)) {
    Write-Host "`n  缺少依赖，请安装后再运行此脚本。" -ForegroundColor Yellow
    Write-Host "  检查清单: docs/setup-checklist.md" -ForegroundColor Yellow
    exit 1
}

# --------------------------------------------------
Step "Checking Ollama models"
# --------------------------------------------------
$models = ollama list 2>$null
if (-not $models) {
    Write-Host "  ⚠ 还没有拉取模型！推荐:" -ForegroundColor Yellow
    Write-Host "     ollama pull llama3.2    (2GB, 入门推荐)" -ForegroundColor Yellow
    Write-Host "     ollama pull qwen2.5:7b  (7GB, 中文更强)" -ForegroundColor Yellow
} else {
    Write-Host "  ✔ 已安装的模型:" -ForegroundColor Green
    $models | Select-String -NotMatch "NAME" | ForEach-Object { Write-Host "     $_" }
}

# --------------------------------------------------
Step "Configuring Ollama for Tailscale network access"
# --------------------------------------------------
$ollamaHost = [Environment]::GetEnvironmentVariable("OLLAMA_HOST", "User")
if ($ollamaHost -ne "0.0.0.0") {
    Write-Host "  Setting OLLAMA_HOST=0.0.0.0 (user-level env var)" -ForegroundColor Yellow
    setx OLLAMA_HOST "0.0.0.0"
    Write-Host "  ⚠ 请重启 Ollama 让设置生效" -ForegroundColor Magenta
    Write-Host "     右键系统托盘 Ollama 图标 → Quit → 重新打开" -ForegroundColor Magenta
} else {
    Write-Host "  ✔ OLLAMA_HOST already set to 0.0.0.0" -ForegroundColor Green
}

# --------------------------------------------------
Step "Checking Tailscale status"
# --------------------------------------------------
$tsStatus = tailscale status --json 2>$null | ConvertFrom-Json
if ($tsStatus -and $tsStatus.Self.Online) {
    $ip = $tsStatus.Self.TailscaleIPs[0]
    Write-Host "  ✔ Tailscale 已连接 — PC Tailscale IP: $ip" -ForegroundColor Green
    Write-Host "  → 同 LAN 下自动走直连，远程则走 DERP 中继，无需手动切换" -ForegroundColor Green
    Write-Host "  → iOS Safari 打开 http://$ip`:8080" -ForegroundColor Green
} else {
    Write-Host "  ✘ Tailscale 未连接。请先运行 'tailscale up' 登录。" -ForegroundColor Red
    exit 1
}

# --------------------------------------------------
Step "Pulling Open WebUI Docker image"
# --------------------------------------------------
docker pull ghcr.io/open-webui/open-webui:main
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ✘ Docker pull failed" -ForegroundColor Red
    exit 1
}

# --------------------------------------------------
Step "Launching Open WebUI"
# --------------------------------------------------
$projectRoot = Split-Path $PSScriptRoot -Parent
docker compose -f "$projectRoot/docker-compose.yml" up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✔ Open WebUI 已启动!" -ForegroundColor Green
    Write-Host "  ─────────────────────────────────────" -ForegroundColor Cyan
    Write-Host "  本机访问: http://localhost:8080" -ForegroundColor Cyan
    Write-Host "  iOS 访问: http://$ip`:8080" -ForegroundColor Cyan
    Write-Host "  ─────────────────────────────────────" -ForegroundColor Cyan
    Write-Host "`n  下一步: iPhone Safari 打开 http://$ip`:8080" -ForegroundColor White
}
