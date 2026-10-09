import os

import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns

# ============================================================================
# App de Backoffice - Análise de Cesto de Compras
#
# Esta aplicação deixou de calcular localmente as regras de associação: o
# motor de recomendação (Apriori, via mlxtend) passou a viver
# exclusivamente na API backend (pasta api_backend/), que é agora o único
# ponto de cálculo do sistema, partilhado com a futura aplicação mobile.
# O backoffice limita-se a consultar essa API e a mostrar/editar os
# parâmetros e as estatísticas globais.
#
# Ver Arquitetura_Geral_Sistema.md, secções 4.3 e 6, para a justificação
# desta decisão, e api_backend/README.md para como arrancar a API.
#
# Páginas desta app:
#   - Estatísticas: regras de associação e itens mais frequentes do
#     dataset, calculados pela API com os parâmetros atuais;
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


def get_rules():
    resp = requests.get(f"{API_BASE_URL}/admin/stats/rules", timeout=60)
    resp.raise_for_status()
    rules = pd.DataFrame(resp.json())
    if not rules.empty:
        # antecedents/consequents chegam como listas (JSON); apresentam-se
        # melhor como texto, tal como já acontecia com os frozenset do
        # mlxtend na versão anterior desta app.
        rules["antecedents"] = rules["antecedents"].apply(", ".join)
        rules["consequents"] = rules["consequents"].apply(", ".join)
    return rules


def get_top_items():
    resp = requests.get(f"{API_BASE_URL}/admin/stats/top-items", timeout=60)
    resp.raise_for_status()
    top_items = pd.DataFrame(resp.json())
    top_items.columns = [c.capitalize() for c in top_items.columns]
    return top_items


# Aplicação Streamlit
def main():
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
            1, 100, settings["user_weight"],
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
            update_settings(min_support, min_confidence, user_weight)
            st.success("Parâmetros atualizados.")

    elif page == "Estatísticas":
        st.header("Resultados")

        rules = get_rules()
        if rules.empty:
            st.warning(
                "Não foram encontradas regras de associação com os limiares "
                "atuais (ver página \"Opções\"). Tenta reduzi-los."
            )
        else:
            st.subheader("Regras de Associação")
            st.write(rules)

        st.subheader("Top 20 Itens com Percentagens")
        top_items = get_top_items()
        st.write(top_items.head(20))

        # Cria um gráfico de dispersão de suporte vs. confiança
        if not rules.empty:
            plt.figure(figsize=(8, 6))
            sns.scatterplot(x="support", y="confidence", data=rules)
            plt.title("Regras de Associação - Suporte vs. Confiança")
            st.pyplot(plt)


if __name__ == "__main__":
    main()
