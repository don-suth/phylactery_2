#!/usr/bin/env sh
python manage.py collectstatic --noinput
python manage.py migrate --noinput