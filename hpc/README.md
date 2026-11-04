# Running TIBAVA on the cluster with Apptainer (no Docker)

One Apptainer instance runs the whole docker-compose stack inside a SLURM GPU job:
postgres, memcached, valkey (redis-server), Ray + Ray Serve (inference models),
analyser (gRPC), celery, gunicorn (Django backend) and nginx (frontend + `/backend` proxy).
Python code and dependencies come from the uv venv in `tibava/.venv`.

```sh
cd ~/tibava
bash hpc/setup.sh            # once: builds hpc/tibava-hpc.sif, syncs .venv, builds frontend
sbatch hpc/tibava.sbatch     # starts everything; node + port are printed in data/logs/slurm-<id>.out
```

Then tunnel the printed port (same for every run: `20000 + (uid % 900) * 11`, override with `PORT_BASE=`):

```sh
ssh -L <port>:localhost:<port> -J <user>@<login-node> <user>@<node>
# open http://localhost:<port>
```

If the job lands on the node your VS Code Remote is connected to, just forward the port in VS Code
(`sbatch -p p_80G --nodelist=<that-node> hpc/tibava.sbatch`).

- Logs: `data/logs/*.log`. Stop: `scancel <jobid>`.
- Database lives in `data/db` (persists across jobs); uploaded videos in `data/media`.
- The first time a plugin runs, Ray builds its uv runtime env (downloads torch etc.), so the first
  analysis of each type takes several minutes.
