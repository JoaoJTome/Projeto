"""Testes de ponta a ponta da API, usando o dataset sintético definido em
conftest.py. Correr com `pytest` a partir da pasta api_backend/.
"""


def test_register_login_logout_flow(client):
    resp = client.post(
        "/auth/register",
        json={
            "email": "ana@example.com",
            "password": "palavra-passe-1",
            "password_confirmation": "palavra-passe-1",
        },
    )
    assert resp.status_code == 201
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # o token emitido no registo dá acesso imediato a rotas protegidas
    resp = client.get("/lists", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

    # logout invalida o token do lado do servidor
    resp = client.post("/auth/logout", headers=headers)
    assert resp.status_code == 204
    resp = client.get("/lists", headers=headers)
    assert resp.status_code == 401

    # login emite um novo token válido
    resp = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "palavra-passe-1"}
    )
    assert resp.status_code == 200
    assert resp.json()["token"]


def test_login_with_wrong_password_is_rejected(client):
    client.post(
        "/auth/register",
        json={"email": "x@example.com", "password": "12345678", "password_confirmation": "12345678"},
    )
    resp = client.post("/auth/login", json={"email": "x@example.com", "password": "errada123"})
    assert resp.status_code == 401


def test_register_rejects_mismatched_passwords(client):
    resp = client.post(
        "/auth/register",
        json={"email": "b@example.com", "password": "12345678", "password_confirmation": "diferente"},
    )
    assert resp.status_code == 422


def test_register_password_policy_and_email_validation(client):
    """Limites efetivamente aceites no registo: palavra-passe com pelo menos
    8 caracteres (7 é rejeitado, 8 é aceite) e email com formato válido."""
    def registar(email, password):
        return client.post(
            "/auth/register",
            json={"email": email, "password": password, "password_confirmation": password},
        )

    assert registar("curta@example.com", "1234567").status_code == 422
    assert registar("sem-arroba.example.com", "12345678").status_code == 422
    assert registar("limite@example.com", "12345678").status_code == 201


def test_register_rejects_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "12345678",
        "password_confirmation": "12345678",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_protected_routes_require_token(client):
    assert client.get("/lists").status_code in (401, 422)
    resp = client.get("/lists", headers={"Authorization": "Bearer token-invalido"})
    assert resp.status_code == 401


def test_items_endpoint_lists_and_searches_dataset_items(client):
    resp = client.get("/items")
    assert resp.status_code == 200
    items = resp.json()
    assert set(items) == {"milk", "bread", "eggs", "butter"}

    resp = client.get("/items", params={"search": "mil"})
    assert resp.json() == ["milk"]


def _register(client, email="c@example.com"):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "12345678", "password_confirmation": "12345678"},
    )
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_save_list_and_history(client):
    headers = _register(client)

    resp = client.post("/lists", json={"items": ["Milk", "Bread"]}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    # os itens guardados ficam em minúsculas, tal como o dataset
    assert {i["item_name"] for i in body["items"]} == {"milk", "bread"}

    resp = client.get("/lists", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_recommendations_exclude_current_items_and_respect_limit(client):
    headers = _register(client, email="d@example.com")
    client.post("/lists", json={"items": ["milk", "bread"]}, headers=headers)

    resp = client.put(
        "/admin/settings",
        json={"min_support": 0.1, "min_confidence": 0.3, "user_weight": 3},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/recommendations", json={"current_items": ["milk"]}, headers=headers
    )
    assert resp.status_code == 200
    recommended = resp.json()["recommended_items"]
    assert "milk" not in recommended
    assert len(recommended) <= 5


def test_admin_settings_roundtrip(client):
    resp = client.get("/admin/settings")
    assert resp.status_code == 200
    assert resp.json() == {"min_support": 0.01, "min_confidence": 0.2, "user_weight": 1000}

    resp = client.put(
        "/admin/settings",
        json={"min_support": 0.2, "min_confidence": 0.5, "user_weight": 10},
    )
    assert resp.status_code == 200

    resp = client.get("/admin/settings")
    assert resp.json() == {"min_support": 0.2, "min_confidence": 0.5, "user_weight": 10}

    # valores fora dos limites são rejeitados e não alteram os parâmetros
    for invalido in (
        {"min_support": 0.0, "min_confidence": 0.5, "user_weight": 10},
        {"min_support": 0.2, "min_confidence": 1.5, "user_weight": 10},
        {"min_support": 0.2, "min_confidence": 0.5, "user_weight": 0},
        {"min_support": 0.2, "min_confidence": 0.5, "user_weight": 1001},
    ):
        assert client.put("/admin/settings", json=invalido).status_code == 422
    resp = client.get("/admin/settings")
    assert resp.json() == {"min_support": 0.2, "min_confidence": 0.5, "user_weight": 10}


def test_admin_stats_top_items_and_rules(client):
    resp = client.get("/admin/stats/top-items")
    assert resp.status_code == 200
    top = resp.json()
    assert top[0]["item"] in {"milk", "bread"}  # os mais frequentes no dataset de teste

    client.put(
        "/admin/settings",
        json={"min_support": 0.1, "min_confidence": 0.3, "user_weight": 3},
    )
    resp = client.get("/admin/stats/rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) > 0
    assert set(rules[0].keys()) == {"antecedents", "consequents", "support", "confidence", "lift"}


def test_list_title_create_and_rename(client):
    headers = _register(client, email="t@example.com")

    # título opcional ao criar
    resp = client.post(
        "/lists", json={"items": ["milk"], "title": "  Jantar de sábado  "}, headers=headers
    )
    assert resp.status_code == 201
    lista = resp.json()
    assert lista["title"] == "Jantar de sábado"

    # sem título continua a funcionar (fica null)
    resp = client.post("/lists", json={"items": ["bread"]}, headers=headers)
    assert resp.json()["title"] is None

    # mudar o título
    resp = client.patch(f"/lists/{lista['id']}", json={"title": "Compras do mês"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Compras do mês"

    # título vazio remove o título
    resp = client.patch(f"/lists/{lista['id']}", json={"title": "   "}, headers=headers)
    assert resp.json()["title"] is None

    # outro utilizador não pode mexer na lista
    outro = _register(client, email="u@example.com")
    resp = client.patch(f"/lists/{lista['id']}", json={"title": "x"}, headers=outro)
    assert resp.status_code == 404


def test_recommendations_require_complete_antecedent(client):
    """Uma regra {A, B} -> C só pode ser aplicada se A e B estiverem ambos na
    lista; com apenas A, C não pode ser recomendado por essa regra. Testa o
    motor diretamente, com regras conhecidas, sem depender do Apriori."""
    import pandas as pd
    from app.routers.recommendations import get_engine

    engine = get_engine()
    regras = pd.DataFrame(
        {
            "antecedents": [frozenset({"milk", "bread"}), frozenset({"milk"})],
            "consequents": [frozenset({"butter"}), frozenset({"eggs"})],
            "support": [0.2, 0.3],
            "confidence": [0.5, 0.5],
            "lift": [3.0, 1.5],
        }
    )
    dat = engine.build_dataset()

    # só "milk": a primeira regra não se aplica; "eggs" vem da segunda
    so_milk = engine.generate_recommendations(["milk"], dat, 0.1, 0.1, rules=regras, limit=1)
    assert so_milk == ["eggs"]

    # "milk" e "bread": as duas regras aplicam-se e "butter" (lift 3,0) vem primeiro
    ambos = engine.generate_recommendations(
        ["milk", "bread"], dat, 0.1, 0.1, rules=regras, limit=2
    )
    assert ambos == ["butter", "eggs"]


def test_save_list_rejects_blank_items_and_removes_duplicates(client):
    headers = _register(client, email="v@example.com")

    resp = client.post("/lists", json={"items": ["   ", ""]}, headers=headers)
    assert resp.status_code == 422

    resp = client.post("/lists", json={"items": ["Milk", " milk ", "bread"]}, headers=headers)
    assert resp.status_code == 201
    assert [i["item_name"] for i in resp.json()["items"]] == ["milk", "bread"]
