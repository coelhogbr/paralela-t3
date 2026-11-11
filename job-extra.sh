#!/usr/bin/env bash
#SBATCH --job-name=bs-extra-g20
#SBATCH --nodes=2
#SBATCH --exclusive
#SBATCH --time=01:30:00
#SBATCH --output=slurm-extra-%j.out
#
# Medicoes complementares (extra.sh), em 2 nos exclusivos da atlantica:
# espera ativa x yield, artigo com 2^k processos, escalabilidade fraca e
# sequencial por tamanho de pedaco. Estimativa: ~40 min.
#
#   make && sbatch job-extra.sh ; tail -f slurm-extra-*.out
#
# Ao terminar: python3 analisar.py | tee resultados/tabelas.txt
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
# 1024 processos em 2 nos = 512 por no; o mpirun abre alguns descritores por
# processo (saida de cada um) e o limite padrao de 1024 nao basta.
ulimit -n "$(ulimit -Hn)" 2>/dev/null || true

mkdir -p resultados
# Confere que os nos sao do mesmo tipo dos da bateria principal (maquina.txt).
{ echo "nos: $SLURM_JOB_NODELIST"; LC_ALL=C lscpu | grep -E 'Model name|Socket|Core|Thread|^CPU\(s\)';
  mpirun --version 2>&1 | head -1; } > resultados/maquina_extra.txt 2>&1
cat resultados/maquina_extra.txt

make
./extra.sh
echo "EXTRA OK"
