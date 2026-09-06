# ==============================================================================
# Hermes Business Agent - Production Dockerfile
# Pre-bakes Python 3.12, Node.js 20, uv, Hermes Agent, and Chromium browser drivers.
# ==============================================================================

FROM python:3.12-slim-bookworm AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HERMES_HOME=/root/.hermes \
    HERMES_PROJECT_SRC=/app/src \
    HERMES_ENABLE_PROJECT_PLUGINS=1 \
    PATH="/root/.local/bin:/app/src/.venv/bin:${PATH}"

WORKDIR /app

# 1. Install OS Dependencies & Playwright/Chromium C-libraries
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    curl \
    git \
    build-essential \
    sqlite3 \
    libsqlite3-dev \
    ca-certificates \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Node.js 20 LTS & agent-browser
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y -qq nodejs \
    && npm install -g agent-browser@0.35.1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Astral uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 4. Install Hermes Agent CLI
RUN curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash || true

# 5. Copy project dependency manifests and install dependencies
COPY src/pyproject.toml src/uv.lock src/.python-version* /app/src/
WORKDIR /app/src
RUN uv sync --frozen \
    && uv tool install tavily-cli==0.1.6 \
    && uv run python -m playwright install chromium

# 6. Copy application code
WORKDIR /app
COPY src/ /app/src/

# 7. Startup command: ensure symlinks exist in mounted volume before starting gateway
WORKDIR /app/src
EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /root/.hermes/profiles/protein-bar && ln -sfn /app/src/.hermes/plugins /root/.hermes/plugins && ln -sfn /app/src/SOUL.md /root/.hermes/SOUL.md && ln -sfn /app/src/workspaces/protein-bar/SOUL.md /root/.hermes/profiles/protein-bar/SOUL.md && exec hermes gateway run"]
