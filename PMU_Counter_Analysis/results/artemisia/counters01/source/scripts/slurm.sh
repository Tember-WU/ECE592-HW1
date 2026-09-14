#!/bin/bash
#SBATCH --job-name=pmu84
#SBATCH --output=pmu84_%j.out
#SBATCH --error=pmu84_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
set -euo pipefail
: "${SLURM_JOB_ID:?Submit through the scheduler; do not benchmark on a login node}"
if [[ $# -lt 2 ]]; then
    echo 'Usage: sbatch [live account/constraint options] scripts/slurm.sh configs/actual_cpu.json RUN_ID [runner options]' >&2
    exit 2
fi
cd "${SLURM_SUBMIT_DIR:?Submit from PMU_Counter_Analysis}"
profile=$1
run_id=$2
shift 2
srun --cpu-bind=cores python3 scripts/run.py --config "$profile" --run-id "$run_id" "$@"
