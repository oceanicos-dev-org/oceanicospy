#!/bin/bash
#SBATCH --job-name="C4"
#SBATCH --cluster=fisica,cecc
#SBATCH --output=/homes/medellin/ffayalac/May_2023_swan_%j.out
#SBATCH --error=/homes/medellin/ffayalac/May_2023_swan_%j.err
#SBATCH --partition=cpu.cecc
#SBATCH --nodelist=nodo-01
#SBATCH --nodes=1
#SBATCH --ntasks=128 #up to 256 cpus
#SBATCH --mem=40G
#SBATCH --time=20:00:00  # up to 4 days
#SBATCH --mail-user=ffayalac@unal.edu.co
#SBATCH --mail-type=ALL
#SBATCH --export=SCRATCH_DIR=/scratch/$SLURM_JOB_ACCOUNT/$SLURM_JOB_USER/$SLURM_JOB_ID

cd $SCRATCH_DIR
unset  SINGULARITY_BINDPATH
export SINGULARITY_BINDPATH=$SCRATCH_DIR

parent_domains

for domain in {1..number_domains}
do
cd "run/domain_0$domain"
> ../../output/log_dom_0$domain.txt
echo "INICIO," $HOSTNAME `date`  2>&1 >>../../output/log_dom_0$domain.txt

if [ "$domain" -gt 1 ]; then
    parent_domain=${bash_dict[$domain]}
    mv "../domain_0${parent_domain}/child0${parent_domain}_0${domain}.NEST" "child0${parent_domain}_0${domain}.NEST" 
fi
singularity run /localapps/swan_41.51_test.sif  swanrun -input run.swn -omp $SLURM_NTASKS   2>&1 >> ../../output/log_dom_0$domain.txt
echo "FIN," $HOSTNAME `date`  2>&1 >> ../../output/log_dom_0$domain.txt
cd ../../
done
