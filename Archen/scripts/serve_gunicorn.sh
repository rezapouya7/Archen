#!/usr/bin/env bash
# PATH: scripts/serve_gunicorn.sh
# Run application with Gunicorn + WhiteNoise for production.
# Usage: bash scripts/serve_gunicorn.sh [HOST] [PORT] [WORKERS]

set -euo pipefail
HOST="${1:-0.0.0.0}"
PORT="${2:-8000}"
WORKERS="${3:-3}"

export DJANGO_SETTINGS_MODULE=Archen.settings
export PYTHONUNBUFFERED=1

# Apply migrations and collect static before serving (idempotent for CI/CD)
python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn Archen.wsgi:application \
  --bind "${HOST}:${PORT}" \
  --workers "${WORKERS}" \
  --access-logfile '-' --error-logfile '-' --forwarded-allow-ips='*'

