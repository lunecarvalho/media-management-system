#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python manage.py migrate --noinput
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 2 --timeout 45 --access-logfile - --error-logfile -
