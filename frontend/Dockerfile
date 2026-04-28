FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* package-lock.json* ./
RUN corepack enable && \
    if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; \
    elif [ -f package-lock.json ]; then npm ci; \
    else npm install; fi

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && pnpm build || npm run build

FROM caddy:2-alpine AS runner
COPY --from=builder /app/out /srv
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
