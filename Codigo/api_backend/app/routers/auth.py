"""Autenticação: registo, login e logout.

Implementa os casos de uso "Criar Conta", "Autenticar-se (Login)" e
"Terminar Sessão" documentados em Aplicacao_Mobile.docx.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from .. import models, schemas, security
from ..database import get_db
from ..dependencies import get_current_session

router = APIRouter(prefix="/auth", tags=["autenticação"])


@router.post(
    "/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED
)
def register(payload: schemas.RegisterRequest, db: DBSession = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Este email já está registado."
        )

    user = models.User(
        email=payload.email, password_hash=security.hash_password(payload.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = models.Session(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return schemas.TokenResponse(token=session.token)


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: DBSession = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou palavra-passe inválidos.",
        )

    session = models.Session(user_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return schemas.TokenResponse(token=session.token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    session: models.Session = Depends(get_current_session), db: DBSession = Depends(get_db)
):
    # Invalida apenas o token usado neste pedido (e não todas as sessões do
    # utilizador), para não desautenticar outros dispositivos onde ele
    # também tenha sessão iniciada.
    db.delete(session)
    db.commit()
    return None
