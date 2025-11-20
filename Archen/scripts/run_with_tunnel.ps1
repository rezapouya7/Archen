# Runs Django on 0.0.0.0:8000 and opens a Cloudflare Quick Tunnel to 127.0.0.1:8000
# Requires: python, cloudflared in PATH
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run_with_tunnel.ps1

param(
  [int]$Port = 8000
)

# Start Django dev server
$env:PYTHONUNBUFFERED='1'
$django = Start-Process -FilePath python -ArgumentList @('manage.py','runserver',"0.0.0.0:$Port") -PassThru
Write-Host "Django runserver started. PID=$($django.Id) on 0.0.0.0:$Port"

Start-Sleep -Seconds 2

# Start cloudflared quick tunnel
$tunnelArgs = @('tunnel','--url',"http://127.0.0.1:$Port")
Write-Host "Starting Cloudflare Quick Tunnel to http://127.0.0.1:$Port ..."
Start-Process -FilePath cloudflared -ArgumentList $tunnelArgs -NoNewWindow
