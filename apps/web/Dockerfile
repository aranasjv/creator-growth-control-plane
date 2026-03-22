FROM node:22-bookworm-slim AS deps
WORKDIR /app

COPY ["package.json", "package-lock.json", "nx.json", "tsconfig.base.json", "./"]
RUN npm ci

FROM node:22-bookworm-slim AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY ["package.json", "package-lock.json", "nx.json", "tsconfig.base.json", "./"]
COPY ["apps/web/", "apps/web/"]

RUN cd apps/web && ../../node_modules/.bin/next build

FROM node:22-bookworm-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/apps/web ./apps/web

WORKDIR /app/apps/web
EXPOSE 3000

CMD ["../../node_modules/.bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]

