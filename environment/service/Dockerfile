# NestJS probe-API image used by the agent's docker-compose stack.
# Multi-stage to keep the runtime layer small.

# --- Builder stage ----------------------------------------------------------
FROM node:20.18.0-alpine AS builder
WORKDIR /usr/src/app

# Install all deps (including dev) for the TypeScript build.
COPY package.json ./
RUN npm install --no-audit --no-fund

COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# --- Runtime stage ----------------------------------------------------------
FROM node:20.18.0-alpine AS runtime
ENV NODE_ENV=production
WORKDIR /usr/src/app

# Production deps only.
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

# Compiled JavaScript from the builder stage.
COPY --from=builder /usr/src/app/dist ./dist

EXPOSE 8080
CMD ["node", "dist/main.js"]