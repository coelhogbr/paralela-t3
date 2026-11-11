# Ordenação por divisão e conquista em MPI (T3)

Ordenação de um vetor pelo modelo divisão e conquista, com processos MPI organizados numa árvore binária.

## Árvore de processos

**Árvore clássica**:
Árvore em que cada processo divide o vetor entre dois filhos e só intercala o que recebe de volta; apenas as folhas ordenam. É a do pseudocódigo do enunciado.
_Avoid_: versão normal, versão sem balanceamento

**Árvore do artigo**:
Árvore do Radenski (PDPTA'11) em que cada processo fica com uma metade e envia a outra a um ajudante, de modo que todo processo, inclusive os internos, também ordena.
_Avoid_: versão balanceada, versão do git

**Nó interno**:
Processo que divide o vetor e intercala as metades devolvidas.
_Avoid_: pai (quando o papel na árvore é o que importa)

**Folha**:
Processo que conquista: recebe um pedaço pequeno o bastante e o ordena.

**Nível**:
Distância de um processo à raiz na árvore; a raiz (rank 0) está no nível 0.

## Operações

**Dividir**:
Partir o vetor em duas metades e enviá-las aos filhos.

**Conquistar**:
Ordenar localmente um pedaço com bubble sort.

**Intercalar**:
Juntar duas metades já ordenadas num único vetor ordenado.
_Avoid_: merge, mesclar

**Delta**:
Tamanho máximo de pedaço que um processo conquista em vez de dividir.
_Avoid_: limiar, threshold

## Medição

**Sequencial**:
Bubble sort do vetor inteiro num único núcleo, sem MPI; é a base do speed-up.
_Avoid_: versão com 1 processo

**Processo ordenador**:
Processo que conquista algum pedaço: só as folhas na árvore clássica; todos os processos na árvore do artigo.
_Avoid_: trabalhador, worker

**Balanceamento por aumento do número de processos**:
Mitigação do desbalanceamento da árvore clássica sem alterar o código: rodar mais processos que núcleos físicos para que as folhas ocupem os núcleos que os nós internos, só esperando, deixariam ociosos.
_Avoid_: balanceamento por excesso de processos

**Speed-up sobre a mesma divisão** (S_div):
Speed-up em relação a ordenar sequencialmente os mesmos pedaços que a execução paralela ordenou; tira do speed-up o ganho de dividir um algoritmo quadrático e deixa só o do paralelismo (ideal: p).
_Avoid_: speed-up corrigido, speed-up real

**Escalabilidade forte**:
Como o tempo cai ao aumentar os processos com N fixo; medida pelo speed-up e pela eficiência em relação ao sequencial.

**Escalabilidade fraca**:
Como o tempo varia quando N cresce junto com os processos ordenadores, mantendo fixo o pedaço de cada um (n₀); o ideal é tempo constante.
_Avoid_: speed-up escalado
