"""Dependencies do FastAPI partilhadas pelos vários routers."""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from . import models
from .database import get_db


def get_current_session(
    authorization: str = Header(..., alias="Authorization"),
    db: DBSession = Depends(get_db),
) -> models.Session:
    """Lê o token de sessão do cabeçalho Authorization (formato
    "Bearer <token>", ou apenas "<token>") e devolve a sessão
    correspondente, ou 401 se o token não existir/já tiver sido invalidado
    (ver caso de uso "Terminar Sessão" em Aplicacao_Mobile.docx)."""
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
    session = db.query(models.Session).filter(models.Session.token == token).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada. Autentica-te novamente.",
        )
    return session


def get_current_user(
    session: models.Session = Depends(get_current_session),
) -> models.User:
    return session.user
