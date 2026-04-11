#!/bin/sh
PORT=${PORT:-8080}
exec gunicorn --chdir backend "app:create_app()" --bind 0.0.0.0:$PORT
