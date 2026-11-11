# T3 Paralela — Bubble sort por divisão e conquista em MPI (Grupo 20, cp32020)

Bubble sort paralelizado em MPI com uma árvore binária de processos, em duas
versões, comparadas com o sequencial. Enunciado em [`docs/enunciado.md`](docs/enunciado.md),
vocabulário em [`GLOSSARY.md`](GLOSSARY.md), decisões não óbvias em [`docs/adr/`](docs/adr/).

| Versão | `-v` | Quem ordena |
|---|---|---|
| sequencial | (`bs_seq`) | um processo, o vetor inteiro — base do speed-up |
| árvore clássica | `arvore` | só as folhas; nós internos dividem e intercalam (pseudocódigo do enunciado) |
| árvore do artigo | `artigo` | todos: cada processo fica com uma metade e manda a outra a `rank + 2^nível` (Radenski, PDPTA'11), com o mesmo bubble sort |

Entrada: pior caso (`N, N-1, ..., 1`). Saída: `versao;processos;n;delta;tempo;ok`,
com `ok=1` se o resultado é exatamente `1..N`.

## Arquivos

| Arquivo | O que é |
|---|---|
| `bs.c` | Fonte único: `gcc` → `bs_seq`, `mpicc -DPARALELO` → `bs_mpi`. `-n N -v arvore\|artigo -d delta -b carga.csv -m` |
| `Makefile` | `make`; `make teste` confere `ok=1` com vários np, N ímpar, e que np=5 na árvore clássica aborta |
| `lancador.sh` | Funções comuns (carregado pelos dois abaixo): detecção do processador, `lanca`, `lanca_modo`, mediana |
| `medir.sh N` | Bateria de um tamanho → `resultados/{tempos,carga,ht}_N.csv` (mediana de 3) |
| `extra.sh` | Medições complementares → `espera_N`, `carga_espera_N`, `muitos2k_N`, `fraca`, `carga_fraca`, `seq_pedacos` |
| `analisar.py` | Tabelas: escala forte (com S_div), 2^k, aumento do número de processos, HT, espera, carga por nível, escala fraca, três abordagens. Gera `resultados/tab_*.tex` |
| `graficos.py` | As figuras do relatório (usa as contas do `analisar.py`; precisa de matplotlib) |
| `job-teste.sh` | Ensaio de ~5 min: limites da partição, `make teste`, distribuição dos ranks, 1023 processos, `medir.sh` e `extra.sh` em miniatura |
| `job.sh N` | 2 nós exclusivos: make + medir + analisar + gráficos |
| `job-extra.sh` | 2 nós exclusivos: make + `extra.sh` (~40 min) |
| `relatorio/relatorio.tex` | Relatório; `[...]` em vermelho = falta número do cluster ou seção do grupo |

## Rodar no cluster

```bash
ssh cp32020@atlantica.lad.pucrs.br          # via sparta se estiver fora da PUCRS
git clone https://github.com/coelhogbr/paralela-t3 && cd paralela-t3
which mpicc mpirun && mpirun --version      # se faltar: module avail / module load openmpi
make                                        # compila na hospedeira (NÃO executar lá)

sbatch job-teste.sh                         # 1) ensaio
cat slurm-teste-*.out                       #    tem de terminar com "ENSAIO OK"

# 2) medição real: um job por tamanho (podem ir juntos, cada um aloca 2 nós)
sbatch --time=00:30:00 job.sh 10000
sbatch --time=01:00:00 job.sh 100000
sbatch --time=05:00:00 job.sh 1000000       # sequencial sozinho ~74 min
squeue -u $USER ; tail -f slurm-*.out

# 3) ao terminar os três, regerar as tabelas com todos os tamanhos e subir
python3 analisar.py | tee resultados/tabelas.txt
git add resultados && git commit -m "Add cluster measurements" && git push

# 4) medições complementares (depois dos três: usa o sequencial de tempos_N.csv)
sbatch job-teste.sh                         # o ensaio agora também roda o extra.sh
sbatch job-extra.sh                         # ~40 min
python3 analisar.py | tee resultados/tabelas.txt
git add resultados && git commit -m "Add complementary measurements" && git push
```

Depois, na máquina local (com matplotlib): `python3 graficos.py` e compilar
o relatório (`cd relatorio && tectonic relatorio.tex`).

Compile com `make` **antes** de submeter: os três jobs rodam `make` ao mesmo
tempo e, com os binários já atualizados, isso não faz nada (sem corrida).

**Conferir no `slurm-teste-*.out`:**

- `MaxTime` da partição: se for menor que 5 h, o job de 1M precisa ser
  dividido (ex.: `PROCS_ARTIGO=... ./medir.sh`) ou rodar com `REPS=1`.
- 31 ranks em 2 nós: 16 + 15. O teste com `taskset` deve mostrar só uma
  hardware thread por núcleo físico (é o modo "sem HT" da comparação de HT).
- 1023 processos: se o `mpirun` falhar (limite de processos/arquivos), anotar o
  maior np que funciona e passar `PROCS_MUITOS="63 127 ..."` ao `medir.sh`.
- Se o `mpirun` recusar alguma flag: `MPIRUN="srun --mpi=pmi2" sbatch job.sh N`
  (perde o modo "só núcleos físicos" da comparação de HT).

## Experimentos e o que cada um responde

| Experimento | Configuração | Pergunta |
|---|---|---|
| Escala | seq + p = 1, 3, 7, 15, 31, duas árvores | speed-up e eficiência (superlinear: o trabalho cai para N²/L com L folhas) |
| Artigo 2^k | p = 2, 4, 8, 16, 32 | a árvore do artigo com pedaços iguais |
| Carga por nível | `-b` em toda execução | quanto cada nível ordena, intercala e espera |
| HT | 15 × 31; e 31 com HT × 31 só em núcleos físicos | separar o efeito da árvore maior do efeito do HT |
| Aumento do número de processos | p = 63 … 1023 (e 64 … 1024 no artigo) | os nós internos ociosos liberam CPU às folhas — até quando compensa? |
| Espera (`extra.sh`) | clássica p = 31: {HT, só físicos} × {polling, yield}; artigo p = 16 | quanto a espera ativa dos nós internos tira das folhas |
| Escala fraca (`extra.sh`) | n0 = 62.500 por processo ordenador, até 63/64 processos | o que cresce com N quando o trabalho por processo é fixo |
| Sequencial por pedaço (`extra.sh`) | seq de N/2 … N/1024 | S_div: speed-up sobre o sequencial com a mesma divisão |

`p` conta todos os processos, inclusive os nós internos, que na árvore
clássica só esperam: `E = S/p`. Acima de 32 processos, `S/32` (hardware threads).
`S_div = Σ T_seq(pedaço) / T_p` tira do speed-up o ganho algorítmico de dividir
(ideal `S_div = p`); `E_fraca = T_seq(n0) / T(p, N)` (ideal 1).
