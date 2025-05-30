#!/bin/sh
set -e
echo "Using self-signed certificate=$USE_SELF_SIGNED_CERT"
if [ "$USE_SELF_SIGNED_CERT" = "true" ]; then
  SSL_BLOCK="listen 443 ssl;\n    ssl_certificate /etc/nginx/ssl/server.crt;\n    ssl_certificate_key /etc/nginx/ssl/server.key;"
else
  SSL_BLOCK=""
fi
# Template replacement
sed "s|__SSL_BLOCK__|$SSL_BLOCK|" /etc/nginx/templates/nginx.template.conf > /etc/nginx/conf.d/default.conf
echo "Starting nginx..."
exec nginx -g 'daemon off;'
