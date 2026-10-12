#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python manage.py bootstrap_render_admin
unset DJANGO_SUPERUSER_USERNAME DJANGO_SUPERUSER_EMAIL DJANGO_SUPERUSER_PASSWORD
exec /bin/sh scripts/start-render.sh
