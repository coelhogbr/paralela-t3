# Funcoes comuns ao medir.sh e ao extra.sh (carregado com ".", nao executar):
# deteccao do processador, lancadores do mpirun e mediana das repeticoes.
#
# Variaveis (com padrao):
#   REPS=3            repeticoes por ponto (vale a mediana)
#   LIMITE_REPS=600   se uma execucao passa disso (s), pula as demais repeticoes
#   TEMPO_MAX=7200    aborta uma execucao travada (o seq de 1M leva ~17 min)
#   LOCAL=0           1 = teste fora do cluster, sem Slurm
#   MPIRUN=           substitui o mpirun (ex.: "srun --mpi=pmi2")

REPS=${REPS:-3}
LIMITE_REPS=${LIMITE_REPS:-600}
TEMPO_MAX=${TEMPO_MAX:-7200}
LOCAL=${LOCAL:-0}

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
#   acima disso          : aumento do numero de processos; sem fixacao e cedendo
#                          a CPU quando bloqueado, senao a espera ativa dos nos
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

# lanca_modo MODO NP programa args...   (2 nos, round-robin)
# Escolhe o processador e o jeito de esperar, para separar o efeito do HT do
# efeito da espera ativa no MPI_Recv:
#   ht-*       um rank por hardware thread (usa o HT); com 31 ranks = lanca 31
#   fisico-*   todos os ranks confinados a uma hardware thread por nucleo
#              fisico: dois ranks no mesmo nucleo se revezam (fatia de tempo)
#   *-polling  espera padrao do Open MPI: o rank bloqueado consulta a chegada
#              de mensagens sem parar e ocupa o processador
#   *-yield    mpi_yield_when_idle: a cada consulta sem novidade, cede a CPU
lanca_modo() {
    local modo=$1 np=$2; shift 2
    local flags=(--oversubscribe --map-by node) antes=()
    case $modo in
        ht-*)     flags+=(--use-hwthread-cpus) ;;
        fisico-*) flags+=(--bind-to none); antes=(taskset -c "$PRIMARIAS") ;;
        *)        echo "modo invalido: $modo" >&2; return 1 ;;
    esac
    case $modo in
        *-yield)   flags+=(--mca mpi_yield_when_idle 1) ;;
        *-polling) ;;
        *)         echo "modo invalido: $modo" >&2; return 1 ;;
    esac
    timeout "$TEMPO_MAX" mpirun "${flags[@]}" -n "$np" "${antes[@]}" "$@"
}

# Mesmos ranks, mas confinados a uma hardware thread por nucleo fisico e
# cedendo a CPU: comparado com lanca, isola o ganho do HT (mesma arvore).
lanca_fisico() { lanca_modo fisico-yield "$@"; }

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

# mede ARQUIVO PREFIXO ROTULO comando...: acrescenta a mediana ao arquivo
# (com PREFIXO antes dela, se nao vazio) e mostra tempo, ok e repeticoes.
mede() {
    local arq=$1 pre=$2 rot=$3 linha; shift 3
    if linha=$(mediana "$@"); then
        echo "$pre$linha" >> "$arq"
        echo "   $rot: $(echo "$linha" | cut -d';' -f5-7 --output-delimiter=' ')"
    else
        echo "   $rot: FALHOU (erro ou mais de ${TEMPO_MAX}s)"
    fi
}

CAB='versao;processos;n;delta;tempo;ok;reps;tmin;tmax'
CAB_CARGA='versao;processos;n;rank;nivel;filhos;recebido;conquistado;inicio;bs;intercala;envio;espera;fim'
