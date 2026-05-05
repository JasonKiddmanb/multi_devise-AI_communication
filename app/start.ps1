<#
.SYNOPSIS
    AI Remote Compute Mesh — App 启动器
.DESCRIPTION
    自动启动 Ollama（内置或系统）、内置网页服务器（端口 8080），
    确认 Tailscale 连接后显示访问地址。
    无需 Docker，无需手动安装。
#>

$ErrorActionPreference = "Stop"
$APP_ROOT = Split-Path $PSCommandPath -Parent
$TOOLS   = Join-Path $APP_ROOT "tools"
$WEB_DIR = Join-Path $APP_ROOT "web"
$OLLAMA_DIR = Join-Path $TOOLS "ollama"
$TS_DIR  = Join-Path $TOOLS "tailscale"
$PORT    = 8080

$STEP = 0
function Step($Title) {
    $global:STEP += 1
    Write-Host "`n[$STEP] $Title" -ForegroundColor Cyan
}
function Ok($Text) { Write-Host "  ✔ $Text" -ForegroundColor Green }
function Warn($Text) { Write-Host "  ⚠ $Text" -ForegroundColor Yellow }
function Fail($Text) { Write-Host "  ✘ $Text" -ForegroundColor Red }

# Cleanup handler
$script:OllamaProcess = $null
$script:WebListener = $null
$script:CleanupDone = $false

function Cleanup {
    if ($script:CleanupDone) { return }
    $script:CleanupDone = $true
    Write-Host "`n`n正在关闭服务..." -ForegroundColor Yellow

    # 关闭 Ollama
    if ($script:OllamaProcess -and -not $script:OllamaProcess.HasExited) {
        $script:OllamaProcess.Kill()
        Ok "Ollama 已停止"
    }

    # 关闭 Web 服务器
    if ($script:WebListener -and $script:WebListener.IsListening) {
        $script:WebListener.Stop()
        Ok "Web 服务器已停止"
    }

    Write-Host "`n已安全退出。" -ForegroundColor Green
}

# ---- 输出 Banner ----
Write-Host @"

╔══════════════════════════════════════════╗
║     AI Remote Compute Mesh — V1         ║
║     App 一键启动                        ║
╚══════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# ================================================
Step "检查 Tailscale"
# ================================================
$tsExe = Get-Command "tailscale" -ErrorAction SilentlyContinue
if (-not $tsExe) {
    $localTs = Get-ChildItem "$TS_DIR\*tailscale*" -Include *.msi,*.exe | Select-Object -First 1
    if ($localTs) {
        Warn "系统未安装 Tailscale，正在从 tools/tailscale/ 安装..."
        try {
            if ($localTs.Extension -eq ".msi") {
                Start-Process msiexec -ArgumentList "/i `"$($localTs.FullName)`" /quiet /norestart" -Wait -NoNewWindow
            } else {
                Start-Process $localTs.FullName -ArgumentList "/quiet /norestart" -Wait -NoNewWindow
            }
            # 刷新 PATH
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            Start-Sleep 2
            $tsExe = Get-Command "tailscale" -ErrorAction SilentlyContinue
            if ($tsExe) { Ok "Tailscale 安装完成" }
            else { Fail "Tailscale 安装失败，请手动安装"; exit 1 }
        } catch {
            Fail "安装失败: $_"; exit 1
        }
    } else {
        Warn "未找到 Tailscale。运行 tools/download.bat 下载，或手动安装"
        Warn "手动安装: https://tailscale.com/download"
        # 尝试从系统已安装的路径查找
        $tsPaths = @(
            "${env:ProgramFiles}\Tailscale\tailscale.exe",
            "${env:ProgramFiles(x86)}\Tailscale\tailscale.exe"
        )
        $tsExe = $tsPaths | ForEach-Object { if (Test-Path $_) { Get-Command $_ -ErrorAction SilentlyContinue } } | Select-Object -First 1
    }
}

if ($tsExe) {
    Ok "Tailscale: $($tsExe.Source)"
} else {
    Fail "Tailscale 不可用。请安装后重试"
    exit 1
}

# 检查是否已登录
$tsStatus = & $tsExe.Source status --json 2>$null | ConvertFrom-Json
if (-not $tsStatus -or -not $tsStatus.Self.Online) {
    Write-Host "  → 请在弹出的浏览器中登录 Tailscale..." -ForegroundColor Yellow
    Start-Process $tsExe.Source -ArgumentList "up"
    Start-Sleep 3
    # 等待登录完成
    for ($i = 0; $i -lt 60; $i++) {
        $tsStatus = & $tsExe.Source status --json 2>$null | ConvertFrom-Json
        if ($tsStatus -and $tsStatus.Self.Online) { break }
        Start-Sleep 2
    }
}

if (-not $tsStatus -or -not $tsStatus.Self.Online) {
    Fail "Tailscale 登录超时。请手动运行 tailscale up"
    exit 1
}

$tsIp = $tsStatus.Self.TailscaleIPs[0]
Ok "Tailscale 已连接 — IP: $tsIp"

# ================================================
Step "启动 Ollama"
# ================================================
$ollamaExe = Get-Command "ollama" -ErrorAction SilentlyContinue
$ollamaPath = $null

if (-not $ollamaExe) {
    # 尝试使用内置版本
    $bundledOllama = Join-Path $OLLAMA_DIR "ollama.exe"
    if (Test-Path $bundledOllama) {
        $ollamaPath = $bundledOllama
        Ok "使用内置 Ollama: $ollamaPath"
    } else {
        Warn "系统未安装 Ollama，且 tools/ollama/ 中未找到 ollama.exe"
        Warn "请运行 tools/download.bat 下载，或手动安装 Ollama"
        exit 1
    }
} else {
    $ollamaPath = $ollamaExe.Source
    Ok "系统 Ollama: $ollamaPath"
}

# 设置环境变量
$env:OLLAMA_HOST = "0.0.0.0"
$env:OLLAMA_ORIGINS = "*"

# 检查是否已有 Ollama 服务在运行
$ollamaRunning = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ollamaRunning = $true }
} catch {}

if (-not $ollamaRunning) {
    # 终止可能已运行的旧 ollama 进程
    Get-Process "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force

    # 以后台进程启动 ollama serve
    Write-Host "  正在启动 Ollama 服务..." -ForegroundColor Yellow
    $script:OllamaProcess = Start-Process -FilePath $ollamaPath -ArgumentList "serve" -NoNewWindow -PassThru -RedirectStandardOutput "$APP_ROOT\ollama.log" -RedirectStandardError "$APP_ROOT\ollama.err"
    Start-Sleep 3

    # 等待 Ollama 就绪
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep 2
    }
    if (-not $ready) {
        Warn "Ollama 启动较慢，继续等待..."
        for ($i = 0; $i -lt 30; $i++) {
            try {
                $r = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -UseBasicParsing
                if ($r.StatusCode -eq 200) { $ready = $true; break }
            } catch {}
            Start-Sleep 2
        }
    }

    if ($ready) { Ok "Ollama 服务已就绪" }
    else { Warn "Ollama 可能未完全启动，请检查 ollama.log" }
} else {
    Ok "Ollama 服务已在运行"
}

# 检查模型
$models = ollama list 2>$null
if (-not $models) {
    Warn "还没有模型！推荐: ollama pull llama3.2"
    Write-Host "  你可以在本机 PowerShell 中拉取模型，然后刷新网页" -ForegroundColor Yellow
}

# ================================================
Step "启动 Web 服务器 (端口 $PORT)"
# ================================================
$server = New-Object System.Net.HttpListener
$server.Prefixes.Add("http://+:$PORT/")

try {
    $server.Start()
    $script:WebListener = $server
    Ok "Web 服务器已启动"

    Write-Host @"

  ─────────────────────────────────────────
  访问地址:
  本机:    http://localhost:$PORT
  iOS:     http://${tsIp}:$PORT

  iPhone 操作步骤:
  1. 确保 iPhone Tailscale 已连接
  2. 打开 Safari 访问上面的 iOS 地址
  3. 选择模型开始聊天
  ─────────────────────────────────────────

  按 Ctrl+C 停止所有服务

"@ -ForegroundColor Cyan

    # 打开本机浏览器
    Start-Process "http://localhost:$PORT"

    # ----- 请求处理循环 -----
    while ($server.IsListening) {
        $context = $server.GetContext()
        $req = $context.Request
        $rsp = $context.Response

        $urlPath = $req.Url.AbsolutePath

        try {
            if ($urlPath -eq "/") { $urlPath = "/index.html" }

            # 代理 /ollama/* → localhost:11434
            if ($urlPath -like "/ollama*") {
                $targetUrl = "http://localhost:11434" + $urlPath.Substring(7) + $req.Url.Query
                $client = New-Object System.Net.Http.HttpClient
                $client.Timeout = [System.TimeSpan]::FromMinutes(5)
                try {
                    # 构建转发请求
                    $method = $req.HttpMethod
                    $forwardReq = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::$method, $targetUrl)

                    # 复制请求体
                    if ($method -eq "POST" -or $method -eq "PUT") {
                        $bodyStream = $req.InputStream
                        $memStream = New-Object System.IO.MemoryStream
                        $bodyStream.CopyTo($memStream)
                        $memStream.Position = 0
                        $forwardReq.Content = New-Object System.Net.Http.StreamContent($memStream)
                        $contentType = $req.ContentType
                        if ($contentType) { $forwardReq.Content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse($contentType) }
                    }

                    # 发送
                    $forwardRsp = $client.SendAsync($forwardReq, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).Result

                    # 复制状态码和头部
                    $rsp.StatusCode = [int]$forwardRsp.StatusCode
                    foreach ($h in $forwardRsp.Headers) {
                        foreach ($v in $h.Value) {
                            try { $rsp.Headers.Add($h.Key, $v) } catch {}
                        }
                    }
                    foreach ($h in $forwardRsp.Content.Headers) {
                        foreach ($v in $h.Value) {
                            try { $rsp.Headers.Add($h.Key, $v) } catch {}
                        }
                    }

                    # 复制 CORS 头
                    $rsp.Headers.Add("Access-Control-Allow-Origin", "*")
                    $rsp.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    $rsp.Headers.Add("Access-Control-Allow-Headers", "Content-Type")

                    # 流式传输响应体
                    $forwardStream = $forwardRsp.Content.ReadAsStreamAsync().Result
                    $forwardStream.CopyTo($rsp.OutputStream)
                    $forwardStream.Dispose()
                } finally {
                    $client.Dispose()
                }
            }
            # 静态文件
            else {
                $filePath = Join-Path $WEB_DIR $urlPath
                if (-not (Test-Path $filePath -PathType Leaf)) {
                    $rsp.StatusCode = 404
                    $msg = "Not Found"
                    $data = [System.Text.Encoding]::UTF8.GetBytes($msg)
                    $rsp.OutputStream.Write($data, 0, $data.Length)
                } else {
                    $ext = [System.IO.Path]::GetExtension($filePath)
                    $mimeMap = @{
                        ".html" = "text/html; charset=utf-8"
                        ".css"  = "text/css"
                        ".js"   = "application/javascript"
                        ".png"  = "image/png"
                        ".ico"  = "image/x-icon"
                        ".svg"  = "image/svg+xml"
                        ".json" = "application/json"
                    }
                    $contentType = if ($mimeMap.ContainsKey($ext)) { $mimeMap[$ext] } else { "application/octet-stream" }
                    $rsp.ContentType = $contentType

                    $bytes = [System.IO.File]::ReadAllBytes($filePath)
                    $rsp.OutputStream.Write($bytes, 0, $bytes.Length)
                }
            }
        } catch {
            try {
                $rsp.StatusCode = 500
                $msg = "Error: $_"
                $data = [System.Text.Encoding]::UTF8.GetBytes($msg)
                $rsp.OutputStream.Write($data, 0, $data.Length)
            } catch {}
        } finally {
            $rsp.OutputStream.Close()
        }
    }
} catch {
    if ($_.Exception.Message -match "access denied") {
        Fail "需要管理员权限才能启动 Web 服务器。请右键点击 start.bat → 以管理员身份运行"
    } else {
        Fail "启动失败: $_"
    }
} finally {
    Cleanup
}
