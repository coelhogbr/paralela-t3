# Trabalho 3 - Computacao Paralela - Grupo 20
# Mesmo fonte, mesmas flags: a versao MPI so acrescenta -DPARALELO e o mpicc.

CC      = gcc
MPICC   = mpicc
CFLAGS  = -O2 -Wall -Wextra -std=gnu11
MPIRUN  = mpirun --oversubscribe

all: bs_seq bs_mpi

bs_seq: bs.c
	$(CC) $(CFLAGS) -o $@ $<

bs_mpi: bs.c
	$(MPICC) $(CFLAGS) -DPARALELO -o $@ $<

# Corretude: o ultimo campo (ok) tem de ser 1 em todas as execucoes.
# N impar (1001) exercita as metades desiguais; N=37 forca pedacos minusculos.
# Por fim, np=5 na arvore classica tem de ABORTAR (arvore incompleta), nao travar.
teste: all
	@./bs_seq -n 1001 | grep -q ';1$$' && echo "OK   seq" || { echo "FALHOU seq"; exit 1; }
	@for n in 1001 37; do \
	  for np in 1 3 7 15; do \
	    $(MPIRUN) -np $$np ./bs_mpi -v arvore -n $$n | grep -q ';1$$' \
	      && echo "OK   arvore np=$$np n=$$n" || { echo "FALHOU arvore np=$$np n=$$n"; exit 1; }; \
	  done; \
	  for np in 1 2 3 4 5 7 8 13 16; do \
	    $(MPIRUN) -np $$np ./bs_mpi -v artigo -n $$n | grep -q ';1$$' \
	      && echo "OK   artigo np=$$np n=$$n" || { echo "FALHOU artigo np=$$np n=$$n"; exit 1; }; \
	  done; \
	done
	@if timeout 30 $(MPIRUN) -np 5 ./bs_mpi -v arvore -n 1001 >/dev/null 2>&1; then \
	  echo "FALHOU: np=5 na arvore classica deveria abortar"; exit 1; \
	else echo "OK   arvore np=5 aborta (arvore incompleta)"; fi

clean:
	rm -f bs_seq bs_mpi

.PHONY: all teste clean
