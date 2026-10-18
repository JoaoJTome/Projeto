"""Configuração da base de dados (SQLite) partilhada por toda a API.

"""
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False é necessário porque o Uvicorn pode atender
# pedidos em threads diferentes; cada pedido continua a usar a sua própria
# sessão (ver get_db), pelo que isto é seguro.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency do FastAPI: abre uma sessão de base de dados por pedido e
    garante que é sempre fechada no final, mesmo em caso de erro."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema(bind=None) -> None:
    bind = bind or engine
    inspector = inspect(bind)
    if "shopping_lists" not in inspector.get_table_names():
        return
    colunas = {c["name"] for c in inspector.get_columns("shopping_lists")}
    if "title" not in colunas:
        with bind.begin() as conn:
            conn.execute(text("ALTER TABLE shopping_lists ADD COLUMN title VARCHAR(80)"))
