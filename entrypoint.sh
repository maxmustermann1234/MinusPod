#!/bin/bash
set -e

# Ensure cache and data directories exist and are writable
# These may be mounted volumes, so we create them if needed
mkdir -p /app/data/.cache
mkdir -p /app/data/podcasts

# Run the application with gunicorn (production WSGI server)
# cd to src directory so relative imports work correctly
cd /app/src
exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --access-logfile - main:app
