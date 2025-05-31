#!/bin/sh
if [ "$USE_SSL" = "true" ]; then
  echo "Starting backend with SSL"
  exec uvicorn app.main:app \
    --host=0.0.0.0 \
    --port=8000 \
    --log-config=app/log_conf.yml \
    --ssl-keyfile=app/certs/server.key \
    --ssl-certfile=app/certs/server.crt
else
  echo "Starting backend without SSL"
  exec uvicorn app.main:app \
    --host=0.0.0.0 \
    --port=8000 \
    --log-config=app/log_conf.yml
fi
