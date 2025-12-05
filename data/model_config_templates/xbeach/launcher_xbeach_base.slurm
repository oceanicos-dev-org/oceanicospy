#!/bin/bash
#SBATCH --job-name="case_name"
#SBATCH --cluster=fisica
#SBATCH --output=output_path_case%j.out
#SBATCH --error=output_path_case%j.err
#SBATCH --partition=cpu.cecc
#SBATCH --ntasks=24
#SBATCH --mem=20G
#SBATCH --time=48:00:00  # up to 4 days
#SBATCH --mail-user=ffayalac@unal.edu.co
#SBATCH --mail-type=ALL
#SBATCH --export=SCRATCH_DIR=/scratch/$SLURM_JOB_ACCOUNT/$SLURM_JOB_USER/$SLURM_JOB_ID

export I_MPI_HYDRA_BOOTSTRAP=ssh
unset  SINGULARITY_BINDPATH
export SINGULARITY_BINDPATH="/scratchsan/medellin/:/scratchsan/medellin/"

> output_path_caselog.txt

START=$(date +%s)
echo "INICIO, $HOSTNAME $(date)" >> output_path_caselog.txt 2>&1

singularity run /localapps/xbeach_MPI_latest.sif mpirun -np 24 -launcher=ssh xbeach  2>&1 >>output_path_caselog.txt
mv output_path_case../run/*.nc output_path_case

END=$(date +%s)
echo "FIN, $HOSTNAME $(date)" >> output_path_caselog.txt 2>&1

# ----- compute formatted elapsed time -----
ELAPSED=$((END - START))

HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))
SECONDS=$((ELAPSED % 60))

printf "ELAPSED, %02d:%02d:%02d\n" "$HOURS" "$MINUTES" "$SECONDS" >> output_path_caselog.txt
