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
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx-custom.conf /default.template.conf
COPY start.sh /start.sh
CMD ["sh", "/start.sh"]
