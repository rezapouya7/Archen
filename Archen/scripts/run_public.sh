#!/usr/bin/env bash
# Temporary public run for local network exposure on 0.0.0.0
# No external tools required. Starts Django on given PORT (default: 54623).
# Notes:
#  - This only binds locally. External access still requires router port forward to this machine.
#  - For WSL2, you may also need Windows portproxy (see scripts/setup_portproxy.ps1).

set -euo pipefail

PORT="${1:-54623}"
export PYTHONUNBUFFERED=1

# Detect WSL IP (best-effort) to help the user with portproxy/router mapping
WSL_IP=""
if command -v ip >/dev/null 2>&1; then
  WSL_IP=$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -n1 || true)
fi

echo "Starting Django on 0.0.0.0:${PORT}"
if [ -n "$WSL_IP" ]; then
  echo "Detected WSL IP: ${WSL_IP}"
  echo "If Windows cannot reach WSL directly from outside, use scripts/setup_portproxy.ps1 with -Port ${PORT} -WSLIP ${WSL_IP}"
fi

python manage.py runserver 0.0.0.0:${PORT}

