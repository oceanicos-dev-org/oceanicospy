#!/bin/bash
#SBATCH --job-name="case_name"
#SBATCH --cluster=fisica
#SBATCH --output=output_path_casetest_cecc_%j.out
#SBATCH --error=output_path_casetest_cecc_%j.err
#SBATCH --partition=cpu.cecc
#SBATCH --ntasks=8
#SBATCH --mem=20G
#SBATCH --time=20:00:00  # up to 4 days
#SBATCH --mail-user=ffayalac@unal.edu.co
#SBATCH --mail-type=ALL
#SBATCH --export=SCRATCH_DIR=/scratch/$SLURM_JOB_ACCOUNT/$SLURM_JOB_USER/$SLURM_JOB_ID

export I_MPI_HYDRA_BOOTSTRAP=ssh
unset  SINGULARITY_BINDPATH
export SINGULARITY_BINDPATH="/scratchsan/medellin/:/scratchsan/medellin/"

> output_path_caselog.txt

echo "INICIO," $HOSTNAME `date`  2>&1 >>output_path_caselog.txt
singularity run /localapps/xbeach_MPI_latest.sif mpirun -np 12 -launcher=ssh xbeach  2>&1 >>output_path_caselog.txt
##srun --mpi=pmix_v4  -N1 -n 1 /usr/local/bin/singularity run /localapps/xbeach_MPI_latest.sif mpirun -np 12 -launcher=ssh xbeach  2>&1 >>/scratchsan/medellin/ffayalac/runs/xbeach_SA/SoundBay_2D/output/log.txt
echo "FIN," $HOSTNAME `date`  2>&1 >>output_path_caselog.txt