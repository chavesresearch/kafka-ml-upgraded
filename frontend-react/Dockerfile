FROM node:20-alpine AS builder
WORKDIR /build
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY vite.config.ts tsconfig.json index.html ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx-custom.conf /default.template.conf
COPY start.sh /start.sh
CMD ["sh", "/start.sh"]
