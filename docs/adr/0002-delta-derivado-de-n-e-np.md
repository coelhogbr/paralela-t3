# Delta calculado a partir de N e do número de processos

O enunciado descreve o delta como um valor fixo, mas um delta que não casa com o número de processos deixa ranks sem trabalho bloqueados para sempre no `MPI_Recv` (o programa não termina). Calculamos `delta = ceil(N / folhas)`, com `folhas = (np+1)/2`, para que a árvore clássica use exatamente np processos; um `-d` explícito é aceito, mas o programa aborta no início se a árvore resultante não usar exatamente np processos.
