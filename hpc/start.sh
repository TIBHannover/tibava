#!/bin/bash
# Start the whole TIBAVA stack (what docker-compose.yml does) inside one Apptainer
# instance. Run it inside a SLURM GPU allocation (see hpc/tibava.sbatch).
# Ctrl-C / scancel stops everything.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

SIF=${SIF:-$ROOT/hpc/tibava-hpc.sif}
WEB_BIND=${WEB_BIND:-127.0.0.1}     # 0.0.0.0 to reach it from other cluster nodes
NUM_CPUS=${NUM_CPUS:-${SLURM_CPUS_PER_TASK:-8}}
if [[ -n "${CUDA_VISIBLE_DEVICES:-}" && "${CUDA_VISIBLE_DEVICES}" != "-1" ]]; then
    NUM_GPUS=$(tr ',' '\n' <<<"$CUDA_VISIBLE_DEVICES" | wc -l)
    DEPLOY=inference_ray/deploy.cuda.yml
else
    NUM_GPUS=0
    DEPLOY=inference_ray/deploy.yml
fi

# GPU nodes are shared, so the compose default ports (5432, 6379, 8000, ...) are
# often taken. Each user gets a block of 11 ports derived from their uid.
PORT_BASE=${PORT_BASE:-$((20000 + ($(id -u) % 900) * 11))}
WEB_PORT=$PORT_BASE                 # the only port you open in the browser
BACKEND_PORT=$((PORT_BASE + 1))
PG_PORT=$((PORT_BASE + 2))
MEMCACHED_PORT=$((PORT_BASE + 3))
VALKEY_PORT=$((PORT_BASE + 4))
RAY_PORT=$((PORT_BASE + 5))
SERVE_PORT=$((PORT_BASE + 6))
RAY_DASHBOARD_PORT=$((PORT_BASE + 7))
RAY_AGENT_PORT=$((PORT_BASE + 8))
ANALYSER_PORT=$((PORT_BASE + 9))
RAY_CLIENT_PORT=$((PORT_BASE + 10))

D=$ROOT/data
RUN=$D/run/$(hostname -s)
LOGS=$D/logs
INSTANCE=tibava-${USER}-${SLURM_JOB_ID:-$$}

mkdir -p "$RUN" "$LOGS" "$D"/{analyser,cache,media,predictions,backend_cache,tmp/nginx,db}
[[ -f "$SIF" ]] || { echo "missing $SIF - run hpc/setup.sh first"; exit 1; }
[[ -f frontend/dist/index.html ]] || { echo "frontend not built - run hpc/setup.sh first"; exit 1; }

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
for ((p = PORT_BASE; p <= PORT_BASE + 10; p++)); do
    if port_open "$p"; then
        echo "port $p already in use on $(hostname -s); pick another block: PORT_BASE=<n> sbatch ..."; exit 1
    fi
done
wait_port() {  # name port timeout_s
    local i
    for ((i = 0; i < $3; i++)); do port_open "$2" && return 0; sleep 1; done
    echo "$1 did not open port $2 within $3s - see $LOGS/$1.log"; exit 1
}

# The code defaults to docker-compose hostnames (postgres, valkey, analyser, ...).
# Point them all at localhost instead of patching the code.
{ cat /etc/hosts; echo "127.0.0.1 postgres memcached valkey analyser inference_ray backend"; } >"$RUN/hosts"

# Ray Serve listens on port 8000 in the deploy file; move it to our block.
sed "0,/^  port: 8000$/s//  port: $SERVE_PORT/" "$DEPLOY" >"$RUN/deploy.yml"

PIDS=()
cleanup() {
    trap - EXIT
    echo "stopping TIBAVA..."
    apptainer exec instance://"$INSTANCE" pg_ctl -D /pgdata stop -m fast >/dev/null 2>&1 || true
    kill "${PIDS[@]}" 2>/dev/null || true
    apptainer instance stop "$INSTANCE" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

apptainer instance start --nv --cleanenv \
    --bind "$RUN/hosts:/etc/hosts" \
    --bind "$D/analyser:/data,$D/models:/models,$D/media:/media,$D/cache:/cache" \
    --bind "$D/predictions:/predictions,$D/backend_cache:/backend_cache,$D/db:/pgdata" \
    "$SIF" "$INSTANCE"

# Run a command in the instance with the host uv venv first on PATH.
ex() {
    apptainer exec --cleanenv instance://"$INSTANCE" env LANG=C.UTF-8 LC_ALL=C.UTF-8 \
        PATH="$ROOT/.venv/bin:$HOME/.local/bin:/usr/lib/postgresql/15/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
        HOME="$HOME" USER="$USER" CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}" \
        HF_HOME=/models NUMBA_CACHE_DIR=/tmp \
        "$@"
}
bg() {  # name cmd...  -> background, log to $LOGS/name.log
    local name=$1; shift
    ex "$@" >"$LOGS/$name.log" 2>&1 &
    PIDS+=($!)
}

# --- postgres -----------------------------------------------------------------
if [[ ! -s "$D/db/PG_VERSION" ]]; then
    chmod 700 "$D/db"
    ex initdb -D /pgdata -U postgres --auth=trust >"$LOGS/initdb.log" 2>&1
fi
bg postgres postgres -D /pgdata -c listen_addresses=127.0.0.1 -c port="$PG_PORT" -c unix_socket_directories=
wait_port postgres "$PG_PORT" 60
sleep 2
ex psql -h 127.0.0.1 -p "$PG_PORT" -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='tibava'" | grep -q 1 \
    || ex createdb -h 127.0.0.1 -p "$PG_PORT" -U postgres tibava

# --- memcached + valkey(redis) ------------------------------------------------
bg memcached memcached -I 32m -l 127.0.0.1 -p "$MEMCACHED_PORT" -U 0
bg valkey redis-server --port "$VALKEY_PORT" --bind 127.0.0.1 --save "" --appendonly no
wait_port valkey "$VALKEY_PORT" 30

# --- ray + inference models ---------------------------------------------------
bg ray ray start --head --block --port="$RAY_PORT" --num-cpus="$NUM_CPUS" --num-gpus="$NUM_GPUS" \
    --dashboard-host=127.0.0.1 --dashboard-port="$RAY_DASHBOARD_PORT" \
    --dashboard-agent-listen-port="$RAY_AGENT_PORT" --ray-client-server-port="$RAY_CLIENT_PORT" \
    --temp-dir="/tmp/ray-$USER"
wait_port ray "$RAY_PORT" 120
bg serve serve run --address="127.0.0.1:$RAY_PORT" "$RUN/deploy.yml"
echo "waiting for Ray Serve ($DEPLOY)..."
wait_port serve "$SERVE_PORT" 600

# --- analyser (gRPC) ----------------------------------------------------------
bg analyser python analyser/src/analyser/server.py -c analyser/config.yml -v --port "$ANALYSER_PORT" \
    --cache_valkey_host 127.0.0.1 --cache_valkey_port "$VALKEY_PORT" \
    --inference_ray_host 127.0.0.1 --inference_ray_port "$SERVE_PORT" \
    --inference_ray_status_port "$RAY_AGENT_PORT"
wait_port analyser "$ANALYSER_PORT" 120

# --- backend: migrations, celery, gunicorn ------------------------------------
BACKEND_ENV=(
    PYTHONPATH="$ROOT/backend:$ROOT:$ROOT/analyser:$ROOT/backend/src/backend"
    ALLOWED_HOSTS='*'
    CSRF_TRUSTED_ORIGINS="http://localhost:$WEB_PORT,http://127.0.0.1:$WEB_PORT"
    MEDIA_URL=/media/ THUMBNAIL_URL=/thumbnails/
    DATA_CACHE_ROOT=/backend_cache/
    DB_HOST=127.0.0.1 DB_PORT="$PG_PORT"
    CACHE_LOCATION="127.0.0.1:$MEMCACHED_PORT"
    ANALYSER_GRPC_HOST=127.0.0.1 ANALYSER_GRPC_PORT="$ANALYSER_PORT"
    CELERY_BROKER_URL="redis://127.0.0.1:$VALKEY_PORT"
)
ex env "${BACKEND_ENV[@]}" python backend/src/backend/manage.py migrate auth >"$LOGS/migrate.log" 2>&1
ex env "${BACKEND_ENV[@]}" python backend/src/backend/manage.py migrate >>"$LOGS/migrate.log" 2>&1

cd backend/src/backend
bg celery env "${BACKEND_ENV[@]}" celery -A tibava worker -l INFO --concurrency=20 --pool=threads
cd "$ROOT"
bg backend env "${BACKEND_ENV[@]}" gunicorn --bind "127.0.0.1:$BACKEND_PORT" \
    --env SCRIPT_NAME=/backend tibava.wsgi --workers=4 --timeout 600 --capture-output --log-level info
wait_port backend "$BACKEND_PORT" 60

# --- nginx: frontend + /backend proxy + media/thumbnails ----------------------
cat >"$RUN/nginx.conf" <<EOF
worker_processes 2;
pid $RUN/nginx.pid;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log $LOGS/nginx.access.log;
    sendfile on;
    client_max_body_size 50G;
    client_body_temp_path $D/tmp/nginx/body;
    proxy_temp_path $D/tmp/nginx/proxy;
    fastcgi_temp_path $D/tmp/nginx/fastcgi;
    uwsgi_temp_path $D/tmp/nginx/uwsgi;
    scgi_temp_path $D/tmp/nginx/scgi;
    server {
        listen $WEB_BIND:$WEB_PORT;
        location /backend/ {
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_set_header Host \$http_host;
            proxy_redirect off;
            proxy_request_buffering off;
            proxy_read_timeout 600;
            proxy_pass http://127.0.0.1:$BACKEND_PORT;
        }
        location /media/ { alias /media/; }
        location /thumbnails/ { alias /predictions/; }
        location / {
            root $ROOT/frontend/dist;
            try_files \$uri \$uri/ /index.html;
        }
    }
}
EOF
bg nginx nginx -c "$RUN/nginx.conf" -e "$LOGS/nginx.error.log" -g 'daemon off;'
wait_port nginx "$WEB_PORT" 30

cat <<EOF

=====================================================================
 TIBAVA is up on $(hostname -s):$WEB_PORT   (logs: $LOGS)
 From your laptop:
   ssh -L $WEB_PORT:localhost:$WEB_PORT -J <user>@<login-node> <user>@$(hostname -s)
   then open http://localhost:$WEB_PORT
 (VS Code Remote on $(hostname -s): just forward port $WEB_PORT.)
=====================================================================
EOF

wait -n "${PIDS[@]}"
echo "a service exited - check $LOGS/*.log"
