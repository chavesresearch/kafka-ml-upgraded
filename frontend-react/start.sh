set -ex

export BACKEND_PROXY_URL=${BACKEND_PROXY_URL:-"http://localhost:80"}
export BACKEND_URL=${BACKEND_URL:-"/api"}
export ENABLE_FEDML_BLOCKCHAIN=${ENABLE_FEDML_BLOCKCHAIN:-"0"}

envsubst < /usr/share/nginx/html/env.template.js > /usr/share/nginx/html/env.js
envsubst '$BACKEND_PROXY_URL' < /default.template.conf > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
