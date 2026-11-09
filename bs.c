/*
 * Trabalho 3 - Programacao Paralela - Grupo 20 (cp32020)
 * Bubble sort por divisao e conquista em MPI.
 *
 * Um unico fonte gera os dois binarios:
 *   gcc   bs.c             -> bs_seq  (bubble sort do vetor inteiro, base do speed-up)
 *   mpicc -DPARALELO bs.c  -> bs_mpi  (duas arvores de processos, escolhidas com -v)
 *
 *   -v arvore  arvore classica (pseudocodigo do enunciado): os nos internos so
 *              dividem e intercalam; apenas as folhas ordenam.
 *   -v artigo  arvore do artigo (Radenski, PDPTA'11): cada processo fica com uma
 *              metade e envia a outra a um ajudante (rank + 2^nivel), de modo que
 *              todos os processos, inclusive os internos, tambem ordenam.
 *              Usa o MESMO bubble sort e a MESMA intercalacao da arvore classica
 *              (docs/adr/0001).
 *
 * Opcoes:
 *   -n N        tamanho do vetor (padrao 40)
 *   -v versao   arvore | artigo (so no bs_mpi; padrao arvore)
 *   -d delta    maior pedaco conquistado na arvore classica (padrao: calculado
 *               para que a arvore use exatamente np processos; docs/adr/0002)
 *   -b arquivo  acrescenta ao arquivo uma linha de carga por rank (CSV)
 *   -m          mostra o vetor antes e depois (so para N pequeno)
 *
 * Saida (stdout, uma linha CSV):  versao;processos;n;delta;tempo;ok
 *   ok = 1 se o vetor terminou ordenado (como a entrada e N, N-1, ..., 1,
 *   o resultado correto e exatamente 1, 2, ..., N).
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#ifdef PARALELO
#include <mpi.h>
#endif

/* ------------------------------------------------------------------------ */
/* Ordenacao e intercalacao (codigo do enunciado, com correcoes)             */
/* ------------------------------------------------------------------------ */

/* Bubble sort do enunciado; para assim que uma passada nao troca nada. */
static void bs(int n, int *vetor)
{
    int c = 0, d, troca, trocou = 1;

    while (c < (n - 1) && trocou) {
        trocou = 0;
        for (d = 0; d < n - c - 1; d++)
            if (vetor[d] > vetor[d + 1]) {
                troca        = vetor[d];
                vetor[d]     = vetor[d + 1];
                vetor[d + 1] = troca;
                trocou = 1;
            }
        c++;
    }
}

#ifdef PARALELO   /* a versao sequencial ordena o vetor inteiro, sem intercalar */
/*
 * Rotina de intercalacao do enunciado: as duas metades ordenadas ficam em
 * vetor[0, tam/2) e vetor[tam/2, tam); devolve um vetor novo com o resultado.
 * Correcao: o limite (i2 == tam, i1 < tam/2) e testado ANTES de ler o vetor;
 * no original, vetor[i2] era lido com i2 == tam (uma posicao alem do fim).
 */
static int *interleaving(const int vetor[], int tam)
{
    int *vetor_auxiliar = malloc(sizeof(int) * (size_t)tam);
    int meio = tam / 2;
    int i1 = 0, i2 = meio, i_aux;

    if (vetor_auxiliar == NULL) {
        fprintf(stderr, "erro: sem memoria para intercalar %d inteiros\n", tam);
        exit(1);
    }
    for (i_aux = 0; i_aux < tam; i_aux++) {
        if (i2 == tam || (i1 < meio && vetor[i1] <= vetor[i2]))
            vetor_auxiliar[i_aux] = vetor[i1++];
        else
            vetor_auxiliar[i_aux] = vetor[i2++];
    }
    return vetor_auxiliar;
}

/* Intercala as duas metades e devolve o resultado no proprio vetor
 * (copia de volta e libera o auxiliar, que no original vazava). */
static void intercala(int vetor[], int tam)
{
    int *vetor_auxiliar = interleaving(vetor, tam);
    memcpy(vetor, vetor_auxiliar, sizeof(int) * (size_t)tam);
    free(vetor_auxiliar);
}
#endif

/* ------------------------------------------------------------------------ */
/* Utilitarios                                                              */
/* ------------------------------------------------------------------------ */

static int *aloca(int n)
{
    int *v = malloc(sizeof(int) * (size_t)(n > 0 ? n : 1));
    if (v == NULL) {
        fprintf(stderr, "erro: sem memoria para %d inteiros\n", n);
        exit(1);
    }
    return v;
}

/* Pior caso do bubble sort: ordem decrescente N, N-1, ..., 1. */
static void inicializa(int *vetor, int n)
{
    for (int i = 0; i < n; i++)
        vetor[i] = n - i;
}

/* 1 se o vetor e exatamente 1, 2, ..., N (ordenado e sem perda de elementos). */
static int confere(const int *vetor, int n)
{
    for (int i = 0; i < n; i++)
        if (vetor[i] != i + 1)
            return 0;
    return 1;
}

static void mostra(const char *rotulo, const int *vetor, int n)
{
    printf("%s:", rotulo);
    for (int i = 0; i < n; i++)
        printf(" [%03d]", vetor[i]);
    printf("\n");
}

typedef struct {
    int n, delta, mostrar;
    const char *versao, *arquivo_carga;
} Opcoes;

static Opcoes le_opcoes(int argc, char **argv)
{
    Opcoes o = { 40, 0, 0, "arvore", NULL };
    int c;
    while ((c = getopt(argc, argv, "n:v:d:b:m")) != -1) {
        switch (c) {
        case 'n': o.n = atoi(optarg); break;
        case 'v': o.versao = optarg; break;
        case 'd': o.delta = atoi(optarg); break;
        case 'b': o.arquivo_carga = optarg; break;
        case 'm': o.mostrar = 1; break;
        default:
            fprintf(stderr, "uso: %s [-n N] [-v arvore|artigo] [-d delta] "
                            "[-b carga.csv] [-m]\n", argv[0]);
            exit(1);
        }
    }
    if (o.n < 1) {
        fprintf(stderr, "erro: N deve ser positivo\n");
        exit(1);
    }
    return o;
}

#ifndef PARALELO
/* ======================================================================== */
/* Versao sequencial                                                         */
/* ======================================================================== */

static double agora(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

int main(int argc, char **argv)
{
    Opcoes o = le_opcoes(argc, argv);
    int *vetor = aloca(o.n);

    inicializa(vetor, o.n);
    if (o.mostrar) mostra("Vetor", vetor, o.n);

    double inicio = agora();
    bs(o.n, vetor);                               /* so a ordenacao e medida */
    double tempo = agora() - inicio;

    if (o.mostrar) mostra("Vetor", vetor, o.n);
    int ok = confere(vetor, o.n);
    printf("seq;1;%d;%d;%.6f;%d\n", o.n, o.n, tempo, ok);
    free(vetor);
    return ok ? 0 : 2;
}

#else
/* ======================================================================== */
/* Versao paralela                                                           */
/* ======================================================================== */

#define TAG 1

/*
 * Carga de um rank, para a analise do balanceamento por nivel da arvore.
 * Instantes medidos a partir do MPI_Barrier que antecede a ordenacao.
 */
typedef struct {
    double nivel;       /* nivel do rank na arvore (raiz = 0)                    */
    double filhos;      /* quantos processos receberam parte do vetor deste rank */
    double recebido;    /* tamanho do pedaco que o rank recebeu                  */
    double conquistado; /* tamanho do pedaco que o rank ordenou (0: so intercala) */
    double inicio;      /* quando o pedaco chegou (raiz: 0)                      */
    double t_bs;        /* tempo no bubble sort (conquista)                      */
    double t_intercala; /* tempo intercalando                                    */
    double t_envio;     /* tempo nos envios (aos filhos e ao pai)                */
    double t_espera;    /* tempo bloqueado esperando a resposta dos filhos       */
    double fim;         /* quando o rank terminou seu papel                      */
} Carga;
#define CAMPOS_CARGA ((int)(sizeof(Carga) / sizeof(double)))

static double t0;   /* instante comum de partida (logo apos o MPI_Barrier) */

/* ------------------------------ arvore classica ------------------------- */
/*
 * Numeracao de heap: filhos de r sao 2r+1 e 2r+2; pai de r e (r-1)/2.
 * Simula a divisao do vetor para saber quais ranks a arvore usara com este
 * delta. Devolve quantos nos a arvore tem e, em *maior, o maior rank usado.
 */
static int conta_nos(int rank, int tam, int delta, int *maior)
{
    if (rank > *maior) *maior = rank;
    if (tam <= delta) return 1;
    return 1 + conta_nos(2 * rank + 1, tam / 2, delta, maior)
             + conta_nos(2 * rank + 2, tam - tam / 2, delta, maior);
}

static int nivel_heap(int rank)
{
    int nivel = 0;
    while ((1 << (nivel + 1)) - 1 <= rank) nivel++;
    return nivel;
}

/* Executa o papel deste rank na arvore classica. Na raiz, vetor ja contem os
 * dados e, ao final, contem o resultado; nos demais ranks, vetor e NULL. */
static void arvore_classica(int *vetor, int n, int delta, int my_rank, Carga *c)
{
    MPI_Status status;
    int tam_vetor;
    double t;

    c->nivel = nivel_heap(my_rank);

    /* recebo vetor */
    if (my_rank != 0) {
        int pai = (my_rank - 1) / 2;
        MPI_Probe(pai, TAG, MPI_COMM_WORLD, &status);   /* nao sou a raiz, tenho pai */
        MPI_Get_count(&status, MPI_INT, &tam_vetor);    /* descubro o tamanho        */
        vetor = aloca(tam_vetor);
        MPI_Recv(vetor, tam_vetor, MPI_INT, pai, TAG, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    } else {
        tam_vetor = n;                                  /* sou a raiz: vetor inteiro */
    }
    c->recebido = tam_vetor;
    c->inicio = MPI_Wtime() - t0;

    /* dividir ou conquistar? */
    if (tam_vetor <= delta) {
        c->conquistado = tam_vetor;
        t = MPI_Wtime();
        bs(tam_vetor, vetor);                           /* conquisto */
        c->t_bs = MPI_Wtime() - t;
    } else {
        /* divido: metade inicial para a esquerda, metade final para a direita.
         * Correcao: com tam_vetor impar, a direita leva o elemento a mais (no
         * pseudocodigo as duas metades tinham tam_vetor/2 e um elemento sumia). */
        int meio = tam_vetor / 2;
        int esq = 2 * my_rank + 1, dir = 2 * my_rank + 2;
        c->filhos = 2;

        t = MPI_Wtime();
        MPI_Send(&vetor[0],    meio,             MPI_INT, esq, TAG, MPI_COMM_WORLD);
        MPI_Send(&vetor[meio], tam_vetor - meio, MPI_INT, dir, TAG, MPI_COMM_WORLD);
        c->t_envio += MPI_Wtime() - t;

        /* recebo dos filhos, cada metade de volta ao seu lugar */
        t = MPI_Wtime();
        MPI_Recv(&vetor[0],    meio,             MPI_INT, esq, TAG, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        MPI_Recv(&vetor[meio], tam_vetor - meio, MPI_INT, dir, TAG, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        c->t_espera = MPI_Wtime() - t;

        t = MPI_Wtime();
        intercala(vetor, tam_vetor);                    /* intercalo o vetor inteiro */
        c->t_intercala = MPI_Wtime() - t;
    }

    /* mando para o pai */
    if (my_rank != 0) {
        t = MPI_Wtime();
        MPI_Send(vetor, tam_vetor, MPI_INT, (my_rank - 1) / 2, TAG, MPI_COMM_WORLD);
        c->t_envio += MPI_Wtime() - t;
        free(vetor);
    }
    c->fim = MPI_Wtime() - t0;
}

/* ------------------------------ arvore do artigo ------------------------ */
/*
 * Nivel em que o rank aparece pela primeira vez na arvore do artigo: o menor
 * nivel l com 2^l > rank (my_topmost_level_mpi do artigo). A raiz esta no 0.
 */
static int nivel_topo(int rank)
{
    int nivel = 0;
    while ((1 << nivel) <= rank) nivel++;
    return nivel;
}

/* mergesort_parallel_mpi do artigo, com bubble sort no caso base. Enquanto
 * houver ajudante (rank + 2^nivel < np), manda a metade final a ele e segue
 * dividindo a metade inicial; sem ajudante, conquista o que sobrou. */
static void artigo_recursivo(int *vetor, int tam, int nivel, int my_rank, int np, Carga *c)
{
    int ajudante = my_rank + (1 << nivel);
    double t;

    if (ajudante >= np) {                       /* sem mais processos: conquisto */
        c->conquistado = tam;
        t = MPI_Wtime();
        bs(tam, vetor);
        c->t_bs = MPI_Wtime() - t;
        return;
    }

    int meio = tam / 2;
    MPI_Request pedido;
    c->filhos += 1;

    /* metade final ao ajudante, assincrono: ordeno a minha enquanto ela viaja */
    t = MPI_Wtime();
    MPI_Isend(&vetor[meio], tam - meio, MPI_INT, ajudante, TAG, MPI_COMM_WORLD, &pedido);
    c->t_envio += MPI_Wtime() - t;

    artigo_recursivo(vetor, meio, nivel + 1, my_rank, np, c);

    t = MPI_Wtime();
    MPI_Wait(&pedido, MPI_STATUS_IGNORE);
    c->t_envio += MPI_Wtime() - t;

    /* metade final ordenada de volta */
    t = MPI_Wtime();
    MPI_Recv(&vetor[meio], tam - meio, MPI_INT, ajudante, TAG, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    c->t_espera += MPI_Wtime() - t;

    t = MPI_Wtime();
    intercala(vetor, tam);
    c->t_intercala += MPI_Wtime() - t;
}

static void arvore_artigo(int *vetor, int n, int my_rank, int np, Carga *c)
{
    int nivel = nivel_topo(my_rank);
    int tam = n, pai = 0;
    double t;

    c->nivel = nivel;
    if (my_rank != 0) {
        /* como no run_helper_mpi do artigo: o pai e quem mandar primeiro */
        MPI_Status status;
        MPI_Probe(MPI_ANY_SOURCE, TAG, MPI_COMM_WORLD, &status);
        MPI_Get_count(&status, MPI_INT, &tam);
        pai = status.MPI_SOURCE;
        vetor = aloca(tam);
        MPI_Recv(vetor, tam, MPI_INT, pai, TAG, MPI_COMM_WORLD, MPI_STATUS_IGNORE);
    }
    c->recebido = tam;
    c->inicio = MPI_Wtime() - t0;

    artigo_recursivo(vetor, tam, nivel, my_rank, np, c);

    if (my_rank != 0) {
        t = MPI_Wtime();
        MPI_Send(vetor, tam, MPI_INT, pai, TAG, MPI_COMM_WORLD);
        c->t_envio += MPI_Wtime() - t;
        free(vetor);
    }
    c->fim = MPI_Wtime() - t0;
}

/* ------------------------------ programa principal ---------------------- */

static void grava_carga(const char *arquivo, const char *versao, int np, int n,
                        const Carga *todas)
{
    FILE *f = fopen(arquivo, "a");
    if (f == NULL) {
        perror(arquivo);
        return;
    }
    for (int r = 0; r < np; r++) {
        const Carga *c = &todas[r];
        fprintf(f, "%s;%d;%d;%d;%d;%d;%d;%d;%.6f;%.6f;%.6f;%.6f;%.6f;%.6f\n",
                versao, np, n, r, (int)c->nivel, (int)c->filhos, (int)c->recebido,
                (int)c->conquistado,
                c->inicio, c->t_bs, c->t_intercala, c->t_envio, c->t_espera, c->fim);
    }
    fclose(f);
}

int main(int argc, char **argv)
{
    int my_rank, np;

    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &my_rank);
    MPI_Comm_size(MPI_COMM_WORLD, &np);

    Opcoes o = le_opcoes(argc, argv);
    int classica = strcmp(o.versao, "arvore") == 0;
    if (!classica && strcmp(o.versao, "artigo") != 0) {
        if (my_rank == 0) fprintf(stderr, "erro: versao deve ser arvore ou artigo\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    /* Delta da arvore classica: com folhas = (np+1)/2, ceil(N/folhas) faz a
     * arvore descer exatamente ate usar np processos. Todos os ranks fazem a
     * mesma conta; se a arvore nao usar exatamente os ranks 0..np-1, aborta
     * em vez de deixar processos esperando para sempre por um vetor. */
    int delta = o.n;
    if (classica) {
        int folhas = (np + 1) / 2;
        delta = o.delta > 0 ? o.delta : (o.n + folhas - 1) / folhas;
        int maior = 0;
        int nos = conta_nos(0, o.n, delta, &maior);
        if (nos != np || maior != np - 1) {
            if (my_rank == 0)
                fprintf(stderr, "erro: com N=%d e delta=%d a arvore classica usa %d "
                        "processos (maior rank %d), mas ha %d. Use np = 2^k - 1 "
                        "ou ajuste -d.\n", o.n, delta, nos, maior, np);
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
    }

    int *vetor = NULL;
    if (my_rank == 0) {                          /* sou a raiz: gero o vetor */
        vetor = aloca(o.n);
        inicializa(vetor, o.n);
        if (o.mostrar) mostra("Vetor", vetor, o.n);
    }

    Carga carga;
    memset(&carga, 0, sizeof carga);

    MPI_Barrier(MPI_COMM_WORLD);                 /* todos partem juntos */
    t0 = MPI_Wtime();
    if (classica)
        arvore_classica(vetor, o.n, delta, my_rank, &carga);
    else
        arvore_artigo(vetor, o.n, my_rank, np, &carga);
    double tempo = MPI_Wtime() - t0;             /* so vale na raiz */

    /* Fora da medicao: a raiz junta a carga de todos os ranks. Todos os ranks
     * leem as mesmas opcoes, entao todos entram (ou nao) no MPI_Gather. */
    Carga *todas = NULL;
    if (o.arquivo_carga) {
        if (my_rank == 0)
            todas = malloc(sizeof(Carga) * (size_t)np);
        MPI_Gather(&carga, CAMPOS_CARGA, MPI_DOUBLE,
                   todas, CAMPOS_CARGA, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    }

    int ok = 1;
    if (my_rank == 0) {                          /* sou a raiz: mostro e confiro */
        if (o.mostrar) mostra("Vetor", vetor, o.n);
        ok = confere(vetor, o.n);
        printf("%s;%d;%d;%d;%.6f;%d\n", o.versao, np, o.n, delta, tempo, ok);
        fflush(stdout);
        if (todas) {
            grava_carga(o.arquivo_carga, o.versao, np, o.n, todas);
            free(todas);
        }
        free(vetor);
    }

    MPI_Finalize();
    return ok ? 0 : 2;
}
#endif
