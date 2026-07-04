#!/bin/sh

python manage.py migrate
python manage.py collectstatic --noinput

# Start Celery in the background
celery -A backend worker --loglevel=info --concurrency=1 &

# Start the web server in the foreground
exec waitress-serve --host=0.0.0.0 --port=$PORT backend.wsgi:application