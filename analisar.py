#!/usr/bin/env python3
"""Tabelas do T3 a partir de resultados/ (ou do diretorio dado).

    python3 analisar.py [dir]

Le os CSVs do medir.sh (tempos_N, carga_N, ht_N) e, se existirem, os do
extra.sh (espera_N, carga_espera_N, muitos2k_N, fraca, carga_fraca,
seq_pedacos) e imprime: escala forte (speed-up e eficiencia), aumento do
numero de processos, HT, espera ativa x yield, balanceamento por nivel da
arvore, escala fraca e o comparativo das tres abordagens. Grava tambem
tab_*.tex, que o relatorio inclui sozinho. So usa a biblioteca padrao (o no
do cluster pode nao ter pandas).

Definicoes (decididas no planejamento):
  S(p) = T_seq / T(p)
  E(p) = S(p) / p           para p <= 32 (conta todos os processos, inclusive
                            os nos internos ociosos: e isso que se quer ver)
  E_hw = S(p) / 32          para p > 32: ha mais processos que as 32 hardware
                            threads dos 2 nos, entao S/p perde o sentido.
  S_div = T_div / T(p)      speed-up sobre a MESMA divisao: T_div e a soma dos
                            sequenciais de cada pedaco que a execucao ordenou
                            (seq_pedacos.csv). Tira do S o ganho algoritmico de
                            dividir (N^2 -> N^2/L); o ideal e S_div = p.
  E_div = S_div / p         (S_div / 32 acima de 32 processos)
  E_fraca = T_seq(n0) / T(p, N)   escala fraca, n0 elementos por processo
                            ordenador; o ideal e 1 (tempo constante).
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
    junta_muitos2k(d, dados)
    return dados


def speedup(pts, versao, p):
    """(tempo, S, E) ou None se o ponto nao existe."""
    l = pts.get((versao, p))
    if l is None or "seq" not in pts:
        return None
    s = pts["seq"] / l["tempo"]
    return l["tempo"], s, eficiencia(s, p)


def eficiencia(s, p):
    return s / (p if p <= HW_THREADS else HW_THREADS)


def ordenadores(versao, p):
    """Processos que ordenam: so as folhas na classica, todos no artigo."""
    return (p + 1) // 2 if versao == "arvore" else p


def pedacos(versao, n, p, delta=None):
    """Tamanhos dos pedacos ordenados numa execucao (simula a divisao do bs.c)."""
    if versao == "arvore":
        folhas = (p + 1) // 2
        delta = delta or -(-n // folhas)

        def desce(tam):
            if tam <= delta:
                return [tam]
            return desce(tam // 2) + desce(tam - tam // 2)
        return desce(n)

    def recursivo(tam, nivel, rank):          # artigo_recursivo do bs.c
        ajudante = rank + (1 << nivel)
        if ajudante >= p:
            return [tam]
        meio = tam // 2
        return recursivo(meio, nivel + 1, rank) + recursivo(tam - meio, nivel + 1, ajudante)
    return recursivo(n, 0, 0)


def carrega_seq_pedacos(d):
    """{tamanho: tempo sequencial} de seq_pedacos.csv; {} se ainda nao medido."""
    caminho = os.path.join(d, "seq_pedacos.csv")
    if not os.path.exists(caminho):
        return {}
    return {int(l["n"]): float(l["tempo"]) for l in le_csv(caminho)}


def t_seq(tabela, n):
    """Sequencial de n elementos: o tamanho medido mais proximo, corrigido
    pelo custo quadratico (os pedacos diferem dos medidos em 1 elemento)."""
    m = min(tabela, key=lambda t: abs(t - n) / t)
    return tabela[m] * (n / m) ** 2


def speedup_div(pts, seqs, versao, p):
    """(S_div, E_div) ou None: speed-up sobre a mesma divisao do vetor."""
    l = pts.get((versao, p))
    if l is None or not seqs:
        return None
    t_div = sum(t_seq(seqs, t) for t in pedacos(versao, int(l["n"]), p, int(l["delta"])))
    s = t_div / l["tempo"]
    return s, eficiencia(s, p)


def carga_ranks(caminho, filtro):
    """Media, sobre as repeticoes, da carga de cada rank das linhas que passam
    no filtro: lista ordenada por rank."""
    if not os.path.exists(caminho):
        return []
    soma = defaultdict(list)
    for l in le_csv(caminho):
        if filtro(l):
            soma[int(l["rank"])].append(l)
    ranks = []
    for r in sorted(soma):
        ls = soma[r]
        reg = {k: mean(float(x[k]) for x in ls)
               for k in ("recebido", "conquistado", "inicio", "bs", "intercala", "envio", "espera", "fim")}
        reg.update(rank=r, nivel=int(ls[0]["nivel"]), filhos=int(ls[0]["filhos"]))
        ranks.append(reg)
    return ranks


def carga_por_rank(d, n, versao, p):
    """Carga de cada rank de uma execucao da bateria principal (carga_N.csv)."""
    return carga_ranks(os.path.join(d, f"carga_{n}.csv"),
                       lambda l: l["versao"] == versao and int(l["processos"]) == p)


def bs_ordenadores(ranks):
    """(media, maximo) do tempo de bubble sort dos ranks que ordenaram."""
    bs = [r["bs"] for r in ranks if r["conquistado"] > 0]
    return (mean(bs), max(bs)) if bs else (None, None)


def carrega_espera(d, n):
    """{modo: linha} de espera_N.csv (classica p=31 em 4 modos + artigo p=16)."""
    caminho = os.path.join(d, f"espera_{n}.csv")
    if not os.path.exists(caminho):
        return {}
    linhas = {}
    for l in le_csv(caminho):
        l["tempo"] = float(l["tempo"])
        l["processos"] = int(l["processos"])
        linhas[l["modo"]] = l
    return linhas


def carga_espera(d, n, modo):
    return carga_ranks(os.path.join(d, f"carga_espera_{n}.csv"), lambda l: l["modo"] == modo)


def carrega_fraca(d):
    """(T_seq(n0), n0, [linhas]) de fraca.csv, ou (None, None, [])."""
    caminho = os.path.join(d, "fraca.csv")
    if not os.path.exists(caminho):
        return None, None, []
    t0 = n0 = None
    linhas = []
    for l in le_csv(caminho):
        l["tempo"] = float(l["tempo"])
        l["processos"], l["n"] = int(l["processos"]), int(l["n"])
        if l["versao"] == "seq":
            t0, n0 = l["tempo"], l["n"]
        else:
            linhas.append(l)
    return t0, n0, linhas


def carga_fraca(d, versao, p, n):
    return carga_ranks(os.path.join(d, "carga_fraca.csv"),
                       lambda l: (l["versao"], int(l["processos"]), int(l["n"])) == (versao, p, n))


def junta_muitos2k(d, dados):
    """Acrescenta aos pontos de cada N os do artigo com 64..1024 (muitos2k_N.csv)."""
    for n, pts in dados.items():
        caminho = os.path.join(d, f"muitos2k_{n}.csv")
        if not os.path.exists(caminho):
            continue
        for l in le_csv(caminho):
            l["tempo"], l["processos"] = float(l["tempo"]), int(l["processos"])
            pts[(l["versao"], l["processos"])] = l


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




def colunas(r, casas=(3, 2, 2)):
    """Formata uma tupla (tempo, S, E, ...) ou None em colunas de texto."""
    return tuple(fmt(x, c) for x, c in zip(r, casas)) if r else ("--",) * len(casas)


def secao_escala(n, pts, seqs, tex):
    """Escala forte 1..31, as duas arvores lado a lado, com S_div e E_div."""
    print("\n  p | arvore: tempo     S     E  S_div E_div | artigo: tempo     S     E  S_div E_div")
    for p in PROCS_BASE:
        cs = []
        for v in ("arvore", "artigo"):
            a, b = speedup(pts, v, p), speedup_div(pts, seqs, v, p)
            cs.append(colunas(a) + colunas(b, (1, 2)))
        if cs[0][0] == "--" and cs[1][0] == "--":
            continue
        print(f"{p:3d} | " + " | ".join(" ".join(f"{c:>6}" for c in x) for x in cs))
        tex.append(f"{n} & {p} & {' & '.join(cs[0])} & {' & '.join(cs[1])} \\\\")


def secao_2k(n, pts, tex):
    """Arvore do artigo com 2^k processos (todos os ranks com pedacos iguais)."""
    print("\n  p | artigo 2^k: tempo     S      E")
    for p in PROCS_2K:
        b = speedup(pts, "artigo", p)
        if b:
            print(f"{p:3d} | {fmt(b[0], 3):>16} {fmt(b[1]):>6} {fmt(b[2]):>6}")
            tex.append(f"{n} & {p} & {' & '.join(colunas(b))} \\\\")


def secao_muitos(n, pts, tex):
    """Aumento do numero de processos: 2^k - 1 nas duas arvores e 2^k no artigo."""
    ks = sorted({k[1] + 1 for k in pts if isinstance(k, tuple) and k[1] > HW_THREADS
                 and k[1] & (k[1] + 1) == 0})                  # 63 -> 64, ...
    if not ks:
        return
    print("\n     p | arvore: tempo     S  S/32 | artigo: tempo     S  S/32 | artigo p+1: tempo     S  S/32")
    for k in ks:
        cs = (colunas(speedup(pts, "arvore", k - 1)), colunas(speedup(pts, "artigo", k - 1)),
              colunas(speedup(pts, "artigo", k)))
        print(f"{k - 1:6d} | " + " | ".join(" ".join(f"{c:>7}" for c in x) for x in cs))
        tex.append(f"{n} & {k - 1} & {' & '.join(cs[0])} & {' & '.join(cs[1])} & {' & '.join(cs[2])} \\\\")


def secao_ht(d, n, pts, tex):
    """HT: (a) 15 x 31 processos; (b) os mesmos 31 com HT x so nucleos fisicos."""
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
        tex.append(f"{n} & {v} & {' & '.join(linha)} \\\\")


MODOS_ESPERA = [("ht-polling", "clássica, HT, polling (padrão)"),
                ("ht-yield", "clássica, HT, yield"),
                ("fisico-polling", "clássica, só núcleos físicos, polling"),
                ("fisico-yield", "clássica, só núcleos físicos, yield"),
                ("artigo", "artigo, 1 por núcleo físico")]


def secao_espera(d, n, seqs, tex):
    """Espera ativa x yield na classica p=31, com o artigo p=16 de referencia."""
    linhas = carrega_espera(d, n)
    if not linhas:
        return
    print("\nespera (mesmos 16 pedacos)            p    tempo  bs folha med   max  S_div")
    for modo, rotulo in MODOS_ESPERA:
        l = linhas.get(modo)
        if l is None:
            continue
        med, mx = bs_ordenadores(carga_espera(d, n, modo))
        sd = speedup_div({(l["versao"], l["processos"]): l}, seqs, l["versao"], l["processos"])
        cs = (fmt(l["tempo"], 3), fmt(med, 3), fmt(mx, 3), fmt(sd and sd[0], 1))
        print(f"  {rotulo:36} {l['processos']:2d} {cs[0]:>8} {cs[1]:>13} {cs[2]:>5} {cs[3]:>6}")
        tex.append(f"{n} & {rotulo} & {l['processos']} & {' & '.join(cs)} \\\\")


def secao_carga(d, n, n_maior, tex):
    """Balanceamento por nivel da arvore (a tabela do relatorio usa so o maior N)."""
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
                if p in (15, 16) and n == n_maior:
                    tex.append(
                        f"{v} & {p} & {l['nivel']} & {l['ranks']} & "
                        f"{l['recebido']:.0f} & {l['conquistado']:.0f} & {fmt(l['bs_med'], 3)} & "
                        f"{fmt(l['intercala'], 3)} & {fmt(l['espera'], 3)} & "
                        f"{fmt(100 * l['ocupacao'], 1)}\\% \\\\")


def secao_fraca(d, tex):
    """Escala fraca: n0 elementos por processo ordenador, N cresce com eles."""
    t0, n0, linhas = carrega_fraca(d)
    if t0 is None:
        return
    print(f"\n================ escala fraca, n0 = {n0} ================")
    print(f"sequencial de n0: {fmt(t0, 3)} s")
    print("  versao   p  ordenad.        N    tempo   bs max    resto  E_fraca")
    tex.append(f"sequencial & 1 & 1 & {n0} & {fmt(t0, 3)} & {fmt(t0, 3)} & {fmt(0, 3)} & {fmt(1)} \\\\")
    for l in sorted(linhas, key=lambda l: (l["versao"] != "arvore", l["processos"])):
        v, p, n = l["versao"], l["processos"], l["n"]
        _, mx = bs_ordenadores(carga_fraca(d, v, p, n))
        resto = l["tempo"] - mx if mx is not None else None
        cs = (fmt(l["tempo"], 3), fmt(mx, 3), fmt(resto, 3), fmt(t0 / l["tempo"]))
        print(f"  {v:7} {p:3d} {ordenadores(v, p):9d} {n:8d} {cs[0]:>8} {cs[1]:>8} {cs[2]:>8} {cs[3]:>8}")
        nome = "clássica" if v == "arvore" else "artigo"
        tex.append(f"{nome} & {p} & {ordenadores(v, p)} & {n} & {' & '.join(cs)} \\\\")


def secao_comparacao(d, dados, seqs, tex):
    """As tres abordagens no maior N: sem balanceamento, aumento do numero de
    processos (sem alterar o codigo) e arvore do artigo (alterando o codigo)."""
    n = max(dados)
    pts, espera = dados[n], carrega_espera(d, n)
    muitos = [p for (v, p) in (k for k in pts if isinstance(k, tuple)) if p > HW_THREADS]
    melhor = lambda v, ps: min((p for p in ps if (v, p) in pts),
                               key=lambda p: pts[(v, p)]["tempo"], default=None)
    casos = [("sem balanceamento", "clássica, 16 núcleos físicos", "arvore", 15, None),
             ("aumento do nº de processos", "clássica, HT, polling", "arvore", 31, None),
             ("", "clássica, HT, yield", "arvore", 31, "ht-yield"),
             ("", "clássica", "arvore", 63, None),
             ("", "clássica, melhor $p$", "arvore", melhor("arvore", muitos), None),
             ("alteração do código", "artigo", "artigo", 16, None),
             ("", "artigo", "artigo", 32, None),
             ("", "artigo, melhor $p$", "artigo", melhor("artigo", muitos), None)]
    print(f"\n================ tres abordagens, N = {n} ================")
    for grupo, rotulo, v, p, modo in casos:
        if p is None:
            continue
        l = espera.get(modo) if modo else pts.get((v, p))
        if l is None or "seq" not in pts:
            continue
        s = pts["seq"] / l["tempo"]
        sd = speedup_div({(v, p): l}, seqs, v, p)
        cs = (fmt(l["tempo"], 3), fmt(s, 1), colunas(sd, (1, 2)))
        print(f"  {grupo:27} {rotulo:30} p={p:4d} ord={ordenadores(v, p):4d} "
              f"t={cs[0]:>8} S={cs[1]:>7} S_div={cs[2][0]:>6} E_div={cs[2][1]:>5}")
        tex.append(f"{grupo} & {rotulo} & {p} & {ordenadores(v, p)} & {cs[0]} & {cs[1]} & "
                   f"{' & '.join(cs[2])} \\\\")


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "resultados"
    dados = carrega(d)
    if not dados:
        sys.exit(f"nenhum tempos_N.csv em {d}/")
    seqs = carrega_seq_pedacos(d)
    if seqs:   # os sequenciais de N inteiro tambem servem de tamanho de pedaco
        for n, pts in dados.items():
            if "seq" in pts:
                seqs.setdefault(n, pts["seq"])
    else:
        print("AVISO: sem seq_pedacos.csv (extra.sh): S_div e E_div ficam em branco")

    tex = defaultdict(list)
    for n, pts in dados.items():
        print(f"\n================ N = {n:,} ================".replace(",", "."))
        print(f"sequencial: {fmt(pts.get('seq'), 3)} s")
        secao_escala(n, pts, seqs, tex["tab_escala"])
        secao_2k(n, pts, tex["tab_2k"])
        secao_muitos(n, pts, tex["tab_muitos"])
        secao_ht(d, n, pts, tex["tab_ht"])
        secao_espera(d, n, seqs, tex["tab_espera"])
        secao_carga(d, n, max(dados), tex["tab_carga"])
    secao_fraca(d, tex["tab_fraca"])
    secao_comparacao(d, dados, seqs, tex["tab_comparacao"])

    for nome in ("tab_escala", "tab_2k", "tab_muitos", "tab_ht", "tab_espera",
                 "tab_carga", "tab_fraca", "tab_comparacao"):
        if tex[nome]:
            grava_tex(d, nome, tex[nome])


if __name__ == "__main__":
    main()
