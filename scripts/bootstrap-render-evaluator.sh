#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python manage.py bootstrap_render_evaluator
unset DJANGO_EVALUATOR_USERNAME DJANGO_EVALUATOR_EMAIL DJANGO_EVALUATOR_PASSWORD
exec /bin/sh scripts/start-render.sh
