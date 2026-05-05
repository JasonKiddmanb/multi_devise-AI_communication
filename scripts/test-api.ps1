Write-Host "Testing API..." -ForegroundColor Cyan

# Web
try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080' -TimeoutSec 5 -UseBasicParsing; Write-Host "✅ Web: $($r.StatusCode) $($r.Content.Length)bytes" } catch { Write-Host "❌ Web: $_" }

# List
try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/conversations' -TimeoutSec 5; Write-Host "✅ GET convs: $($r.Count)" } catch { Write-Host "❌ GET convs: $_" }

# Create
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/conversations' -Method POST -Body '{"title":"test","model":"demo"}' -ContentType 'application/json' -TimeoutSec 5
    Write-Host "✅ POST conv: id=$($r.id)"
    $cid = $r.id

    # Save
    try {
        $body = '{"messages":[{"role":"user","content":"hello"}]}'
        Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/conversations/$cid" -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 5 | Out-Null
        Write-Host "✅ Save msg OK"
    } catch { Write-Host "❌ Save msg: $_" }

    # Get back
    try {
        $c = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/conversations/$cid" -TimeoutSec 5
        Write-Host "✅ Get conv: $($c.messages.Count) msgs"
    } catch { Write-Host "❌ Get conv: $_" }

    # Delete
    try { Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/conversations/$cid" -Method DELETE -TimeoutSec 5 | Out-Null; Write-Host "✅ Delete OK" } catch { Write-Host "❌ Delete: $_" }
} catch { Write-Host "❌ POST conv: $_" }

Write-Host "`n✅ All tests done" -ForegroundColor Green
