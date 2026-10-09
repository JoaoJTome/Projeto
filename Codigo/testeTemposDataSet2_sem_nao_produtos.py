"""
Verificação da equivalência Apriori / FP-Growth e medição de tempo e memória (Dataset 2 - Online Retail II).

Como correr (na pasta onde está o dataSet2.csv):
    python testeTemposDataSet2_sem_nao_produtos.py
    python testeTemposDataSet2_sem_nao_produtos.py --rapido     (só uma configuração, para testar)

Dados de entrada (usa o primeiro que encontrar na pasta):
  1. dataSet2.xlsx ou online_retail_II.xlsx (folha "Year 2009-2010") -> limpeza completa, igual à do relatório:
     remove linhas sem descrição, faturas de cancelamento ("C..."), quantidade <= 0, preço <= 0
     e códigos que não correspondem a produtos (portes, registos manuais, ajustes, taxas, vales, testes);
  2. dataSet2.csv (colunas Invoice, Description)      -> limpeza parcial: o ficheiro não tem
     quantidade nem preço, por isso só remove linhas sem descrição e faturas de cancelamento.

Para cada configuração (suporte mínimo, max_len = 2):
  1. verifica se o Apriori e o FP-Growth produzem os mesmos conjuntos frequentes e as mesmas
     regras (antecedente, consequente, suporte, confiança e elevação);
  2. mede o tempo (mediana de 3 execuções) de:
       - Apriori (implementação por omissão da mlxtend, vetorizada, muito exigente em memória);
       - Apriori com low_memory=True (avalia os candidatos um a um);
       - FP-Growth;
  3. mede o pico de memória de cada um (uma execução extra com tracemalloc).
O Apriori por omissão só é executado se a memória estimada for inferior a LIMITE_MEMORIA_GB;
caso contrário, regista-se a memória que seria necessária.
Os resultados são impressos e gravados em resultados_dataset2_sem_nao_produtos.csv.
"""
import platform
import statistics
import sys
import time
import tracemalloc
import warnings
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd
import mlxtend
from mlxtend.frequent_patterns import apriori, fpgrowth, association_rules
from mlxtend.preprocessing import TransactionEncoder

warnings.filterwarnings("ignore")

PASTA = Path(__file__).resolve().parent
XLSX_NOMES = ["dataSet2.xlsx", "online_retail_II.xlsx"]
XLSX = next((PASTA / n for n in XLSX_NOMES if (PASTA / n).exists()), PASTA / XLSX_NOMES[0])
CSV = PASTA / "dataSet2.csv"
MIN_CONF = 0.40
MAX_LEN = 2
REPETICOES = 3
LIMITE_MEMORIA_GB = 6.0
NAO_PRODUTOS = {"POST", "DOT", "M", "m", "C2", "ADJUST", "ADJUST2", "BANK CHARGES", "D", "AMAZONFEE", "S"}
SUPORTES = [0.03] if "--rapido" in sys.argv else [0.03, 0.02, 0.015, 0.01]


# ----------------------------------------------------------------------------- dados
def carregar_transacoes():
    if XLSX.exists():
        print(f"A ler {XLSX.name} (folha 'Year 2009-2010') - pode demorar 1 a 2 minutos...")
        d = pd.read_excel(XLSX, sheet_name="Year 2009-2010", dtype={"Invoice": str, "StockCode": str})
        n0, f0 = len(d), d["Invoice"].nunique()
        d = d[d["Description"].notna()]
        d = d[~d["Invoice"].str.upper().str.startswith("C")]
        d = d[d["Quantity"] > 0]
        d = d[d["Price"] > 0]
        sc = d["StockCode"].astype(str)
        nao_produto = sc.isin(NAO_PRODUTOS) | sc.str.startswith("gift_") | sc.str.startswith("TEST")
        print(f"Linhas com códigos que não são produtos removidas: {int(nao_produto.sum())}")
        d = d[~nao_produto]
        origem = "xlsx (limpeza completa, sem códigos não-produto)"
    else:
        print(f"A ler {CSV.name}...")
        d = pd.read_csv(CSV, encoding="utf-8-sig", dtype=str)
        n0, f0 = len(d), d["Invoice"].nunique()
        d = d[d["Description"].notna()]
        d = d[~d["Invoice"].str.upper().str.startswith("C")]
        origem = "csv (limpeza parcial: sem filtros de quantidade e preço)"

    # o produto é identificado pela descrição, sem espaços no início e no fim
    d = d.assign(Description=d["Description"].astype(str).str.strip())
    trans = d.groupby("Invoice")["Description"].apply(lambda s: sorted(set(s))).tolist()
    n_itens = d["Description"].nunique()
    ocorr = sum(len(t) for t in trans)
    print(f"Origem: {origem}")
    print(f"Linhas originais: {n0} ({f0} faturas) | linhas após limpeza: {len(d)}")
    print(f"Transações: {len(trans)} | itens distintos: {n_itens} | ocorrências: {ocorr} | "
          f"média por transação: {ocorr / len(trans):.2f}")
    return trans, origem


# ------------------------------------------------------------------------- auxiliares
def gerar_regras(conjuntos, n_transacoes):
    try:  # mlxtend >= 0.23.2
        r = association_rules(conjuntos, num_itemsets=n_transacoes,
                              metric="confidence", min_threshold=MIN_CONF)
    except TypeError:  # versões anteriores
        r = association_rules(conjuntos, metric="confidence", min_threshold=MIN_CONF)
    cols = ["antecedents", "consequents", "support", "confidence", "lift"]
    return {(a, c): (s, cf, l) for a, c, s, cf, l in r[cols].itertuples(index=False)}


def iguais(dic_a, dic_b):
    return dic_a.keys() == dic_b.keys() and all(np.allclose(dic_a[k], dic_b[k]) for k in dic_a)


def memoria_apriori_gb(df, suporte):
    """Memória (GB) do maior bloco que a apriori() por omissão aloca para os pares candidatos."""
    n_freq = int((df.mean(axis=0) >= suporte).sum())
    return comb(n_freq, 2) * 2 * len(df) / 1024 ** 3, n_freq


def medir_tempo(func, df, suporte):
    tempos = []
    for _ in range(REPETICOES):
        t0 = time.perf_counter()
        func(df, min_support=suporte, use_colnames=True, max_len=MAX_LEN)
        tempos.append(time.perf_counter() - t0)
    return statistics.median(tempos)


def medir_memoria_mb(func, df, suporte):
    tracemalloc.start()
    func(df, min_support=suporte, use_colnames=True, max_len=MAX_LEN)
    pico = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return pico / 1024 ** 2


def apriori_low_memory(df, **kw):
    return apriori(df, low_memory=True, **kw)


# ------------------------------------------------------------------------------ main
def main():
    print(f"Sistema: {platform.system()} {platform.release()} | CPU: {platform.processor()}")
    print(f"Python {platform.python_version()} | pandas {pd.__version__} | "
          f"NumPy {np.__version__} | mlxtend {mlxtend.__version__}\n")

    trans, origem = carregar_transacoes()
    te = TransactionEncoder()
    df = pd.DataFrame(te.fit(trans).transform(trans), columns=te.columns_)
    print(f"Matriz transação x item: {df.shape[0]} x {df.shape[1]}\n")

    linhas = []
    for suporte in SUPORTES:
        print(f"--- suporte mínimo {suporte} (max_len = {MAX_LEN}) ---", flush=True)
        mem_est, n_freq = memoria_apriori_gb(df, suporte)

        # 1. equivalência (Apriori low_memory vs FP-Growth)
        fa = apriori_low_memory(df, min_support=suporte, use_colnames=True, max_len=MAX_LEN)
        ff = fpgrowth(df, min_support=suporte, use_colnames=True, max_len=MAX_LEN)
        conj_a = {k: (v,) for k, v in zip(fa.itemsets, fa.support)}
        conj_f = {k: (v,) for k, v in zip(ff.itemsets, ff.support)}
        regras_a, regras_f = gerar_regras(fa, len(df)), gerar_regras(ff, len(df))

        # 2 e 3. tempo e memória
        if mem_est <= LIMITE_MEMORIA_GB:
            try:
                t_ap = round(medir_tempo(apriori, df, suporte), 3)
                m_ap = round(medir_memoria_mb(apriori, df, suporte))
            except MemoryError:
                t_ap, m_ap = "memória insuficiente", f"> {mem_est:.1f} GB"
        else:
            t_ap, m_ap = "não executado", f"~{mem_est:.1f} GB estimados"
        t_al = round(medir_tempo(apriori_low_memory, df, suporte), 3)
        m_al = round(medir_memoria_mb(apriori_low_memory, df, suporte))
        t_fp = round(medir_tempo(fpgrowth, df, suporte), 3)
        m_fp = round(medir_memoria_mb(fpgrowth, df, suporte))

        linha = dict(
            dados=origem,
            suporte_min=suporte,
            itens_frequentes=n_freq,
            pares_candidatos=comb(n_freq, 2),
            conjuntos=len(conj_a),
            regras=len(regras_a),
            conjuntos_iguais=iguais(conj_a, conj_f),
            regras_iguais=iguais(regras_a, regras_f),
            apriori_s=t_ap,
            apriori_pico_mb=m_ap,
            apriori_low_memory_s=t_al,
            apriori_low_memory_pico_mb=m_al,
            fpgrowth_s=t_fp,
            fpgrowth_pico_mb=m_fp,
        )
        linhas.append(linha)
        print(linha, flush=True)

    pd.DataFrame(linhas).to_csv(PASTA / "resultados_dataset2_sem_nao_produtos.csv", index=False, sep=";", decimal=",")
    print("\nGravado em resultados_dataset2_sem_nao_produtos.csv")


if __name__ == "__main__":
    main()
