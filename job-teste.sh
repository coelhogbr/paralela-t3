#!/usr/bin/env bash
#SBATCH --job-name=bs-teste-g20
#SBATCH --nodes=2
#SBATCH --exclusive
#SBATCH --time=00:15:00
#SBATCH --output=slurm-teste-%j.out
#
# Ensaio rapido ANTES da medicao real (o codigo nao pode ser testado fora do
# LAD). Confere, em ordem:
#   1. limites da particao (o job de 1M precisa de ~5 h) e do usuario;
#   2. compilacao e corretude (make teste: varios np, N impar, abort com np=5);
#   3. onde cai cada rank (2 nos, round-robin) e o modo "so nucleos fisicos";
#   4. se o cluster consegue lancar 1023 processos em 2 nos;
#   5. a bateria inteira do medir.sh com N pequeno e 1 repeticao.
# Tem de terminar com "ENSAIO OK".
#
#   sbatch job-teste.sh ; cat slurm-teste-*.out
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

echo "===== 1. particao e limites"
sinfo || true
scontrol show partition 2>/dev/null | grep -E 'PartitionName|MaxTime|DefaultTime|MaxNodes' || true
echo "nos: $SLURM_JOB_NODELIST"
echo "ulimit -u (processos): $(ulimit -u)   ulimit -n (arquivos): $(ulimit -n)"
LC_ALL=C lscpu | grep -E 'Model name|Socket|Core|Thread|^CPU\(s\)'
mpirun --version 2>&1 | head -1

echo "===== 2. compilacao e corretude"
make clean && make
make teste

echo "===== 3. distribuicao dos ranks"
echo "-- 31 ranks em 2 nos (esperado 16 + 15):"
mpirun --oversubscribe --map-by node --use-hwthread-cpus -n 31 hostname | sort | uniq -c
PRIMARIAS=$(lscpu -p=CPU,CORE,SOCKET | grep -v '^#' | awk -F, '!v[$2","$3]++{print $1}' | paste -sd,)
echo "-- uma hardware thread por nucleo fisico: $PRIMARIAS"
mpirun --oversubscribe --map-by node --bind-to none -n 4 \
    taskset -c "$PRIMARIAS" sh -c 'echo "$(hostname): $(taskset -pc $$)"'

echo "===== 4. 1023 processos"
mpirun --oversubscribe --map-by node --bind-to none --mca mpi_yield_when_idle 1 \
    -n 1023 hostname | sort | uniq -c
for v in arvore artigo; do
    timeout 300 mpirun --oversubscribe --map-by node --bind-to none \
        --mca mpi_yield_when_idle 1 -n 1023 ./bs_mpi -v $v -n 20000
done

echo "===== 5. bateria completa em miniatura"
REPS=1 RES=resultados-teste ./medir.sh 20000
python3 analisar.py resultados-teste > /dev/null && echo "analisar.py ok"
rm -rf resultados-teste

echo "ENSAIO OK"
