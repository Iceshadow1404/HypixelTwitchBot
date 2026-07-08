FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Node.js (v18 LTS) for the networth service
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (cached layer as long as the lockfile is unchanged)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Node dependencies for networth.js
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN chmod +x start.sh

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/config \
    PATH="/app/.venv/bin:$PATH"

CMD ["./start.sh"]
