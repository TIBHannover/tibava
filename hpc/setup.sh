#!/bin/bash
# One-time setup (no GPU needed): build the runtime image and the frontend.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# 1. runtime image (postgres, memcached, valkey/redis, nginx, imagemagick, ffmpeg)
[[ -f hpc/tibava-hpc.sif ]] || apptainer build hpc/tibava-hpc.sif hpc/tibava-hpc.def

# 2. python venv for the whole uv workspace (backend + analyser + inference_ray)
uv sync --frozen --all-packages

# 3. frontend: talk to the backend through nginx under /backend (same layout as
#    templates/app.config.js.j2 with an empty script_name), then build with node 16.
cat > frontend/app.config.js <<'JS'
module.exports = {
  API_LOCATION: '/backend',
  THUMBNAIL_LOCATION: '/thumbnails',
};
JS
apptainer exec --cleanenv --env HOME="$HOME" --pwd "$ROOT/frontend" docker://node:16-bullseye \
    bash -c "npm install && npm run build"

mkdir -p data/{analyser,cache,media,predictions,backend_cache,tmp,db,logs}
echo "setup done - now: sbatch hpc/tibava.sbatch   (from $ROOT)"
