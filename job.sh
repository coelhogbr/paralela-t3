#!/usr/bin/env bash
#SBATCH --job-name=bs-mpi-g20
#SBATCH --nodes=2
#SBATCH --exclusive
#SBATCH --time=01:00:00
#SBATCH --output=slurm-%j.out
#
# Um job por tamanho de vetor, em 2 nos exclusivos da atlantica (8 nucleos /
# 16 threads HT cada). O tempo muda muito com N (bubble sort e quadratico),
# entao passe --time na linha de comando:
#
#   sbatch --time=00:30:00 job.sh 10000
#   sbatch --time=01:00:00 job.sh 100000
#   sbatch --time=05:00:00 job.sh 1000000     (sequencial sozinho ~74 min)
#
# Se o sbatch reclamar de particao ou de --time acima do limite, veja a saida
# do job-teste.sh (sinfo / scontrol show partition) e ajuste.
# acompanhar:  squeue -u $USER ; tail -f slurm-*.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
# 1023 processos em 2 nos = ~512 por no; o mpirun abre alguns descritores por
# processo (saida de cada um) e o limite padrao de 1024 nao basta.
ulimit -n "$(ulimit -Hn)" 2>/dev/null || true
N=${1:?uso: sbatch job.sh N}

mkdir -p resultados
{ echo "nos: $SLURM_JOB_NODELIST"; LC_ALL=C lscpu; free -g; gcc --version | head -1;
  mpirun --version 2>&1 | head -1; } > resultados/maquina.txt 2>&1

make
./medir.sh "$N"

# Analisa o que ja houver (os outros tamanhos podem nao ter rodado ainda).
python3 analisar.py | tee resultados/tabelas.txt || true
if python3 -c "import matplotlib" 2>/dev/null; then
    python3 graficos.py || true
else
    echo "matplotlib ausente: rode 'python3 graficos.py' na maquina local"
fi
