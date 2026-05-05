param([switch]$Background)

$WEB_DIR = "e:\my_1st_claudeCode_prjt\app\web"
$PORT = 8080

$server = New-Object System.Net.HttpListener
$server.Prefixes.Add("http://127.0.0.1:$PORT/")

$server.Start()
Write-Host "Web server running on http://127.0.0.1:$PORT"

while ($server.IsListening) {
    $ctx = $server.GetContext()
    $req = $ctx.Request
    $rsp = $ctx.Response
    $urlPath = $req.Url.AbsolutePath

    try {
        if ($urlPath -eq "/") { $urlPath = "/index.html" }

        # Proxy /ollama/* -> localhost:11434
        if ($urlPath -like "/ollama*") {
            $targetUrl = "http://localhost:11434" + $urlPath.Substring(7) + $req.Url.Query
            $client = New-Object System.Net.Http.HttpClient
            $client.Timeout = [System.TimeSpan]::FromMinutes(5)
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
