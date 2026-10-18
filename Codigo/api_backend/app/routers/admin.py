"""Endpoints de backoffice: parâmetros do motor e estatísticas globais.

"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from .. import models, schemas
from ..database import get_db
from ..engine_singleton import get_engine

router = APIRouter(prefix="/admin", tags=["backoffice"])


def get_or_create_settings(db: DBSession) -> models.Settings:
    """Devolve a linha (única) de Settings, criando-a com valores por
    omissão na primeira utilização da API."""
    settings = db.query(models.Settings).first()
    if settings is None:
        settings = models.Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/settings", response_model=schemas.SettingsSchema)
def read_settings(db: DBSession = Depends(get_db)):
    settings = get_or_create_settings(db)
    return schemas.SettingsSchema(
        min_support=settings.min_support,
        min_confidence=settings.min_confidence,
        user_weight=settings.user_weight,
    )


@router.put("/settings", response_model=schemas.SettingsSchema)
def update_settings(payload: schemas.SettingsSchema, db: DBSession = Depends(get_db)):
    """Atualiza os parâmetros do motor de recomendação. Passam a ser usados
    de imediato tanto pelas estatísticas do backoffice como pelas
    recomendações calculadas para a app mobile."""
    settings = get_or_create_settings(db)
    settings.min_support = payload.min_support
    settings.min_confidence = payload.min_confidence
    settings.user_weight = payload.user_weight
    db.commit()
    return payload


@router.get("/stats/top-items", response_model=List[schemas.TopItemOut])
def top_items(db: DBSession = Depends(get_db)):
    """Top de itens mais frequentes do dataset global (não depende de
    suporte/confiança, nem do histórico de nenhum utilizador em particular
    - é sempre a mesma estatística global)."""
    engine = get_engine()
    dat = engine.build_dataset()
    top = engine.compute_top_items(dat)
    return [
        schemas.TopItemOut(
            item=row.item, contagem=int(row.contagem), percentagem=float(row.percentagem)
        )
        for row in top.itertuples()
    ]


@router.get("/stats/rules", response_model=List[schemas.AssociationRuleOut])
def association_rules_endpoint(db: DBSession = Depends(get_db)):
    """Regras de associação do dataset global, calculadas com os parâmetros
    atualmente guardados em Settings (página "Opções" do backoffice)."""
    settings = get_or_create_settings(db)
    engine = get_engine()
    dat = engine.build_dataset()
    rules = engine.generate_association_rules(dat, settings.min_support, settings.min_confidence)
    return [
        schemas.AssociationRuleOut(
            antecedents=sorted(row.antecedents),
            consequents=sorted(row.consequents),
            support=float(row.support),
            confidence=float(row.confidence),
            lift=float(row.lift),
        )
        for row in rules.itertuples()
    ]
