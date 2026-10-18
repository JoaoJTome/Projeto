# API Backend - Análise de Cesto de Compras

Backend partilhado pela aplicação de backoffice e pela aplicação móvel
(`mercado_app/`). É o único sítio do sistema onde as regras de associação (Apriori,
via `mlxtend`) são calculadas — ver `Arquitetura_Geral_Sistema.md` na raiz
do projeto para a justificação desta decisão.

## Estrutura

```
api_backend/
  requirements.txt
  README.md            (este ficheiro)
  app.db               (criado automaticamente no primeiro arranque)
  app/
    main.py             (arranque da API e registo dos routers)
    database.py          (ligação SQLAlchemy / SQLite)
    models.py             (tabelas: User, Session, ShoppingList, ShoppingListItem, Settings)
    schemas.py             (validação dos pedidos/respostas - Pydantic)
    security.py             (hashing de palavras-passe com bcrypt)
    dependencies.py          (autenticação por token de sessão)
    recommendation_engine.py  (motor de recomendação - Apriori/mlxtend)
    engine_singleton.py        (instância única e partilhada do motor)
    routers/
      auth.py                   (registo, login, logout)
      lists.py                   (itens disponíveis, listas de compras)
      recommendations.py          (recomendações personalizadas)
      admin.py                     (parâmetros e estatísticas - backoffice)
```

## Pré-requisitos

- Python 3.9 ou superior.
- O ficheiro `dataSort.csv` (o mesmo já usado por `AppItensRecomendados.py`)
  colocado na **raiz do projeto**, ao lado da pasta `api_backend/` e do
  próprio `AppItensRecomendados.py`.

## Instalação

```bash
cd api_backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Arrancar a API

```bash
uvicorn app.main:app --reload
```

Por omissão fica disponível em `http://localhost:8000`. Documentação
interativa (Swagger UI) em `http://localhost:8000/docs`.

Na primeira vez que arranca, a API cria automaticamente o ficheiro
`app.db` (SQLite) com as tabelas necessárias, e uma linha de parâmetros por
omissão (`min_support=0.01`, `min_confidence=0.2`, `user_weight=1000`).

## Ligar o backoffice a esta API

O `AppItensRecomendados.py` já foi atualizado para consultar esta API em
vez de correr o Apriori localmente. Por omissão assume que a API está em
`http://localhost:8000`; para apontar para outro endereço, define a
variável de ambiente `API_BASE_URL` antes de correr o Streamlit.

As bibliotecas do backoffice (Streamlit, Matplotlib e Seaborn) já estão
incluídas no `requirements.txt`, por isso basta usar o mesmo ambiente
virtual da API, noutro terminal, a partir da pasta `Codigo`:

```bash
cd ..                                          # pasta Codigo
export API_BASE_URL="http://localhost:8000"    # opcional; Windows: set API_BASE_URL=...
streamlit run AppItensRecomendados.py
```

A API tem de estar a correr antes de abrires o backoffice, caso contrário
a app mostra um erro de ligação em vez das estatísticas.

## Testes

```bash
pip install pytest httpx   # httpx é o cliente HTTP usado pelo TestClient
pytest
```

Ver `tests/test_api.py`: cria uma base de dados SQLite temporária e testa o
fluxo completo (registo → login → guardar lista → recomendações → logout) e
os endpoints de backoffice (`/admin/settings`, `/admin/stats/*`).

## Endpoints principais

| Método | Rota | Autenticação | Descrição |
| --- | --- | --- | --- |
| POST | `/auth/register` | — | Cria conta e devolve token de sessão |
| POST | `/auth/login` | — | Autentica e devolve token de sessão |
| POST | `/auth/logout` | token | Invalida o token usado no pedido |
| GET | `/items?search=` | — | Lista/pesquisa itens do dataset |
| GET | `/lists` | token | Histórico de listas do utilizador |
| POST | `/lists` | token | Guarda uma nova lista de compras |
| POST | `/recommendations` | token | Recomendações para a lista em construção |
| GET | `/admin/settings` | — | Lê os parâmetros do motor |
| PUT | `/admin/settings` | — | Atualiza os parâmetros do motor |
| GET | `/admin/stats/top-items` | — | Top de itens mais frequentes (global) |
| GET | `/admin/stats/rules` | — | Regras de associação (global) |

A autenticação por token usa o cabeçalho `Authorization: Bearer <token>`.

## Limitações conhecidas / trabalho futuro

- Os endpoints `/admin/*` não exigem autenticação de administrador (não foi
  pedida uma componente de login para o backoffice nesta fase).
- Sem paginação em `/lists` nem em `/admin/stats/*` — aceitável para o
  volume de dados de demonstração deste projeto, mas a rever se o dataset
  ou o número de utilizadores crescer muito.
- Não foi ainda validado neste ambiente o comportamento do `mlxtend` com
  pandas 3.x (ver nota em `requirements.txt`).
