# Enunciado do T3 (transcrito do Moodle)

O objetivo do trabalho é implementar, usando a biblioteca MPI, uma versão paralela seguindo o modelo divisão e conquista, de um código de ordenação de vetores quadrático (bubble-sort). Após implementado, o programa deve ser executado no cluster Atlantica com até 2 nós (variando de 1, 3, 7, 15 e 31 processos, este último com HT) para realização das medições de desempenho. Deve ser medida também uma versão onde o trabalho é balanceado na árvore (código do artigo no git).

O nó raiz da árvore verifica se o vetor inicial será dividido ou conquistado. A verificação da condição de conquista é uma comparação com um valor fixo; para o vetor com 40 elementos pode ser por exemplo `<= 10` (assim o algoritmo só desce 2 níveis da árvore binária e se utiliza dos 7 processadores alocados). Se for dividido, cada filho da árvore binária recebe uma metade do vetor. Por sua vez, cada filho verifica se irá conquistar ou novamente dividir o vetor. Quando as folhas decidirem que o vetor já está pequeno o bastante para ser conquistado, o vetor é ordenado com o Bubble Sort e devolvido para o respectivo pai. O pai intercala os dois vetores recebidos e devolve ao seu pai, até que a raiz restabeleça o vetor original ordenado.

Para ordenar um vetor de 1.000.000 de elementos com um processo rodando em um núcleo na Atlantica, o bubble sort precisou de 74 minutos. Para 3 processos (um raiz e dois filhos) rodando em 3 núcleos, 18 minutos.

## Itens de avaliação

- execução da versão sequencial da ordenação;
- implementação da versão paralela SPMD do algoritmo MPI do BS seguindo o modelo divisão e conquista;
- medição dos tempos de execução para a versão sequencial em um core e da versão paralela (usando 2 nós exclusivos da máquina Atlantica totalizando 15 processadores — cada nó possui 8 processadores físicos);
- cálculo do speed up e da eficiência para os casos de teste (variando de 1, 3, 7, 15 e 31 processos, este último com HT);
- análise do balanceamento da carga na execução do programa paralelo nos diferentes níveis da árvore;
- análise do ganho obtido com HT;
- análise do ganho obtido com a inclusão de um mecanismo de balanceamento de carga (aumentando o número de processos e com a versão do artigo);
- execute com mais processos (63, 127, 255, 511, 1023) e analise o desempenho obtido;
- clareza do código (utilização de comentários e nomes de variáveis adequadas).

Tamanhos do trabalho final: 10.000, 100.000 e 1.000.000.

## Código fornecido

```c
void bs(int n, int * vetor)
{
    int c=0, d, troca, trocou =1;
    while (c < (n-1) & trocou )
    {
        trocou = 0;
        for (d = 0 ; d < n - c - 1; d++)
            if (vetor[d] > vetor[d+1])
            {
                troca      = vetor[d];
                vetor[d]   = vetor[d+1];
                vetor[d+1] = troca;
                trocou = 1;
            }
        c++;
    }
}

/* recebe um ponteiro para um vetor que contem as mensagens recebidas dos filhos e */
/* intercala estes valores em um terceiro vetor auxiliar. Devolve um ponteiro para este vetor */
int *interleaving(int vetor[], int tam)
{
    int *vetor_auxiliar;
    int i1, i2, i_aux;
    vetor_auxiliar = (int *)malloc(sizeof(int) * tam);
    i1 = 0;
    i2 = tam / 2;
    for (i_aux = 0; i_aux < tam; i_aux++) {
        if (((vetor[i1] <= vetor[i2]) && (i1 < (tam / 2)))
            || (i2 == tam))
            vetor_auxiliar[i_aux] = vetor[i1++];
        else
            vetor_auxiliar[i_aux] = vetor[i2++];
    }
    return vetor_auxiliar;
}
```

## Pseudocódigo

```
MPI_Init();
my_rank = MPI_Comm_rank();

// recebo vetor
if ( my_rank != 0 ) {
    MPI_Recv ( vetor, pai );                       // não sou a raiz, tenho pai
    MPI_Get_count(&Status, MPI_INT, &tam_vetor);   // descubro tamanho da mensagem recebida
} else {
    tam_vetor = VETOR_SIZE;                        // defino tamanho inicial do vetor
    Inicializa ( vetor, tam_vetor );               // sou a raiz: gero o vetor em ordem reversa
}

// dividir ou conquistar?
if ( tam_vetor <= delta )
    BubbleSort (vetor);                            // conquisto
else {
    // dividir: quebrar em duas partes e mandar para os filhos
    MPI_Send ( &vetor[0], filho esquerda, tam_vetor/2 );            // metade inicial
    MPI_Send ( &vetor[tam_vetor/2], filho direita, tam_vetor/2 );   // metade final
    // receber dos filhos
    MPI_Recv ( &vetor[0], filho esquerda );
    MPI_Recv ( &vetor[tam_vetor/2], filho direita );
    // intercalo vetor inteiro
    Intercala ( vetor );
}

// mando para o pai
if ( my_rank != 0 )
    MPI_Send ( vetor, pai, tam_vetor );            // tenho pai, retorno vetor ordenado
else
    Mostra ( vetor );                              // sou a raiz, mostro vetor
MPI_Finalize();
```

## Versão com balanceamento (artigo)

A. Radenski, *Shared Memory, Message Passing, and Hybrid Merge Sorts for Standalone and Clustered SMPs*, PDPTA'11, pp. 367-373. Código: https://github.com/gary-funck/parallel-merge-sort (`mpi_mergesort.c`).
