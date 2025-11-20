Param(
  [int]$Port = 54623
)

#
# Cleanup Windows portproxy + firewall rule created by setup_portproxy.ps1.
# Run PowerShell as Administrator.
#

Write-Host "[i] Removing portproxy for 0.0.0.0:$Port"
& netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 | Out-Null

Write-Host "[i] Removing Windows Firewall rule Archen-$Port"
& netsh advfirewall firewall delete rule name="Archen-$Port" | Out-Null

Write-Host "[ok] Cleanup completed."

