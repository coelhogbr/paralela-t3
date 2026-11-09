#!/usr/bin/env bash
# Coleta os tempos do T3 para UM tamanho de vetor:  ./medir.sh N
# Deve rodar dentro da alocacao de 2 nos exclusivos do job.sh. Gera em $RES:
#
#   tempos_N.csv  sequencial + arvore classica + arvore do artigo, por np
#                 (1..31, 2..32 no artigo, e 63..1023 nas duas arvores)
#   carga_N.csv   uma linha por rank de cada execucao  -> balanceamento por nivel
#   ht_N.csv      31 processos com HT x os mesmos 31 so nos nucleos fisicos
#
# Cada tempo e a MEDIANA de ate REPS execucoes. Se uma execucao passa de
# LIMITE_REPS segundos, as demais repeticoes daquele ponto sao puladas (o
# sequencial de 1M leva ~74 min): a coluna reps diz quantas valeram.
set -euo pipefail
cd "$(dirname "$0")"

N=${1:?uso: ./medir.sh N}
REPS=${REPS:-3}
LIMITE_REPS=${LIMITE_REPS:-600}
TEMPO_MAX=${TEMPO_MAX:-7200}    # aborta uma execucao travada (seq 1M ~ 74 min)
PROCS_ARVORE=${PROCS_ARVORE:-"3 7 15 31"}
PROCS_ARTIGO=${PROCS_ARTIGO:-"2 3 4 7 8 15 16 31 32"}
PROCS_MUITOS=${PROCS_MUITOS:-"63 127 255 511 1023"}
NP_HT=${NP_HT:-31}
RES=${RES:-resultados}
LOCAL=${LOCAL:-0}               # 1 = teste fora do cluster, sem Slurm

# np=1 na versao MPI e identico ao sequencial + overhead do MPI: so vale a
# pena para os tamanhos em que custa pouco (com 1M seriam outros 74 min).
if [ "$N" -lt 1000000 ]; then
    PROCS_ARVORE="1 $PROCS_ARVORE"; PROCS_ARTIGO="1 $PROCS_ARTIGO"
fi

# ------------------------------------------------------------- lancador -----
if [ "$LOCAL" = 1 ]; then
    NUC=64; HW=64; PRIMARIAS=""
else
    NUC=$(LC_ALL=C lscpu | awk -F: '/^Core\(s\) per socket/{c=$2} /^Socket\(s\)/{s=$2} END{print c*s}')
    HW=$(nproc --all)
    # Uma hardware thread por nucleo fisico (a primeira de cada par HT).
    PRIMARIAS=$(lscpu -p=CPU,CORE,SOCKET | grep -v '^#' | awk -F, '!v[$2","$3]++{print $1}' | paste -sd,)
fi

# lanca NP programa args...   (2 nos, round-robin: metade dos ranks em cada)
#   ate NUC ranks por no : um rank por nucleo fisico
#   ate HW  ranks por no : um rank por hardware thread (usa o HT)
#   acima disso          : excesso de processos; sem fixacao e cedendo a CPU
#                          quando bloqueado, senao a espera ativa dos nos
#                          internos rouba o processador das folhas.
lanca() {
    local np=$1; shift
    if [ -n "${MPIRUN:-}" ]; then timeout "$TEMPO_MAX" $MPIRUN -n "$np" "$@"; return; fi
    if [ "$LOCAL" = 1 ]; then timeout "$TEMPO_MAX" mpirun --oversubscribe -n "$np" "$@"; return; fi
    local por_no=$(( (np + 1) / 2 )) extra=""
    if   [ "$por_no" -gt "$HW" ];  then extra="--bind-to none --mca mpi_yield_when_idle 1"
    elif [ "$por_no" -gt "$NUC" ]; then extra="--use-hwthread-cpus"
    fi
    timeout "$TEMPO_MAX" mpirun --oversubscribe --map-by node $extra -n "$np" "$@"
}

# Mesmos ranks, mas confinados a uma hardware thread por nucleo fisico: dois
# ranks por nucleo se revezam (fatia de tempo) em vez de rodar em paralelo no
# HT. Comparado com lanca, isola o ganho do HT (mesma arvore, mesmo trabalho).
lanca_fisico() {
    local np=$1; shift
    timeout "$TEMPO_MAX" mpirun --oversubscribe --map-by node --bind-to none \
        --mca mpi_yield_when_idle 1 -n "$np" taskset -c "$PRIMARIAS" "$@"
}

# mediana comando...  -> linha da mediana + ;reps;tmin;tmax
# Falha (sem saida, status 1) se alguma execucao falhar ou passar de
# TEMPO_MAX segundos: um ponto travado nao derruba o resto da bateria.
mediana() {
    local i linha t saida=()
    for ((i = 0; i < REPS; i++)); do
        linha=$("$@" | tail -1) || return 1
        [ -n "$linha" ] || return 1
        saida+=("$linha")
        t=$(echo "$linha" | cut -d';' -f5)
        awk -v t="$t" -v l="$LIMITE_REPS" 'BEGIN{exit !(t > l)}' && break
    done
    printf '%s\n' "${saida[@]}" | sort -t';' -k5 -g |
        awk -F';' '{l[NR]=$0; t[NR]=$5}
             END {print l[int((NR+1)/2)] ";" NR ";" t[1] ";" t[NR]}'
}

CAB='versao;processos;n;delta;tempo;ok;reps;tmin;tmax'
CAB_CARGA='versao;processos;n;rank;nivel;filhos;recebido;conquistado;inicio;bs;intercala;envio;espera;fim'
mkdir -p "$RES"
TEMPOS=$RES/tempos_$N.csv; CARGA=$RES/carga_$N.csv; HT=$RES/ht_$N.csv
echo "$CAB" > "$TEMPOS"; echo "$CAB_CARGA" > "$CARGA"; echo "modo;$CAB" > "$HT"
# mede ARQUIVO PREFIXO ROTULO comando...: acrescenta a mediana ao arquivo
# (com PREFIXO; antes dele, se nao vazio) e mostra tempo, ok e repeticoes.
mede() {
    local arq=$1 pre=$2 rot=$3 linha; shift 3
    if linha=$(mediana "$@"); then
        echo "$pre$linha" >> "$arq"
        echo "   $rot: $(echo "$linha" | cut -d';' -f5-7 --output-delimiter=' ')"
    else
        echo "   $rot: FALHOU (erro ou mais de ${TEMPO_MAX}s)"
    fi
}

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
echo ">> excesso de processos"
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
