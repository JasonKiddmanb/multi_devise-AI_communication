<#
.SYNOPSIS
    仅启动网页服务器（Ollama + Tailscale 已运行时的快速启动）
    监听 0.0.0.0:8080，从 iOS 也能访问
#>

$WEB_DIR = Join-Path (Split-Path $PSCommandPath -Parent) "web"
$PORT = 8080

$tsIp = (tailscale ip -4 2>$null)
if (-not $tsIp) { $tsIp = "你的 Tailscale IP" }

# 先尝试 netsh 授权免管理员启动
netsh http delete urlacl url=http://+:8080/ 2>$null | Out-Null
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
netsh http add urlacl url=http://+:8080/ user=$user 2>$null | Out-Null

$server = New-Object System.Net.HttpListener
$server.Prefixes.Add("http://+:8080/")
$server.Prefixes.Add("http://127.0.0.1:8080/")

try {
    $server.Start()
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  Web 服务器已启动！" -ForegroundColor Green
    Write-Host "  本机: http://localhost:$PORT" -ForegroundColor Cyan
    Write-Host "  iOS:  http://${tsIp}:$PORT" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  按 Ctrl+C 停止" -ForegroundColor Yellow
    Write-Host ""

    while ($server.IsListening) {
        $ctx = $server.GetContext()
        $req = $ctx.Request
        $rsp = $ctx.Response
        $urlPath = $req.Url.AbsolutePath

        try {
            if ($urlPath -eq "/") { $urlPath = "/index.html" }

            # 代理 /ollama/* -> localhost:11434
            if ($urlPath -like "/ollama*") {
                $targetUrl = "http://localhost:11434" + $urlPath.Substring(7) + $req.Url.Query
                $client = New-Object System.Net.Http.HttpClient
                $client.Timeout = [System.TimeSpan]::FromMinutes(10)
                try {
                    $method = $req.HttpMethod
                    $forwardReq = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::$method, $targetUrl)
                    if ($method -eq "POST" -or $method -eq "PUT") {
                        $memStream = New-Object System.IO.MemoryStream
                        $req.InputStream.CopyTo($memStream)
                        $memStream.Position = 0
                        $forwardReq.Content = New-Object System.Net.Http.StreamContent($memStream)
                        $ct = $req.ContentType
                        if ($ct) { $forwardReq.Content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse($ct) }
                    }
                    $forwardRsp = $client.SendAsync($forwardReq, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).Result
                    $rsp.StatusCode = [int]$forwardRsp.StatusCode
                    $rsp.Headers.Add("Access-Control-Allow-Origin", "*")
                    $rsp.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                    $rsp.Headers.Add("Access-Control-Allow-Headers", "Content-Type")
                    foreach ($h in $forwardRsp.Headers) { foreach ($v in $h.Value) { try { $rsp.Headers.Add($h.Key, $v) } catch {} } }
                    foreach ($h in $forwardRsp.Content.Headers) { foreach ($v in $h.Value) { try { $rsp.Headers.Add($h.Key, $v) } catch {} } }
                    $forwardRsp.Content.ReadAsStreamAsync().Result.CopyTo($rsp.OutputStream)
                } finally { $client.Dispose() }
            } else {
                $filePath = Join-Path $WEB_DIR $urlPath
                if (-not (Test-Path $filePath -PathType Leaf)) {
                    $rsp.StatusCode = 404
                    $data = [System.Text.Encoding]::UTF8.GetBytes("Not Found")
                    $rsp.OutputStream.Write($data, 0, $data.Length)
                } else {
                    $ext = [System.IO.Path]::GetExtension($filePath)
                    $mimeMap = @{".html" = "text/html; charset=utf-8"; ".css" = "text/css"; ".js" = "application/javascript"; ".png" = "image/png"; ".json" = "application/json"}
                    if ($mimeMap.ContainsKey($ext)) { $rsp.ContentType = $mimeMap[$ext] }
                    [System.IO.File]::ReadAllBytes($filePath) | ForEach-Object { $rsp.OutputStream.Write($_, 0, $_.Length) }
                }
            }
        } catch {
            try { $rsp.StatusCode = 500 } catch {}
        } finally { $rsp.OutputStream.Close() }
    }
} catch {
    if ($_.Exception.Message -match "access denied") {
        Write-Host "需要管理员权限。" -ForegroundColor Red
        Write-Host "请右键点击此文件 → 使用 PowerShell 运行" -ForegroundColor Yellow
    } else {
        Write-Host "错误: $_" -ForegroundColor Red
    }
}
