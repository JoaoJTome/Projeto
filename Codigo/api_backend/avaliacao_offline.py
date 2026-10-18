"""Avaliação offline do motor de recomendação

Usa o próprio RecommendationEngine da API, sobre o dataSort.csv (Dataset 1):

1. Divide as 9 835 transações em treino (80%) e teste (20%), com 5 divisões
   aleatórias diferentes (sementes 0 a 4).
2. Extrai as regras só com o treino, com os parâmetros indicados.
3. Para cada cesto de teste com pelo menos dois itens, esconde um item escolhido
   ao acaso e pede ao motor cinco recomendações para os restantes itens.
4. Mede a taxa de acerto nas cinco recomendações (HR@5): a proporção de casos
   em que o item escondido está entre as recomendações. Com um único item
   escondido, coincide com a revocação nas cinco primeiras (recall@5); a
   precisão nas cinco primeiras (precision@5) é HR@5 / 5.
5. Compara com uma recomendação baseada apenas na popularidade: os cinco itens
   mais frequentes do treino que ainda não estão no cesto.

Mostra também exemplos de recomendações sem histórico e com o histórico de um
utilizador (peso 1000).

O resultado é escrito no ecrã e no ficheiro resultados_avaliacao.txt.
"""
import random
import statistics
import time

import pandas as pd

from app.recommendation_engine import ITEMS_TO_EXCLUDE, RecommendationEngine

SEMENTES = range(5)
LIMITE = 5
CONFIGURACOES = [(0.01, 0.2), (0.005, 0.2), (0.005, 0.1), (0.003, 0.1)]

linhas_saida = []


def escrever(texto=""):
    print(texto)
    linhas_saida.append(texto)


def itens_do_cesto(linha):
    return sorted(c for c, v in linha.items() if v and c not in ITEMS_TO_EXCLUDE)


def avaliar(engine, min_support, min_confidence):
    base = engine.base_df
    resultados = {"motor": [], "popularidade": [], "regras": [], "cobertura": [], "casos": []}
    for semente in SEMENTES:
        rnd = random.Random(semente)
        indices = list(range(len(base)))
        rnd.shuffle(indices)
        corte = int(0.8 * len(indices))
        treino = base.iloc[indices[:corte]].reset_index(drop=True)
        teste = base.iloc[indices[corte:]]

        regras = engine.generate_association_rules(treino, min_support, min_confidence)
        populares = engine.compute_top_items(treino)["item"].tolist()

        acertos_motor = acertos_pop = casos = 0
        recomendados = set()
        for _, linha in teste.iterrows():
            cesto = itens_do_cesto(linha)
            if len(cesto) < 2:
                continue
            escondido = rnd.choice(cesto)
            atuais = [i for i in cesto if i != escondido]
            rec = engine.generate_recommendations(
                atuais, treino, min_support, min_confidence, rules=regras, limit=LIMITE
            )
            pop = [i for i in populares if i not in atuais][:LIMITE]
            casos += 1
            acertos_motor += escondido in rec
            acertos_pop += escondido in pop
            recomendados.update(rec)

        resultados["motor"].append(acertos_motor / casos)
        resultados["popularidade"].append(acertos_pop / casos)
        resultados["regras"].append(len(regras))
        resultados["cobertura"].append(len(recomendados))
        resultados["casos"].append(casos)
    return resultados


def media_dp(valores):
    return statistics.mean(valores), statistics.pstdev(valores)


def exemplos(engine):
    jantar = ["whipped/sour cream", "other vegetables", "yogurt", "citrus fruit", "tropical fruit"]
    for atuais in (["bottled water", "soda", "root vegetables"], ["whipped/sour cream"]):
        for peso, historico in ((1, []), (1000, [jantar])):
            dat = engine.build_dataset(historico, peso)
            rec = engine.generate_recommendations(atuais, dat, 0.01, 0.2, limit=LIMITE)
            rotulo = "sem histórico" if not historico else f"com a lista Jantar (peso {peso})"
            escrever(f"  {atuais} {rotulo}: {rec}")


def main():
    inicio = time.time()
    engine = RecommendationEngine()
    escrever("Avaliação offline do motor de recomendação (Dataset 1, 80/20, 5 divisões)")
    escrever("")
    escrever("Suporte | Confiança | Regras | Casos | HR@5 motor | HR@5 popularidade | Itens distintos recomendados")
    for min_support, min_confidence in CONFIGURACOES:
        r = avaliar(engine, min_support, min_confidence)
        m, dm = media_dp(r["motor"])
        p, dp = media_dp(r["popularidade"])
        escrever(
            f"{min_support} | {min_confidence} | {statistics.mean(r['regras']):.0f} | "
            f"{statistics.mean(r['casos']):.0f} | {m:.3f} ± {dm:.3f} | {p:.3f} ± {dp:.3f} | "
            f"{statistics.mean(r['cobertura']):.1f}"
        )
    escrever("")
    escrever("Exemplos (suporte 0,01, confiança 0,2):")
    exemplos(engine)
    escrever("")
    escrever(f"Tempo total: {time.time() - inicio:.0f} s")
    with open("resultados_avaliacao.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(linhas_saida) + "\n")


if __name__ == "__main__":
    pd.set_option("mode.chained_assignment", None)
    main()
