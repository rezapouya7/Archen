#!/usr/bin/env bash
# PATH: scripts/serve_gunicorn_with_tunnel.sh
# Serve via Gunicorn and expose through Cloudflare Quick Tunnel.
# Requires: cloudflared in PATH
# Usage: bash scripts/serve_gunicorn_with_tunnel.sh [PORT]

set -euo pipefail
PORT="${1:-8000}"
export PYTHONUNBUFFERED=1

bash "$(dirname "$0")/serve_gunicorn.sh" 0.0.0.0 "${PORT}" &
APP_PID=$!
echo "Gunicorn started (PID=${APP_PID}) on 0.0.0.0:${PORT}"

echo "Starting Cloudflare Quick Tunnel to http://127.0.0.1:${PORT} ..."
exec cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${PORT}"

