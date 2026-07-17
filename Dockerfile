# Install uv
FROM ghcr.io/astral-sh/uv:debian

# Change the working directory to the `app` directory
WORKDIR /app

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy


COPY uv.lock /app/uv.lock
COPY .python-version /app/.python-version
COPY pyproject.toml /app/pyproject.toml
COPY packages/tibava_data/pyproject.toml /app/packages/tibava_data/pyproject.toml
COPY packages/tibava_interface/pyproject.toml /app/packages/tibava_interface/pyproject.toml
COPY packages/tibava_utils/pyproject.toml /app/packages/tibava_utils/pyproject.toml
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY analyser/pyproject.toml /app/analyser/pyproject.toml
COPY inference_ray/pyproject.toml /app/inference_ray/pyproject.toml

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
# COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"
# Explicitly set VIRTUAL_ENV so uv and Ray agree on where it lives
# ENV VIRTUAL_ENV="/app/.venv"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []
