#!/usr/bin/env bash
# Medicoes complementares do T3:  ./extra.sh
# Roda na alocacao de 2 nos exclusivos do job-extra.sh, depois das baterias do
# medir.sh (usa o sequencial de tempos_N.csv como base). Gera em $RES:
#
#   espera_N.csv        arvore classica p=31: {HT, so fisicos} x {polling, yield},
#                       e a arvore do artigo p=16 (mesmos 16 pedacos) de referencia
#   carga_espera_N.csv  carga por rank dessas execucoes (modo na 1a coluna)
#   muitos2k_N.csv      arvore do artigo com 64..1024 processos (pedacos iguais)
#   fraca.csv           escalabilidade fraca: N cresce com os processos
#                       ordenadores, n0 elementos para cada um
#   carga_fraca.csv     carga por rank das execucoes de fraca.csv
#   seq_pedacos.csv     sequencial nos tamanhos de pedaco N/2^j que as arvores
#                       ordenam -> speed-up sobre a mesma divisao (S_div)
set -euo pipefail
cd "$(dirname "$0")"

NS=${NS:-"10000 100000 1000000"}
NS_ESPERA=${NS_ESPERA:-"100000 1000000"}
NP_ESPERA=${NP_ESPERA:-31}
PROCS_2K_MUITOS=${PROCS_2K_MUITOS:-"64 128 256 512 1024"}
N0=${N0:-62500}                                  # = 10^6 / 16
PROCS_FRACA_ARVORE=${PROCS_FRACA_ARVORE:-"1 3 7 15 31 63"}
PROCS_FRACA_ARTIGO=${PROCS_FRACA_ARTIGO:-"1 2 4 8 16 32 64"}
NIVEIS_PEDACO=${NIVEIS_PEDACO:-10}               # N/2 ... N/2^10 (ate 1024 pedacos)
RES=${RES:-resultados}
. ./lancador.sh

mkdir -p "$RES"
TMP_CARGA=$RES/.carga_tmp.csv       # no diretorio compartilhado: quem grava e o rank 0
echo "nucleos fisicos/no: $NUC | hw threads/no: $HW | reps: $REPS (limite ${LIMITE_REPS}s)"
echo "   (colunas: tempo ok repeticoes)"

# ------------------------------------------- espera ativa x ceder a CPU ----
# Na arvore classica com 31 processos, os 15 nos internos so esperam. Se a
# espera ocupa o processador (polling), as 16 folhas perdem parte dele.
for n in $NS_ESPERA; do
    ESPERA=$RES/espera_$n.csv; CARGA_ESPERA=$RES/carga_espera_$n.csv
    echo "modo;$CAB" > "$ESPERA"; echo "modo;$CAB_CARGA" > "$CARGA_ESPERA"
    echo ">> espera: arvore classica p=$NP_ESPERA, N=$n"
    for modo in ht-polling ht-yield fisico-polling fisico-yield; do
        rm -f "$TMP_CARGA"
        mede "$ESPERA" "$modo;" "$modo" \
            lanca_modo "$modo" "$NP_ESPERA" ./bs_mpi -v arvore -n "$n" -b "$TMP_CARGA"
        [ -f "$TMP_CARGA" ] && sed "s/^/$modo;/" "$TMP_CARGA" >> "$CARGA_ESPERA"
    done
    # referencia: o artigo com a mesma divisao (16 pedacos), 1 rank por nucleo fisico
    np_ref=$(( (NP_ESPERA + 1) / 2 ))
    rm -f "$TMP_CARGA"
    mede "$ESPERA" "artigo;" "artigo p=$np_ref" lanca "$np_ref" ./bs_mpi -v artigo -n "$n" -b "$TMP_CARGA"
    [ -f "$TMP_CARGA" ] && sed "s/^/artigo;/" "$TMP_CARGA" >> "$CARGA_ESPERA"
done
rm -f "$TMP_CARGA"

# ---------------------------------------- artigo com 2^k, muitos processos ----
# A serie 63..1023 do medir.sh so tem 2^k - 1: no artigo, um rank sempre fica
# com o pedaco dobrado. Com 2^k todos os pedacos sao iguais.
for n in $NS; do
    MUITOS=$RES/muitos2k_$n.csv; echo "$CAB" > "$MUITOS"
    echo ">> artigo 2^k, N=$n"
    for np in $PROCS_2K_MUITOS; do
        mede "$MUITOS" "" "artigo p=$np" lanca "$np" ./bs_mpi -v artigo -n "$n"
    done
done

# ------------------------------------------------- escalabilidade fraca ----
# Cada processo ordenador recebe n0 elementos: N = n0 x folhas na classica
# ((p+1)/2 folhas) e N = n0 x p no artigo (p = 2^k, todos ordenam).
FRACA=$RES/fraca.csv; CARGA_FRACA=$RES/carga_fraca.csv
echo "$CAB" > "$FRACA"; echo "$CAB_CARGA" > "$CARGA_FRACA"
echo ">> escalabilidade fraca, n0=$N0"
mede "$FRACA" "" "seq N=$N0" timeout "$TEMPO_MAX" ./bs_seq -n "$N0"
for np in $PROCS_FRACA_ARVORE; do
    n=$(( N0 * (np + 1) / 2 ))
    mede "$FRACA" "" "arvore p=$np N=$n" lanca "$np" ./bs_mpi -v arvore -n "$n" -b "$CARGA_FRACA"
done
for np in $PROCS_FRACA_ARTIGO; do
    n=$(( N0 * np ))
    mede "$FRACA" "" "artigo p=$np N=$n" lanca "$np" ./bs_mpi -v artigo -n "$n" -b "$CARGA_FRACA"
done

# ------------------------------------------- sequencial por pedaco ----
# Tempo de ordenar sozinho cada tamanho de pedaco que as arvores ordenam
# (N/2, N/4, ...): somando os pedacos de uma execucao, tem-se o sequencial
# com a MESMA divisao, que separa o ganho de dividir do ganho de paralelizar.
SEQ=$RES/seq_pedacos.csv; echo "$CAB" > "$SEQ"
TAMS=$(for n in $NS; do for ((j = 1; j <= NIVEIS_PEDACO; j++)); do
           if [ $(( n >> j )) -gt 1 ]; then echo $(( n >> j )); fi; done; done | sort -nu)
echo ">> sequencial por pedaco: $(echo $TAMS)"
for t in $TAMS; do
    mede "$SEQ" "" "seq N=$t" timeout "$TEMPO_MAX" ./bs_seq -n "$t"
done

echo "pronto: $RES/{espera,carga_espera,muitos2k}_N.csv $FRACA $CARGA_FRACA $SEQ"
