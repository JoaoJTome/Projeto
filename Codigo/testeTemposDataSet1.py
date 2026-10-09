"""
Verificação da equivalência Apriori / FP-Growth e medição de tempos (Dataset 1 - Groceries).

Como correr (na pasta onde está o dataSort.csv):
    python verificar_e_medir_dataset1.py

Para cada configuração (suporte mínimo, max_len):
  1. verifica se apriori() e fpgrowth() produzem os mesmos conjuntos frequentes e as
     mesmas regras (antecedente, consequente, suporte, confiança e elevação);
  2. mede o tempo de extração dos conjuntos frequentes (mediana de 5 execuções).
Os resultados são impressos e gravados em resultados_dataset1.csv.
"""
import platform
import statistics
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import mlxtend
from mlxtend.frequent_patterns import apriori, fpgrowth, association_rules
from mlxtend.preprocessing import TransactionEncoder

warnings.filterwarnings("ignore")

CSV = Path(__file__).with_name("dataSort.csv")
MIN_CONF = 0.25
REPETICOES = 5
CONFIGS = [(0.02, 2), (0.01, 2), (0.005, 2), (0.02, None), (0.01, None), (0.005, None)]
N_GROCERIES = 9835          # n.º de transações do Groceries original (pacote arules)
OCORRENCIAS_ESPERADAS = 43367


def carregar_transacoes():
    d = pd.read_csv(CSV, index_col=0, low_memory=False)
    trans = [[x.strip() for x in linha if isinstance(x, str) and x.strip()] for linha in d.values]
    trans = [t for t in trans if t != ["======="]]
    # o ficheiro contém o Groceries duas vezes: usam-se apenas as últimas 9 835 transações
    trans = trans[-N_GROCERIES:]
    ocorrencias = sum(len(t) for t in trans)
    print(f"Transações usadas: {len(trans)} | ocorrências de itens: {ocorrencias} "
          f"(esperado: {OCORRENCIAS_ESPERADAS}) -> {'OK' if ocorrencias == OCORRENCIAS_ESPERADAS else 'VERIFICAR'}")
    return trans


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


def medir(func, df, suporte, max_len):
    tempos = []
    for _ in range(REPETICOES):
        t0 = time.perf_counter()
        func(df, min_support=suporte, use_colnames=True, max_len=max_len)
        tempos.append(time.perf_counter() - t0)
    return statistics.median(tempos), statistics.stdev(tempos)


def main():
    print(f"Sistema: {platform.system()} {platform.release()} | CPU: {platform.processor()}")
    print(f"Python {platform.python_version()} | pandas {pd.__version__} | "
          f"NumPy {np.__version__} | mlxtend {mlxtend.__version__}\n")

    trans = carregar_transacoes()
    te = TransactionEncoder()
    df = pd.DataFrame(te.fit(trans).transform(trans), columns=te.columns_)
    print(f"Matriz transação x item: {df.shape[0]} x {df.shape[1]}\n")

    linhas = []
    for suporte, max_len in CONFIGS:
        fa = apriori(df, min_support=suporte, use_colnames=True, max_len=max_len)
        ff = fpgrowth(df, min_support=suporte, use_colnames=True, max_len=max_len)
        conj_a = {k: (v,) for k, v in zip(fa.itemsets, fa.support)}
        conj_f = {k: (v,) for k, v in zip(ff.itemsets, ff.support)}
        regras_a, regras_f = gerar_regras(fa, len(df)), gerar_regras(ff, len(df))

        t_ap, dp_ap = medir(apriori, df, suporte, max_len)
        t_fp, dp_fp = medir(fpgrowth, df, suporte, max_len)

        linha = dict(
            suporte_min=suporte,
            max_len=max_len if max_len else "sem limite",
            conjuntos=len(conj_a),
            regras=len(regras_a),
            conjuntos_iguais=iguais(conj_a, conj_f),
            regras_iguais=iguais(regras_a, regras_f),
            apriori_mediana_s=round(t_ap, 4),
            apriori_dp_s=round(dp_ap, 4),
            fpgrowth_mediana_s=round(t_fp, 4),
            fpgrowth_dp_s=round(dp_fp, 4),
            fpgrowth_sobre_apriori=round(t_fp / t_ap, 1),
        )
        linhas.append(linha)
        print(linha)

    pd.DataFrame(linhas).to_csv(CSV.with_name("resultados_dataset1.csv"),
                                index=False, sep=";", decimal=",")
    print("\nGravado em resultados_dataset1.csv")


if __name__ == "__main__":
    main()