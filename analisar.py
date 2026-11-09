#!/usr/bin/env python3
"""Tabelas do T3 a partir de resultados/ (ou do diretorio dado).

    python3 analisar.py [dir]

Le tempos_N.csv, carga_N.csv e ht_N.csv de cada tamanho N ja medido e
imprime: escala (speed-up e eficiencia), excesso de processos, HT e
balanceamento por nivel da arvore. Grava tambem tab_*.tex, que o relatorio
inclui sozinho. So usa a biblioteca padrao (o no do cluster pode nao ter pandas).

Definicoes (decididas no planejamento):
  S(p) = T_seq / T(p)
  E(p) = S(p) / p           para p <= 32 (conta todos os processos, inclusive
                            os nos internos ociosos: e isso que se quer ver)
  E_hw = S(p) / 32          para p > 32: ha mais processos que as 32 hardware
                            threads dos 2 nos, entao S/p perde o sentido.
"""
import csv
import glob
import os
import re
import sys
from collections import defaultdict
from statistics import mean

HW_THREADS = 32           # 2 nos x 16 hardware threads
PROCS_BASE = [1, 3, 7, 15, 31]
PROCS_2K = [2, 4, 8, 16, 32]
PROCS_CARGA = [7, 15, 31]


def le_csv(caminho):
    with open(caminho, newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def tamanhos(d):
    """Valores de N com tempos medidos, em ordem crescente."""
    ns = []
    for c in glob.glob(os.path.join(d, "tempos_*.csv")):
        m = re.search(r"tempos_(\d+)\.csv$", c)
        if m:
            ns.append(int(m.group(1)))
    return sorted(ns)


def carrega(d):
    """{N: {"seq": T, ("arvore"|"artigo", p): linha}} com tempo em float."""
    dados = {}
    for n in tamanhos(d):
        pts = {}
        for l in le_csv(os.path.join(d, f"tempos_{n}.csv")):
            l["tempo"] = float(l["tempo"])
            l["processos"] = int(l["processos"])
            if l["ok"] != "1":
                print(f"AVISO: vetor NAO ordenado em {l['versao']} p={l['processos']} N={n}")
            if l["versao"] == "seq":
                pts["seq"] = l["tempo"]
            else:
                pts[(l["versao"], l["processos"])] = l
        dados[n] = pts
    return dados


def speedup(pts, versao, p):
    """(tempo, S, E) ou None se o ponto nao existe."""
    l = pts.get((versao, p))
    if l is None or "seq" not in pts:
        return None
    s = pts["seq"] / l["tempo"]
    return l["tempo"], s, s / (p if p <= HW_THREADS else HW_THREADS)


def carga_por_rank(d, n, versao, p):
    """Media, sobre as repeticoes, da carga de cada rank: lista indexada por rank."""
    caminho = os.path.join(d, f"carga_{n}.csv")
    if not os.path.exists(caminho):
        return []
    soma = defaultdict(list)
    for l in le_csv(caminho):
        if l["versao"] == versao and int(l["processos"]) == p:
            soma[int(l["rank"])].append(l)
    ranks = []
    for r in sorted(soma):
        ls = soma[r]
        reg = {k: mean(float(x[k]) for x in ls)
               for k in ("recebido", "conquistado", "inicio", "bs", "intercala", "envio", "espera", "fim")}
        reg.update(rank=r, nivel=int(ls[0]["nivel"]), filhos=int(ls[0]["filhos"]))
        ranks.append(reg)
    return ranks


def por_nivel(ranks):
    """Agrega a carga por nivel: ranks, pedaco medio, bs medio/max, espera, ocupacao.
    Ocupacao = (bs + intercala) / tempo total da arvore (o fim da raiz)."""
    if not ranks:
        return []
    total = ranks[0]["fim"]
    niveis = defaultdict(list)
    for r in ranks:
        niveis[r["nivel"]].append(r)
    linhas = []
    for nv in sorted(niveis):
        rs = niveis[nv]
        linhas.append(dict(
            nivel=nv, ranks=len(rs),
            recebido=mean(r["recebido"] for r in rs),
            conquistado=mean(r["conquistado"] for r in rs),
            bs_med=mean(r["bs"] for r in rs), bs_max=max(r["bs"] for r in rs),
            intercala=mean(r["intercala"] for r in rs),
            espera=mean(r["espera"] for r in rs),
            ocupacao=mean((r["bs"] + r["intercala"]) / total for r in rs) if total else 0))
    return linhas


def desbalanceamento(ranks):
    """max/media do tempo de bubble sort entre os ranks que conquistaram (1 = perfeito)."""
    bs = [r["bs"] for r in ranks if r["bs"] > 0]
    return max(bs) / mean(bs) if bs else float("nan")


def carrega_ht(d, n):
    caminho = os.path.join(d, f"ht_{n}.csv")
    if not os.path.exists(caminho):
        return {}
    return {(l["modo"], l["versao"]): float(l["tempo"]) for l in le_csv(caminho)}


# ------------------------------------------------------------------ saida ----

def fmt(x, casas=2):
    return "--" if x is None else f"{x:.{casas}f}".replace(".", ",")


def grava_tex(d, nome, linhas):
    with open(os.path.join(d, f"{nome}.tex"), "w") as f:
        f.write("\n".join(linhas) + "\n")


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "resultados"
    dados = carrega(d)
    if not dados:
        sys.exit(f"nenhum tempos_N.csv em {d}/")

    tex_escala, tex_2k, tex_muitos, tex_ht, tex_carga = [], [], [], [], []

    for n, pts in dados.items():
        print(f"\n================ N = {n:,} ================".replace(",", "."))
        print(f"sequencial: {fmt(pts.get('seq'), 3)} s")

        # Escala 1..31: as duas arvores lado a lado
        print("\n  p | arvore: tempo     S      E | artigo: tempo     S      E")
        for p in PROCS_BASE:
            a, b = speedup(pts, "arvore", p), speedup(pts, "artigo", p)
            if a is None and b is None:
                continue
            ca = (fmt(a[0], 3), fmt(a[1]), fmt(a[2])) if a else ("--",) * 3
            cb = (fmt(b[0], 3), fmt(b[1]), fmt(b[2])) if b else ("--",) * 3
            print(f"{p:3d} | {ca[0]:>12} {ca[1]:>6} {ca[2]:>6} | {cb[0]:>12} {cb[1]:>6} {cb[2]:>6}")
            tex_escala.append(f"{n} & {p} & {' & '.join(ca)} & {' & '.join(cb)} \\\\")

        # Arvore do artigo com 2^k processos (todos os ranks com pedacos iguais)
        print("\n  p | artigo 2^k: tempo     S      E")
        for p in PROCS_2K:
            b = speedup(pts, "artigo", p)
            if b:
                print(f"{p:3d} | {fmt(b[0], 3):>16} {fmt(b[1]):>6} {fmt(b[2]):>6}")
                tex_2k.append(f"{n} & {p} & {fmt(b[0], 3)} & {fmt(b[1])} & {fmt(b[2])} \\\\")

        # Excesso de processos
        muitos = sorted({k[1] for k in pts if isinstance(k, tuple) and k[1] > HW_THREADS})
        if muitos:
            print("\n     p | arvore: tempo     S  S/32 | artigo: tempo     S  S/32")
            for p in muitos:
                a, b = speedup(pts, "arvore", p), speedup(pts, "artigo", p)
                ca = (fmt(a[0], 3), fmt(a[1]), fmt(a[2])) if a else ("--",) * 3
                cb = (fmt(b[0], 3), fmt(b[1]), fmt(b[2])) if b else ("--",) * 3
                print(f"{p:6d} | {ca[0]:>12} {ca[1]:>6} {ca[2]:>5} | {cb[0]:>12} {cb[1]:>6} {cb[2]:>5}")
                tex_muitos.append(f"{n} & {p} & {' & '.join(ca)} & {' & '.join(cb)} \\\\")

        # HT: (a) 15 x 31 processos; (b) os mesmos 31 com HT x so nucleos fisicos
        ht = carrega_ht(d, n)
        print("\nHT       | T(15)    T(31)   15->31 | 31 com HT  31 so fis.  ganho HT")
        for v in ("arvore", "artigo"):
            t15, t31 = pts.get((v, 15)), pts.get((v, 31))
            g1 = t15["tempo"] / t31["tempo"] if t15 and t31 else None
            th, tf = ht.get(("ht", v)), ht.get(("fisico", v))
            g2 = tf / th if th and tf else None
            linha = (fmt(t15 and t15["tempo"], 3), fmt(t31 and t31["tempo"], 3), fmt(g1),
                     fmt(th, 3), fmt(tf, 3), fmt(g2))
            print(f"{v:8} | " + "  ".join(f"{c:>8}" for c in linha))
            tex_ht.append(f"{n} & {v} & {' & '.join(linha)} \\\\")

        # Balanceamento por nivel
        for v, procs in (("arvore", PROCS_CARGA), ("artigo", PROCS_CARGA + [8, 16, 32])):
            for p in procs:
                ranks = carga_por_rank(d, n, v, p)
                if not ranks:
                    continue
                print(f"\ncarga {v} p={p}: desbalanceamento do bubble sort (max/media) = "
                      f"{fmt(desbalanceamento(ranks))}")
                print("  nivel ranks recebido conquist.   bs med    bs max  intercala    espera  ocupacao")
                for l in por_nivel(ranks):
                    print(f"  {l['nivel']:5d} {l['ranks']:5d} {l['recebido']:8.0f} {l['conquistado']:9.0f} "
                          f"{l['bs_med']:9.3f} {l['bs_max']:9.3f} {l['intercala']:10.4f} "
                          f"{l['espera']:9.3f} {100 * l['ocupacao']:8.1f}%")
                    if p in (15, 16):
                        tex_carga.append(
                            f"{n} & {v} & {p} & {l['nivel']} & {l['ranks']} & "
                            f"{l['recebido']:.0f} & {l['conquistado']:.0f} & {fmt(l['bs_med'], 3)} & "
                            f"{fmt(l['intercala'], 3)} & {fmt(l['espera'], 3)} & "
                            f"{fmt(100 * l['ocupacao'], 1)}\\% \\\\")

    grava_tex(d, "tab_escala", tex_escala)
    grava_tex(d, "tab_2k", tex_2k)
    grava_tex(d, "tab_muitos", tex_muitos)
    grava_tex(d, "tab_ht", tex_ht)
    grava_tex(d, "tab_carga", tex_carga)


if __name__ == "__main__":
    main()
