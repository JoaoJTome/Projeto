import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.recommendation_engine import RecommendationEngine  # noqa: E402

# Dataset sintético pequeno, só para os testes: evita depender do
# dataSort.csv real (que não faz parte do repositório de testes) e mantém
# os testes rápidos e determinísticos.
SAMPLE_TRANSACOES = [
    ["milk", "bread", "eggs"],
    ["milk", "bread"],
    ["milk", "butter"],
    ["bread", "butter", "eggs"],
    ["milk", "bread", "butter"],
    ["milk", "eggs"],
    ["bread", "eggs"],
    ["milk", "bread", "eggs", "butter"],
    ["milk", "bread"],
    ["butter", "eggs"],
]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # --- base de dados SQLite isolada e vazia para este teste ---
    db_path = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # --- motor de recomendação com o dataset sintético acima ---
    csv_path = tmp_path / "dataSort_test.csv"
    df = pd.DataFrame(SAMPLE_TRANSACOES)
    df.insert(0, "Unnamed: 0", range(len(df)))
    df.to_csv(csv_path, index=False)

    test_recommendation_engine = RecommendationEngine(csv_path=csv_path)
    # Cada router importou "get_engine" para o seu próprio namespace
    # (from ..engine_singleton import get_engine), por isso o monkeypatch
    # tem de ser feito módulo a módulo, e não só em app.engine_singleton.
    monkeypatch.setattr("app.routers.admin.get_engine", lambda: test_recommendation_engine)
    monkeypatch.setattr("app.routers.lists.get_engine", lambda: test_recommendation_engine)
    monkeypatch.setattr(
        "app.routers.recommendations.get_engine", lambda: test_recommendation_engine
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
