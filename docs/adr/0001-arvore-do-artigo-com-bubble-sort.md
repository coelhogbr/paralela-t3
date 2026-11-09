# Árvore do artigo reimplementada com bubble sort, não o mpi_mergesort.c original

O enunciado pede medir "a versão do artigo (código no git)", mas o `mpi_mergesort.c` do Radenski conquista com mergesort/insertion sort (O(n log n)) e vetor aleatório. Compará-lo à árvore clássica com bubble sort (O(n²)) mediria o algoritmo, não o balanceamento. Por isso reaproveitamos apenas o esquema de árvore do artigo (cada processo fica com uma metade e manda a outra a `rank + 2^nível`) e usamos o mesmo bubble sort, a mesma intercalação e a mesma entrada (ordem reversa) da árvore clássica.
