#!/usr/bin/env bash
# Coleta os tempos do T3 para UM tamanho de vetor:  ./medir.sh N
# Deve rodar dentro da alocacao de 2 nos exclusivos do job.sh. Gera em $RES:
#
#   tempos_N.csv  sequencial + arvore classica + arvore do artigo, por np
#                 (1..31, 2..32 no artigo, e 63..1023 nas duas arvores)
#   carga_N.csv   uma linha por rank de cada execucao  -> balanceamento por nivel
#   ht_N.csv      31 processos com HT x os mesmos 31 so nos nucleos fisicos
#
# Cada tempo e a MEDIANA de ate REPS execucoes (lancador.sh). Se uma execucao
# passa de LIMITE_REPS segundos, as demais repeticoes daquele ponto sao
# puladas: a coluna reps diz quantas valeram.
set -euo pipefail
cd "$(dirname "$0")"

N=${1:?uso: ./medir.sh N}
PROCS_ARVORE=${PROCS_ARVORE:-"3 7 15 31"}
PROCS_ARTIGO=${PROCS_ARTIGO:-"2 3 4 7 8 15 16 31 32"}
PROCS_MUITOS=${PROCS_MUITOS:-"63 127 255 511 1023"}
NP_HT=${NP_HT:-31}
RES=${RES:-resultados}
. ./lancador.sh

# np=1 na versao MPI e identico ao sequencial + overhead do MPI: so vale a
# pena para os tamanhos em que custa pouco (com 1M seriam outros 17 min).
if [ "$N" -lt 1000000 ]; then
    PROCS_ARVORE="1 $PROCS_ARVORE"; PROCS_ARTIGO="1 $PROCS_ARTIGO"
fi

mkdir -p "$RES"
TEMPOS=$RES/tempos_$N.csv; CARGA=$RES/carga_$N.csv; HT=$RES/ht_$N.csv
echo "$CAB" > "$TEMPOS"; echo "$CAB_CARGA" > "$CARGA"; echo "modo;$CAB" > "$HT"

echo "N=$N | nucleos fisicos/no: $NUC | hw threads/no: $HW | reps: $REPS (limite ${LIMITE_REPS}s)"
echo "   (colunas: tempo ok repeticoes)"

# ------------------------------------------------------------ sequencial ----
echo ">> sequencial"
mede "$TEMPOS" "" seq timeout "$TEMPO_MAX" ./bs_seq -n "$N"

# --------------------------------------------------------------- arvores ----
# -b grava a carga de cada rank em toda execucao: o MPI_Gather acontece depois
# da medicao, entao nao altera o tempo. A analise tira a media das repeticoes.
roda() {  # versao np
    mede "$TEMPOS" "" "$1 p=$2" lanca "$2" ./bs_mpi -v "$1" -n "$N" -b "$CARGA"
}
echo ">> arvore classica";  for np in $PROCS_ARVORE; do roda arvore "$np"; done
echo ">> arvore do artigo"; for np in $PROCS_ARTIGO; do roda artigo "$np"; done
echo ">> aumento do numero de processos"
for np in $PROCS_MUITOS; do roda arvore "$np"; roda artigo "$np"; done

# -------------------------------------------------------------------- HT ----
if [ "$LOCAL" != 1 ]; then
    echo ">> HT: $NP_HT processos com HT x so nucleos fisicos"
    for v in arvore artigo; do
        mede "$HT" "ht;"     "$v com HT"     lanca        "$NP_HT" ./bs_mpi -v $v -n "$N"
        mede "$HT" "fisico;" "$v so fisicos" lanca_fisico "$NP_HT" ./bs_mpi -v $v -n "$N"
    done
fi

echo "pronto: $TEMPOS $CARGA $HT"
