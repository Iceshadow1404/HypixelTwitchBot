FROM node:24.22.2-trixie-slim AS node
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM python:3.12.16-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/
COPY --from=node /usr/local/bin/node /usr/local/bin/node

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (cached layer as long as the lockfile is unchanged)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --from=node /app/node_modules ./node_modules

COPY . .
RUN chmod +x start.sh

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/config \
    PATH="/app/.venv/bin:$PATH"

CMD ["./start.sh"]
