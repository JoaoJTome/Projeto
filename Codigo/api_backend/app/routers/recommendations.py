"""Recomendações personalizadas para o utilizador autenticado.

Implementa o caso de uso "Consultar Itens Recomendados" de
Aplicacao_Mobile.docx: o histórico de listas já guardadas pelo utilizador é
pesado com maior relevância (Settings.user_weight) no cálculo das regras de
associação usadas para o recomendar.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user
from ..engine_singleton import get_engine
from .admin import get_or_create_settings

router = APIRouter(tags=["recomendações"])


@router.post("/recommendations", response_model=schemas.RecommendationResponse)
def recommend(
    payload: schemas.RecommendationRequest,
    current_user: models.User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    settings = get_or_create_settings(db)
    engine = get_engine()

    past_lists = (
        db.query(models.ShoppingList)
        .filter(models.ShoppingList.user_id == current_user.id)
        .all()
    )
    user_transactions = [[item.item_name for item in lst.items] for lst in past_lists]

    dat = engine.build_dataset(user_transactions, settings.user_weight)
    current_items = [item.strip().lower() for item in payload.current_items if item.strip()]
    recommended = engine.generate_recommendations(
        current_items, dat, settings.min_support, settings.min_confidence
    )
    return schemas.RecommendationResponse(recommended_items=recommended)
