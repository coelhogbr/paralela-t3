#!/usr/bin/env python3
"""Figuras do relatorio do T3 (PDF vetorial + PNG para conferir na tela).

    python3 graficos.py [dir]

  grafico_escala.pdf   speed-up e eficiencia x p (1..32), um par de paineis por N
  grafico_carga.pdf    ocupacao de cada rank ao longo da execucao (p = 15/16)
  grafico_muitos.pdf   speed-up e eficiencia x p de 1 a 1024 (aumento do numero de processos)
  grafico_espera.pdf   classica p=31: HT x so fisicos, polling x yield (extra.sh)
  grafico_fraca.pdf    escalabilidade fraca: tempo e eficiencia (extra.sh)

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
    fig, eixos = plt.subplots(2, len(ns), figsize=(7.2, 4.2), squeeze=False, sharex=True)
    for col, n in enumerate(ns):
        pts = dados[n]
        procs = sorted({k[1] for k in pts if isinstance(k, tuple)})
        curvas = [("arvore", "arvore", [p for p in procs if p & (p + 1) == 0]),    # 1, 3, ..., 1023
                  ("artigo", "artigo", [p for p in procs if p & (p + 1) == 0]),
                  ("artigo2k", "artigo", [p for p in procs if p & (p - 1) == 0])]  # 1, 2, 4, ..., 1024
        for chave, versao, ps in curvas:
            xs, s, e = serie(pts, versao, ps)
            if not xs:
                continue
            estilo = dict(color=COR[chave], marker="o", label=NOME[chave])
            if chave == "artigo2k":
                estilo.update(linestyle=(0, (4, 2)))
            eixos[0][col].plot(xs, s, **estilo)
            eixos[1][col].plot(xs, e, **estilo)
        eixos[0][col].set_title(rotulo_n(n), fontsize=8, color=TINTA)
        for ax in (eixos[0][col], eixos[1][col]):
            ax.axvline(A.HW_THREADS, color=TINTA2, lw=1, ls=":")
            ax.set_xscale("log", base=2)
            ax.set_xticks([1, 4, 16, 64, 256, 1024])
            ax.set_xticklabels(["1", "4", "16", "64", "256", "1024"], fontsize=6)
            ax.minorticks_off()
            ax.set_ylim(bottom=0)
        eixos[0][col].text(A.HW_THREADS * 1.08, 0.97, "32 hw threads",
                           transform=eixos[0][col].get_xaxis_transform(),
                           fontsize=6, color=TINTA2, va="top")
        eixos[1][col].set_xlabel("processos (p)")
    eixos[0][0].set_ylabel("speed-up")
    eixos[1][0].set_ylabel("eficiência\n(S/p; S/32 acima de 32)")
    alcas, nomes = eixos[0][0].get_legend_handles_labels()
    fig.legend(alcas, nomes, loc="lower center", ncol=3, fontsize=7, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Aumento do número de processos: speed-up e eficiência de 1 a 1024 processos",
                 color=TINTA)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    salva(fig, d, "grafico_muitos")


def fig_fraca(d):
    """Escala fraca: tempo e eficiencia com n0 elementos por processo ordenador."""
    t0, n0, linhas = A.carrega_fraca(d)
    if t0 is None:
        return
    fig, (ax_t, ax_e) = plt.subplots(1, 2, figsize=(7.2, 2.6))
    for chave in ("arvore", "artigo"):
        ls = sorted((l for l in linhas if l["versao"] == chave), key=lambda l: l["processos"])
        if not ls:
            continue
        xs = [A.ordenadores(chave, l["processos"]) for l in ls]
        nome = NOME[chave] + (" (2^k)" if chave == "artigo" else "")
        ax_t.plot(xs, [l["tempo"] for l in ls], color=COR[chave], marker="o", label=nome)
        ax_e.plot(xs, [t0 / l["tempo"] for l in ls], color=COR[chave], marker="o", label=nome)
    ax_t.axhline(t0, color=TINTA2, lw=1, ls=":", label=f"ideal (sequencial de n0 = {n0:,})".replace(",", "."))
    ax_e.axhline(1, color=TINTA2, lw=1, ls=":")
    for ax in (ax_t, ax_e):
        for x, txt, y in ((16, "16 núcleos físicos", 0.97), (32, "32 hw threads", 0.86)):
            ax.axvline(x, color=TINTA2, lw=1, ls=":")
            ax.text(x * 1.06, y, txt, transform=ax.get_xaxis_transform(),
                    fontsize=6, color=TINTA2, va="top")
        ax.set_xscale("log", base=2)
        ax.set_xticks([1, 2, 4, 8, 16, 32, 64])
        ax.set_xticklabels(["1", "2", "4", "8", "16", "32", "64"])
        ax.minorticks_off()
        ax.set_ylim(bottom=0)
        ax.set_xlabel("processos ordenadores (N = n0 × ordenadores)")
    ax_t.set_ylabel("tempo (s)")
    ax_e.set_ylabel("eficiência fraca  T(n0) / T(p, N)")
    ax_t.legend(loc="upper left", fontsize=6.5, bbox_to_anchor=(0, 0.9))
    fig.suptitle("Escalabilidade fraca", color=TINTA)
    fig.tight_layout()
    salva(fig, d, "grafico_fraca")


def fig_espera(d, dados):
    """Classica p=31: HT x so nucleos fisicos, polling x yield; artigo p=16 de referencia."""
    ns = [n for n in dados if A.carrega_espera(d, n)]
    if not ns:
        return
    fig, eixos = plt.subplots(1, len(ns), figsize=(7.2, 2.7), squeeze=False)
    rotulos = {"ht-polling": "HT\npolling", "ht-yield": "HT\nyield",
               "fisico-polling": "físicos\npolling", "fisico-yield": "físicos\nyield",
               "artigo": "artigo\np = 16"}
    for ax, n in zip(eixos[0], ns):
        linhas = A.carrega_espera(d, n)
        modos = [m for m, _ in A.MODOS_ESPERA if m in linhas]
        for i, m in enumerate(modos):
            cor = COR["artigo"] if m == "artigo" else COR["arvore"]
            ax.bar(i, linhas[m]["tempo"], 0.7, color=cor, linewidth=0)
            med, _ = A.bs_ordenadores(A.carga_espera(d, n, m))
            if med is not None:
                ax.plot([i - 0.35, i + 0.35], [med, med], color=TINTA, lw=1.6)
        ax.set_axisbelow(True)
        ax.set_xticks(range(len(modos)))
        ax.set_xticklabels([rotulos[m] for m in modos], fontsize=6.5)
        ax.grid(axis="x", visible=False)
        ax.set_title(rotulo_n(n), fontsize=8, color=TINTA)
        ax.set_ylabel("tempo (s)")
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    leg = [Patch(color=COR["arvore"], label="árvore clássica, p = 31 (tempo total)"),
           Patch(color=COR["artigo"], label="árvore do artigo, p = 16 (tempo total)"),
           Line2D([], [], color=TINTA, lw=1.6, label="bubble sort médio de um processo ordenador")]
    fig.legend(handles=leg, loc="lower center", ncol=3, fontsize=7, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Espera ativa (polling) × ceder a CPU (yield), com e sem HT", color=TINTA)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    salva(fig, d, "grafico_espera")


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "resultados"
    dados = A.carrega(d)
    if not dados:
        sys.exit(f"nenhum tempos_N.csv em {d}/")
    fig_escala(d, dados)
    fig_carga(d, dados)
    fig_muitos(d, dados)
    fig_espera(d, dados)
    fig_fraca(d)


if __name__ == "__main__":
    main()
