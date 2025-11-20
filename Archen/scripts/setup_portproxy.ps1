Param(
  [int]$Port = 54623,
  [string]$WSLIP = ""
)

#
# Temporary Windows portproxy + firewall setup for WSL2 exposure without extra tools.
# - Adds inbound firewall rule for the selected port.
# - Adds netsh portproxy rule from 0.0.0.0:$Port to $WSLIP:$Port
# - Detects WSL IP if not provided (requires wsl.exe available in PATH).
# - Run this PowerShell as Administrator.
#

function Detect-WSLIP {
  try {
    $cmd = "ip -4 -o addr show scope global | awk '{print \$4}' | cut -d/ -f1 | head -n1"
    $out = & wsl.exe -e bash -lc $cmd 2>$null
    if ($LASTEXITCODE -eq 0) { return ($out.Trim()) }
  } catch { }
  return ""
}

if (-not $WSLIP -or $WSLIP -eq "") {
  Write-Host "[i] Detecting WSL IP..."
  $WSLIP = Detect-WSLIP
}

if (-not $WSLIP -or $WSLIP -eq "") {
  Write-Error "Could not detect WSL IP. Please pass -WSLIP <ip> explicitly."
  exit 1
}

Write-Host "[i] Using WSL IP: $WSLIP"
Write-Host "[i] Opening Windows Firewall for TCP port $Port"
& netsh advfirewall firewall add rule name="Archen-$Port" dir=in action=allow protocol=TCP localport=$Port | Out-Null

Write-Host ("[i] Adding portproxy from 0.0.0.0:{0} to {1}:{0}" -f $Port, $WSLIP)
& netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectaddress=$WSLIP connectport=$Port | Out-Null

Write-Host "[ok] Portproxy + Firewall ready. Forward this port on your router to this Windows machine."
