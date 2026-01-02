#!/bin/sh
set -e

echo "Running Django migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn gym_project.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 4