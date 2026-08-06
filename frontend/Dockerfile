FROM node:24-alpine AS builder
WORKDIR /build
RUN npm install -g pnpm@11
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json index.html ./
COPY public ./public
COPY src ./src
RUN pnpm run build

FROM nginx:1.31-alpine
# Alpine's busybox has no useradd (that's shadow-utils, a Debian/Ubuntu
# thing every other service's non-root Dockerfile step relies on) - adduser
# is the Alpine equivalent. start.sh templates default.conf and writes
# env.js at container startup, and nginx itself needs to create its own
# temp/cache dirs and pid file - all root-owned in the base image, so all
# get explicitly chowned here.
RUN adduser -D -u 1000 kafkaml \
    && chown -R kafkaml:kafkaml /etc/nginx/conf.d /var/cache/nginx /run
COPY --from=builder --chown=kafkaml:kafkaml /build/dist /usr/share/nginx/html
COPY nginx-custom.conf /default.template.conf
COPY start.sh /start.sh
USER kafkaml
CMD ["sh", "/start.sh"]
