"""Itens disponíveis e listas de compras do utilizador autenticado.

Implementa os casos de uso "Adicionar Item à Lista" (via GET /items, para
pesquisar/selecionar), "Guardar Lista de Compras" e "Consultar Histórico de
Listas", documentados em Aplicacao_Mobile.docx.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user
from ..engine_singleton import get_engine

router = APIRouter(tags=["listas de compras"])


@router.get("/items", response_model=List[str])
def list_items(search: str = ""):
    """Lista de itens do dataset, usada pela app mobile para pesquisar e
    selecionar produtos ao construir uma nova lista de compras."""
    engine = get_engine()
    items = engine.item_list
    if search:
        termo = search.lower()
        items = [item for item in items if termo in item]
    return items


@router.get("/lists", response_model=List[schemas.ShoppingListOut])
def get_lists(
    current_user: models.User = Depends(get_current_user), db: DBSession = Depends(get_db)
):
    """Histórico de listas de compras do utilizador autenticado, mais
    recentes primeiro (caso de uso "Consultar Histórico de Listas")."""
    return (
        db.query(models.ShoppingList)
        .filter(models.ShoppingList.user_id == current_user.id)
        .order_by(models.ShoppingList.created_at.desc())
        .all()
    )


@router.post(
    "/lists", response_model=schemas.ShoppingListOut, status_code=201
)
def create_list(
    payload: schemas.ShoppingListCreate,
    current_user: models.User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Guarda a lista de compras atual do utilizador (caso de uso "Guardar
    Lista de Compras"), com um título opcional. Esta lista passa a contribuir, pesada por
    Settings.user_weight, para as suas recomendações pessoais futuras."""
    # Normaliza os itens (sem espaços nas pontas, minúsculas), ignora os
    # vazios e remove duplicados, mantendo a ordem. A validação de "pelo
    # menos um item" tem de ser repetida depois da normalização: uma lista
    # só com textos vazios passa no esquema mas ficaria sem itens.
    itens = list(dict.fromkeys(item.strip().lower() for item in payload.items if item.strip()))
    if not itens:
        raise HTTPException(
            status_code=422,
            detail="A lista tem de ter pelo menos um item.",
        )
    shopping_list = models.ShoppingList(
        user_id=current_user.id, title=_clean_title(payload.title)
    )
    shopping_list.items = [models.ShoppingListItem(item_name=item) for item in itens]
    db.add(shopping_list)
    db.commit()
    db.refresh(shopping_list)
    return shopping_list


@router.patch("/lists/{list_id}", response_model=schemas.ShoppingListOut)
def update_list(
    list_id: int,
    payload: schemas.ShoppingListUpdate,
    current_user: models.User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Altera o título de uma lista guardada. Só o dono da lista o pode
    fazer; para qualquer outro utilizador a lista "não existe" (404)."""
    shopping_list = (
        db.query(models.ShoppingList)
        .filter(
            models.ShoppingList.id == list_id,
            models.ShoppingList.user_id == current_user.id,
        )
        .first()
    )
    if shopping_list is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lista não encontrada")
    shopping_list.title = _clean_title(payload.title)
    db.commit()
    db.refresh(shopping_list)
    return shopping_list


def _clean_title(title):
    """Remove espaços a mais; um título vazio é guardado como NULL."""
    if title is None:
        return None
    title = title.strip()
    return title or None
