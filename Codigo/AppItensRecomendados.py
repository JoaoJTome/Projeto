import os

import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns

# ============================================================================
# App de Backoffice - Análise de Cesto de Compras
#
# Páginas desta app:
#   - Estatísticas: regras de associação, itens mais frequentes e itens
#     sem regras associadas, calculados pela API com os parâmetros atuais;
#   - Opções: configuração dos parâmetros do motor de recomendação
#     (guardados na API, partilhados com a app mobile).
# ============================================================================

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def get_settings():
    resp = requests.get(f"{API_BASE_URL}/admin/settings", timeout=10)
    resp.raise_for_status()
    return resp.json()


def update_settings(min_support, min_confidence, user_weight):
    resp = requests.put(
        f"{API_BASE_URL}/admin/settings",
        json={
            "min_support": min_support,
            "min_confidence": min_confidence,
            "user_weight": user_weight,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_rules_raw():
    """Regras de associação tal como a API as devolve, com "antecedents" e
    "consequents" ainda como listas (não como texto), para poderem ser
    comparadas item a item - usado tanto para apresentar a tabela como para
    calcular os itens sem regras associadas."""
    resp = requests.get(f"{API_BASE_URL}/admin/stats/rules", timeout=60)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def format_rules_for_display(rules_raw: pd.DataFrame) -> pd.DataFrame:
    if rules_raw.empty:
        return rules_raw
    display = rules_raw.copy()
    # antecedents/consequents chegam como listas (JSON); apresentam-se
    # melhor como texto, tal como já acontecia com os frozenset do mlxtend
    # na versão anterior desta app.
    display["antecedents"] = display["antecedents"].apply(", ".join)
    display["consequents"] = display["consequents"].apply(", ".join)
    return display


def get_top_items():
    resp = requests.get(f"{API_BASE_URL}/admin/stats/top-items", timeout=60)
    resp.raise_for_status()
    top_items = pd.DataFrame(resp.json())
    top_items.columns = [c.capitalize() for c in top_items.columns]
    return top_items


def items_covered_by_rules(rules_raw: pd.DataFrame) -> set:
    """Conjunto de itens que aparecem em pelo menos uma regra de associação,
    como antecedente ou como consequente. Extraído como função à parte
    porque é usado tanto para a tabela/contagem de itens sem regras como
    para a contagem de regras por item."""
    covered = set()
    if rules_raw.empty:
        return covered
    for coluna in ("antecedents", "consequents"):
        for grupo in rules_raw[coluna]:
            covered.update(grupo)
    return covered


def compute_items_without_rules(top_items: pd.DataFrame, rules_raw: pd.DataFrame) -> pd.DataFrame:
    """Itens do dataset que, com os parâmetros atuais, não aparecem em
    nenhuma regra de associação - nem como antecedente, nem como
    consequente. É calculado aqui, e não na API, porque é apenas uma
    comparação sobre dados que a API já devolveu (as regras e o top de
    itens); a extração das regras em si continua a ser feita
    exclusivamente na API - ver Arquitetura_Geral_Sistema.md, secção 6.1.
    """
    covered = items_covered_by_rules(rules_raw)
    sem_regras = top_items[~top_items["Item"].isin(covered)].reset_index(drop=True)
    return sem_regras


def compute_item_rule_counts(rules_raw: pd.DataFrame) -> pd.DataFrame:
    """Para cada item que aparece em pelo menos uma regra, conta em quantas
    regras aparece no total (somando as vezes que surge como antecedente e
    como consequente), ordenado do mais para o menos frequente. Tal como
    compute_items_without_rules, é calculado aqui a partir das regras já
    devolvidas pela API, sem repetir o cálculo das próprias regras."""
    if rules_raw.empty:
        return pd.DataFrame(columns=["Item", "Nº de Regras"])

    contagens = {}
    for coluna in ("antecedents", "consequents"):
        for grupo in rules_raw[coluna]:
            for item in grupo:
                contagens[item] = contagens.get(item, 0) + 1

    contagens_df = pd.DataFrame(
        sorted(contagens.items(), key=lambda par: par[1], reverse=True),
        columns=["Item", "Nº de Regras"],
    )
    return contagens_df


def _dataframe_height(num_rows: int, max_height: int = 800) -> int:
    """Altura (em pixels) suficiente para mostrar todas as linhas de uma
    tabela sem barra de scroll interna, até um máximo razoável."""
    return min(max_height, 38 + 35 * max(num_rows, 1))


# Aplicação Streamlit
def main():
    # Tem de ser a primeira instrução Streamlit da aplicação. O layout
    # "wide" usa a largura toda da janela em vez da coluna estreita e
    # centrada por omissão, para as tabelas de estatísticas terem espaço.
    st.set_page_config(
        page_title="Backoffice - Análise de Cesto de Compras", layout="wide"
    )

    st.title("App de Backoffice - Análise de Cesto de Compras")

    # Seleção de página. A app abre diretamente em "Estatísticas": deixou de
    # existir uma página de boas-vindas, já que esta aplicação passa a ser
    # usada apenas por administradores/gestores, e não pelo consumidor final.
    page = st.sidebar.selectbox("Selecionar página", ["Estatísticas", "Opções"])

    try:
        settings = get_settings()
    except requests.exceptions.RequestException as exc:
        st.error(
            f"Não foi possível ligar à API backend em {API_BASE_URL}.\n\n"
            "Confirma que a API está a correr (`uvicorn app.main:app`, a "
            "partir da pasta `api_backend/`) antes de usar o backoffice.\n\n"
            f"Detalhe do erro: {exc}"
        )
        return

    if page == "Opções":
        st.header("Opções")

        # Limiares de suporte e confiança usados no cálculo das regras de
        # associação apresentadas na página "Estatísticas".
        min_support = st.slider("Suporte Mínimo", 0.01, 1.0, settings["min_support"])
        min_confidence = st.slider("Confiança Mínima", 0.01, 1.0, settings["min_confidence"])
        user_weight = st.slider(
            "Peso do histórico do utilizador (aplicação mobile)",
            1, 1000, settings["user_weight"],
            help="Quantas vezes cada lista de compras guardada por um utilizador "
                 "da app mobile conta no cálculo das SUAS recomendações pessoais. "
                 "Não afeta as estatísticas globais mostradas nesta app."
        )
        st.write(
            "Estes parâmetros são guardados na API e usados tanto pelas "
            "estatísticas deste backoffice como pelas recomendações "
            "apresentadas na aplicação mobile."
        )

        if st.button("Guardar"):
            try:
                update_settings(min_support, min_confidence, user_weight)
            except requests.exceptions.RequestException:
                st.error(
                    "Não foi possível guardar os parâmetros. Verifique se a API "
                    "está em execução e tente novamente."
                )
            else:
                st.success("Parâmetros atualizados.")

    elif page == "Estatísticas":
        st.header("Resultados")

        # Erros HTTP ou de ligação (incluindo timeouts) mostram uma mensagem
        # compreensível em vez da exceção completa.
        try:
            rules_raw = get_rules_raw()
            top_items = get_top_items()
        except requests.exceptions.RequestException:
            st.error(
                "Não foi possível obter as estatísticas da API. Verifique se a "
                "API está em execução e tente novamente."
            )
            return

        if rules_raw.empty:
            st.warning(
                "Não foram encontradas regras de associação com os limiares "
                "atuais (ver página \"Opções\"). Tenta reduzi-los."
            )
        else:
            st.subheader("Regras de Associação")
            rules_display = format_rules_for_display(rules_raw)
            st.dataframe(
                rules_display,
                use_container_width=True,
                height=_dataframe_height(len(rules_display)),
            )

        # Totais de cobertura: quantos itens do dataset ficam, ou não, cobertos
        # por pelo menos uma regra de associação com os limiares atuais.
        covered = items_covered_by_rules(rules_raw)
        total_itens = len(top_items)
        total_com_regras = len(covered)
        total_sem_regras = total_itens - total_com_regras

        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Itens", total_itens)
        col2.metric("Itens com Regras", total_com_regras)
        col3.metric("Itens sem Regras", total_sem_regras)

        st.subheader("Top 20 Itens com Percentagens")
        st.dataframe(
            top_items.head(20),
            use_container_width=True,
            height=_dataframe_height(min(len(top_items), 20)),
        )

        st.subheader("Itens que Mais Aparecem nas Regras")
        st.caption(
            "Número de regras de associação em que cada item aparece, seja "
            "como antecedente, seja como consequente. Um valor elevado indica "
            "um item central nos padrões de compra encontrados."
        )
        contagem_regras = compute_item_rule_counts(rules_raw)
        if contagem_regras.empty:
            st.write("Não há regras de associação para contar.")
        else:
            st.dataframe(
                contagem_regras,
                use_container_width=True,
                height=_dataframe_height(len(contagem_regras)),
            )

        st.subheader("Itens sem Regras Associadas")
        sem_regras = compute_items_without_rules(top_items, rules_raw)
        st.caption(
            "Itens do dataset que, com os limiares atuais (ver página \"Opções\"), "
            "não aparecem em nenhuma regra de associação - nem como antecedente, "
            "nem como consequente. Um número elevado de itens aqui costuma indicar "
            "que vale a pena reduzir o suporte e/ou a confiança mínimos."
        )
        if sem_regras.empty:
            st.write("Todos os itens do dataset aparecem em pelo menos uma regra de associação.")
        else:
            st.write(f"{len(sem_regras)} de {len(top_items)} itens sem nenhuma regra associada.")
            st.dataframe(
                sem_regras,
                use_container_width=True,
                height=_dataframe_height(len(sem_regras)),
            )

        # Cria um gráfico de dispersão de suporte vs. confiança
        if not rules_raw.empty:
            st.subheader("Suporte vs. Confiança")
            fig, ax = plt.subplots(figsize=(10, 5))
            sns.scatterplot(x="support", y="confidence", data=rules_raw, ax=ax)
            ax.set_title("Regras de Associação - Suporte vs. Confiança")
            st.pyplot(fig)


if __name__ == "__main__":
    main()