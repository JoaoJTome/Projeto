"""Ponto de entrada da API backend.

Corre com:  uvicorn app.main:app --reload
(a partir da pasta api_backend/, com o ambiente virtual do requirements.txt
ativado e o dataSort.csv colocado na raiz do projeto - ver README.md).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import engine as db_engine, ensure_schema
from .routers import admin, auth, lists, recommendations

# Cria as tabelas na base de dados SQLite se ainda não existirem. Para um
# projeto desta dimensão isto é suficiente; não é usado um sistema de
# migrações (ex.: Alembic) porque o esquema não deverá mudar com frequência.
models.Base.metadata.create_all(bind=db_engine)
# Acrescenta colunas novas (ex.: título das listas) a uma app.db antiga.
ensure_schema(db_engine)

app = FastAPI(
    title="API - Análise de Cesto de Compras",
    description=(
        "Backend partilhado pela aplicação mobile e pela aplicação de "
        "backoffice. É o único ponto de cálculo das regras de associação "
        "(Apriori) e das recomendações - ver Arquitetura_Geral_Sistema.md."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(lists.router)
app.include_router(recommendations.router)
app.include_router(admin.router)


@app.get("/health", tags=["infra"])
def health_check():
    return {"status": "ok"}
