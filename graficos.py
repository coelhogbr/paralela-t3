#!/usr/bin/env python3
"""Figuras do relatorio do T3 (PDF vetorial + PNG para conferir na tela).

    python3 graficos.py [dir]

  grafico_escala.pdf   speed-up e eficiencia x p (1..32), um par de paineis por N
  grafico_carga.pdf    ocupacao de cada rank ao longo da execucao (p = 15/16)
  grafico_muitos.pdf   speed-up x p de 1 a 1023 (excesso de processos)
  grafico_ht.pdf       ganho de 15 -> 31 processos e ganho isolado do HT

Usa as mesmas contas do analisar.py. Cores: paleta categorica de referencia
(slots fixos: arvore = azul, artigo = laranja, artigo 2^k = verde-agua), sempre
com legenda; speed-up e eficiencia em paineis separados (nunca eixo duplo).
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import analisar as A

COR = {"arvore": "#2a78d6", "artigo": "#eb6834", "artigo2k": "#1baf7a",
       "intercala": "#eb6834", "envio": "#1baf7a"}
NOME = {"arvore": "árvore clássica", "artigo": "árvore do artigo",
        "artigo2k": "árvore do artigo (2^k)"}
TINTA, TINTA2, GRADE, OCIOSO = "#0b0b0b", "#52514e", "#e4e3df", "#d9d8d3"

plt.rcParams.update({
    "font.size": 8, "axes.edgecolor": TINTA2, "axes.labelcolor": TINTA,
    "xtick.color": TINTA2, "ytick.color": TINTA2, "axes.grid": True,
    "grid.color": GRADE, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "lines.linewidth": 2,
    "lines.markersize": 4.5, "savefig.bbox": "tight",
})


def salva(fig, d, nome):
    fig.savefig(os.path.join(d, nome + ".pdf"))
    fig.savefig(os.path.join(d, nome + ".png"), dpi=150)
    plt.close(fig)
    print("gerado", os.path.join(d, nome + ".pdf"))


def serie(pts, versao, procs):
    xs, s, e = [], [], []
    for p in procs:
        r = A.speedup(pts, versao, p)
        if r:
            xs.append(p); s.append(r[1]); e.append(r[2])
    return xs, s, e


def rotulo_n(n):
    return f"N = {n:,}".replace(",", ".")


def fig_escala(d, dados):
    ns = list(dados)
    fig, eixos = plt.subplots(len(ns), 2, figsize=(7.2, 2.3 * len(ns)), squeeze=False)
    for i, n in enumerate(ns):
        pts = dados[n]
        curvas = [("arvore", "arvore", A.PROCS_BASE), ("artigo", "artigo", A.PROCS_BASE),
                  ("artigo2k", "artigo", A.PROCS_2K)]
        for chave, versao, procs in curvas:
            xs, s, e = serie(pts, versao, procs)
            if not xs:
                continue
            estilo = dict(color=COR[chave], marker="o", label=NOME[chave])
            if chave == "artigo2k":
                estilo.update(linestyle=(0, (4, 2)))
            eixos[i][0].plot(xs, s, **estilo)
            eixos[i][1].plot(xs, e, **estilo)
        eixos[i][0].plot([1, 32], [1, 32], color=TINTA2, lw=1, ls=":", label="linear (S = p)")
        eixos[i][1].axhline(1, color=TINTA2, lw=1, ls=":")
        eixos[i][0].set_ylabel(f"{rotulo_n(n)}\nspeed-up")
        eixos[i][1].set_ylabel("eficiência (S/p)")
        for ax in eixos[i]:
            ax.set_xscale("log", base=2)
            # so a serie 2^k-1 rotulada: 15|16 e 31|32 se sobrepoem em escala log
            ax.set_xticks([1, 3, 7, 15, 31])
            ax.set_xticklabels(["1", "3", "7", "15", "31"])
            ax.minorticks_off()
            ax.set_ylim(bottom=0)
    for ax in eixos[-1]:
        ax.set_xlabel("processos (p)")
    eixos[0][0].legend(loc="upper left", fontsize=7)
    fig.suptitle("Speed-up e eficiência em relação ao bubble sort sequencial", color=TINTA)
    fig.tight_layout()
    salva(fig, d, "grafico_escala")


def fig_carga(d, dados):
    n = max(dados)              # o maior N medido mostra melhor o desbalanceamento
    casos = [("arvore", 15), ("artigo", 15), ("artigo", 16)]
    casos = [(v, p, A.carga_por_rank(d, n, v, p)) for v, p in casos]
    casos = [c for c in casos if c[2]]
    if not casos:
        return
    fig, eixos = plt.subplots(1, len(casos), figsize=(7.2, 3.4), squeeze=False, sharex=True)
    for ax, (v, p, ranks) in zip(eixos[0], casos):
        total = ranks[0]["fim"]
        ordem = sorted(ranks, key=lambda r: (r["nivel"], r["rank"]))
        for y, r in enumerate(ordem):
            partes = [(r["bs"], COR["arvore"]), (r["intercala"], COR["intercala"]),
                      (r["envio"], COR["envio"])]
            esq = 0.0
            ax.barh(y, 100, color=OCIOSO, height=0.75, linewidth=0)   # fundo = esperando
            for t, cor in partes:
                w = 100 * t / total
                ax.barh(y, w, left=esq, color=cor, height=0.75, edgecolor="white", linewidth=0.5)
                esq += w
        ax.set_yticks(range(len(ordem)))
        ax.set_yticklabels([f"r{r['rank']} (nív. {r['nivel']})" for r in ordem], fontsize=6)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.grid(axis="y", visible=False)
        ax.set_title(f"{NOME[v]}, p = {p}", fontsize=8, color=TINTA)
        ax.set_xlabel("% do tempo total")
    from matplotlib.patches import Patch
    leg = [Patch(color=COR["arvore"], label="bubble sort"),
           Patch(color=COR["intercala"], label="intercalação"),
           Patch(color=COR["envio"], label="envio"),
           Patch(color=OCIOSO, label="esperando (pai ou filhos) / terminado")]
    fig.legend(handles=leg, loc="lower center", ncol=4, fontsize=7, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle(f"Ocupação de cada processo, {rotulo_n(n)}", color=TINTA)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    salva(fig, d, "grafico_carga")


def fig_muitos(d, dados):
    ns = list(dados)
    fig, eixos = plt.subplots(1, len(ns), figsize=(7.2, 2.5), squeeze=False)
    for ax, n in zip(eixos[0], ns):
        pts = dados[n]
        procs = sorted({k[1] for k in pts if isinstance(k, tuple)})
        for chave in ("arvore", "artigo"):
            ps = [p for p in procs if p == 1 or (p + 1) & p == 0]   # 1, 3, 7, ..., 1023
            xs, s, _ = serie(pts, chave, ps)
            if xs:
                ax.plot(xs, s, color=COR[chave], marker="o", label=NOME[chave])
        ax.axvline(A.HW_THREADS, color=TINTA2, lw=1, ls=":")
        ax.text(A.HW_THREADS * 1.08, 0.97, "32 hw threads", transform=ax.get_xaxis_transform(),
                fontsize=6, color=TINTA2, va="top")
        ax.set_xscale("log", base=2)
        ax.set_xticks([1, 3, 7, 15, 31, 63, 127, 255, 511, 1023])
        ax.set_xticklabels(["1", "3", "7", "15", "31", "63", "127", "255", "511", "1023"],
                           fontsize=6, rotation=45)
        ax.minorticks_off()
        ax.set_ylim(bottom=0)
        ax.set_title(rotulo_n(n), fontsize=8, color=TINTA)
        ax.set_xlabel("processos (p)")
    eixos[0][0].set_ylabel("speed-up")
    alcas, nomes = eixos[0][0].get_legend_handles_labels()
    fig.legend(alcas, nomes, loc="lower center", ncol=2, fontsize=7, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("Excesso de processos: speed-up de 1 a 1023 processos", color=TINTA)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    salva(fig, d, "grafico_muitos")


def fig_ht(d, dados):
    ns = list(dados)
    rotulos, ganho_p, ganho_ht = [], [], []
    for n in ns:
        ht = A.carrega_ht(d, n)
        for v in ("arvore", "artigo"):
            t15, t31 = dados[n].get((v, 15)), dados[n].get((v, 31))
            th, tf = ht.get(("ht", v)), ht.get(("fisico", v))
            rotulos.append(f"{NOME[v]}\n{rotulo_n(n)}")
            ganho_p.append(t15["tempo"] / t31["tempo"] if t15 and t31 else 0)
            ganho_ht.append(tf / th if th and tf else 0)
    if not rotulos:
        return
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    x = range(len(rotulos))
    larg = 0.38
    ax.bar([i - larg / 2 - 0.01 for i in x], ganho_p, larg, color=COR["arvore"],
           label="15 → 31 processos (árvore maior + HT)")
    ax.bar([i + larg / 2 + 0.01 for i in x], ganho_ht, larg, color=COR["artigo"],
           label="só HT: 31 em hw threads × 31 em núcleos físicos")
    ax.axhline(1, color=TINTA2, lw=1, ls=":")
    ax.set_xticks(list(x))
    ax.set_xticklabels(rotulos, fontsize=6)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("ganho (tempo antes / tempo depois)")
    ax.legend(loc="lower center", ncol=2, fontsize=7, bbox_to_anchor=(0.5, 1.0))
    ax.set_title("Ganho com hyper-threading", color=TINTA, pad=22)
    fig.tight_layout()
    salva(fig, d, "grafico_ht")


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "resultados"
    dados = A.carrega(d)
    if not dados:
        sys.exit(f"nenhum tempos_N.csv em {d}/")
    fig_escala(d, dados)
    fig_carga(d, dados)
    fig_muitos(d, dados)
    fig_ht(d, dados)


if __name__ == "__main__":
    main()
