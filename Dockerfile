# --- Stage 1: Build environment ---
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagickwand-dev imagemagick git ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Pin uv version so upstream releases don't silently bust your layer cache
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/root/.cache/uv

ARG WORKSPACE_MEMBER

# 1. Copy ONLY the lockfile and every workspace member's pyproject.toml first
COPY uv.lock .python-version pyproject.toml ./
COPY packages/tibava_data/pyproject.toml ./packages/tibava_data/pyproject.toml
COPY packages/tibava_interface/pyproject.toml ./packages/tibava_interface/pyproject.toml
COPY packages/tibava_utils/pyproject.toml ./packages/tibava_utils/pyproject.toml
COPY inference_ray/pyproject.toml ./inference_ray/pyproject.toml
COPY analyser/pyproject.toml ./analyser/pyproject.toml
COPY backend/pyproject.toml ./backend/pyproject.toml

# 2. Install ONLY external dependencies (cached unless uv.lock or a pyproject.toml changes!)
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev --package ${WORKSPACE_MEMBER} --no-install-project --no-install-workspace

# 3. NOW copy the actual source code (editing .py files only invalidates from here down)
COPY packages/ /app/packages/
COPY backend/ /app/backend/
COPY analyser/ /app/analyser/
COPY inference_ray/ /app/inference_ray/

# 4. Install your local workspace packages into the existing .venv (~1-2 seconds, zero downloads)
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-dev --package ${WORKSPACE_MEMBER} --no-editable


# --- Stage 2: Final lightweight runtime ---
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagickwand-dev imagemagick git ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY .python-version pyproject.toml uv.lock ./
COPY analyser/ /app/analyser/
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY inference_ray/ /app/inference_ray/
COPY packages/ /app/packages/

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []
