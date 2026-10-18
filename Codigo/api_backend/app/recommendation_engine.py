"""Motor de Recomendação - Análise de Cesto de Compras.

Este módulo concentra TODA a lógica de mineração de regras de associação
(algoritmo Apriori, via mlxtend) usada no sistema. É, deliberadamente, a
única implementação deste algoritmo em todo o projeto: nem a aplicação de
backoffice nem a aplicação mobile recalculam regras por conta própria —
ambas consultam sempre esta API. Isto garante que os dois lados do sistema
veem sempre os mesmos resultados para os mesmos parâmetros.

"""
from pathlib import Path
from typing import List, Optional, Sequence

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

# api_backend/app/recommendation_engine.py -> app -> api_backend -> raiz do
# projeto, onde se espera encontrar o dataSort.csv (o mesmo ficheiro já
# usado por AppItensRecomendados.py).
CSV_PATH = Path(__file__).resolve().parent.parent.parent / "dataSort.csv"

# Itens de "ruído" do dataset original que nunca devem ser tratados como
# produtos (separador de secções do CSV e células vazias).
ITEMS_TO_EXCLUDE = ["=======", "nan"]


class RecommendationEngine:

    def __init__(self, csv_path: Path = CSV_PATH):
        self.csv_path = csv_path
        self._load_base_dataset()

    def _load_base_dataset(self) -> None:
        csv_data = pd.read_csv(self.csv_path, low_memory=False)
        csv_data.drop(columns="Unnamed: 0", inplace=True)
        csv_data = csv_data.fillna("nan").astype(str)
        csv_data = csv_data.apply(lambda col: col.str.lower())
        data_list = csv_data.to_numpy().tolist()

        self.te = TransactionEncoder()
        te_ary = self.te.fit(data_list).transform(data_list)
        self.base_df = pd.DataFrame(te_ary, columns=self.te.columns_)

        self.item_list = sorted(
            item for item in self.te.columns_ if item not in ITEMS_TO_EXCLUDE
        )

    def _encode_transactions(self, transactions: Sequence[Sequence[str]]) -> pd.DataFrame:
        """Codifica transações adicionais (ex.: as listas de compras já
        guardadas por um utilizador da app mobile) usando exatamente as
        mesmas colunas do dataset base, para poderem ser concatenadas com
        ele."""
        rows = [
            {col: (col in transacao) for col in self.base_df.columns}
            for transacao in transactions
        ]
        return pd.DataFrame(rows, columns=self.base_df.columns)

    def build_dataset(
        self,
        user_transactions: Sequence[Sequence[str]] = (),
        user_weight: int = 1,
    ) -> pd.DataFrame:
        """Junta o dataset base ao histórico de UM utilizador específico da
        app mobile, repetindo cada uma das suas listas guardadas
        `user_weight` vezes, para que o seu histórico pese mais no cálculo
        das SUAS recomendações pessoais. Sem transações extra (o caso
        das estatísticas do backoffice, que são sempre globais), devolve
        apenas o dataset base.
        """
        if not user_transactions:
            return self.base_df.copy()
        peso = max(1, int(user_weight))
        repeated = [list(t) for t in user_transactions for _ in range(peso)]
        extra_df = self._encode_transactions(repeated)
        return pd.concat([self.base_df, extra_df], ignore_index=True)

    def generate_association_rules(
        self, dat: pd.DataFrame, min_support: float, min_confidence: float
    ) -> pd.DataFrame:
        dat = dat.drop(columns=ITEMS_TO_EXCLUDE, errors="ignore")
        frequent_item_sets = apriori(dat, min_support=min_support, use_colnames=True)
        if frequent_item_sets.empty:
            return pd.DataFrame(
                columns=["antecedents", "consequents", "support", "confidence", "lift"]
            )
        return association_rules(
            frequent_item_sets, metric="confidence", min_threshold=min_confidence
        )

    def compute_top_items(self, dat: pd.DataFrame) -> pd.DataFrame:
        top_items = dat.sum().reset_index()
        top_items.columns = ["item", "contagem"]
        top_items = top_items[~top_items["item"].isin(ITEMS_TO_EXCLUDE)]
        top_items = top_items.sort_values("contagem", ascending=False).reset_index(drop=True)
        top_items["percentagem"] = (top_items["contagem"] / len(dat)) * 100
        return top_items

    def generate_recommendations(
        self,
        shopping_list: Sequence[str],
        dat: pd.DataFrame,
        min_support: float,
        min_confidence: float,
        rules: Optional[pd.DataFrame] = None,
        limit: int = 5,
    ) -> List[str]:
        """Gera recomendações para uma lista de compras em construção.

        `rules` pode ser passado já calculado (o endpoint de recomendações
        evita recalcular regras que acabaram de ser pedidas por outro
        endpoint); se omitido, é calculado aqui. Este parâmetro extra também
        facilita testar esta função isoladamente, sem depender do Apriori.
        """
        if rules is None:
            rules = self.generate_association_rules(dat, min_support, min_confidence)

        candidatos = []
        if not rules.empty:
            atuais = set(shopping_list)
            relevant_rules = rules[rules["antecedents"].apply(lambda x: set(x) <= atuais)]
            for _, regra in relevant_rules.iterrows():
                for consequente in regra["consequents"]:
                    candidatos.append((consequente, regra["lift"]))

        recommended: List[str] = []
        if candidatos:
            candidatos_df = pd.DataFrame(candidatos, columns=["item", "lift"])
            # Remove os itens que já estão na lista de compras
            candidatos_df = candidatos_df[~candidatos_df["item"].isin(shopping_list)]
            # Para cada item, mantém apenas a ocorrência com maior lift, e
            # ordena a lista final por lift decrescente
            # (em caso de empate no lift, desempata pelo nome do item, para
            # que o resultado seja determinístico)
            candidatos_df = candidatos_df.sort_values(
                ["lift", "item"], ascending=[False, True], kind="mergesort"
            ).drop_duplicates(subset="item", keep="first")
            recommended = candidatos_df["item"].tolist()

        # Se houver menos recomendações que o limite pedido (ex.: poucas
        # regras encontradas), completa com os itens mais frequentes do
        # dataset que ainda não estejam na lista nem já nas recomendações.
        if len(recommended) < limit:
            top_items = self.compute_top_items(dat)
            for item in top_items["item"]:
                if len(recommended) >= limit:
                    break
                if item not in recommended and item not in shopping_list:
                    recommended.append(item)

        return recommended[:limit]
