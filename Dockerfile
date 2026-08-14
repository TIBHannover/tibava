# --- Stage 1: Build environment ---
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagickwand-dev imagemagick git

# Install uv using the official standalone installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation for faster container startup
ENV UV_COMPILE_BYTECODE=1

ARG WORKSPACE_MEMBER

# Copy only the dependency files first to leverage Docker's layer caching
COPY uv.lock /app/uv.lock
COPY .python-version /app/.python-version
COPY pyproject.toml /app/pyproject.toml
# COPY README.md /app/README.md
COPY packages/ /app/packages/
COPY backend/ /app/backend/
COPY analyser/ /app/analyser/
COPY inference_ray/ /app/inference_ray/

# Install dependencies into a virtual environment at /app/.venv
# We use --no-install-project because the application code isn't copied yet
RUN --mount=type=cache,target=/root/.cache/uv \
    # uv sync --frozen --no-dev --package ${WORKSPACE_MEMBER}
    uv sync --frozen --no-dev --package ${WORKSPACE_MEMBER} --no-editable


# --- Stage 2: Final lightweight runtime ---
FROM python:3.12-slim-bookworm


RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagickwand-dev imagemagick git

WORKDIR /app

# Re-declare the ARG in the new stage
ARG WORKSPACE_MEMBER

# Copy the isolated virtual environment
COPY --from=builder /app/.venv /app/.venv

# Copy ONLY the target package's source code into the final image
COPY .python-version /app/.python-version
COPY analyser/ /app/analyser/
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY inference_ray/ /app/inference_ray/
COPY packages/ /app/packages/
COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock

# Place the virtual environment's binaries at the front of the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Run your application
ENTRYPOINT []
