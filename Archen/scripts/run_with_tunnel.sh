#!/usr/bin/env bash
# Runs Django on 0.0.0.0:8000 and opens a Cloudflare Quick Tunnel to 127.0.0.1:8000
# Requires: python, cloudflared in PATH
# Usage: bash scripts/run_with_tunnel.sh [PORT]

set -euo pipefail
PORT="${1:-8000}"
export PYTHONUNBUFFERED=1

# Start Django in background
python manage.py runserver 0.0.0.0:${PORT} &
DJANGO_PID=$!
echo "Django runserver started. PID=${DJANGO_PID} on 0.0.0.0:${PORT}"

# Start cloudflared quick tunnel (foreground)
exec cloudflared tunnel --url http://127.0.0.1:${PORT}