#!/bin/bash
# Submit from the tibava repo root:  sbatch hpc/tibava.sbatch
# Pin to the node your VS Code runs on to use its port forwarding, e.g.
#   sbatch -p p_80G --nodelist=gpu-h100-03 hpc/tibava.sbatch
#SBATCH --job-name=tibava
#SBATCH --partition=p_48G
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=1-00:00:00
#SBATCH --output=data/logs/slurm-%j.out

cd "$SLURM_SUBMIT_DIR"
exec bash hpc/start.sh
