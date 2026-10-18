"""Modelos SQLAlchemy (tabelas da base de dados).

"""
import secrets
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # bcrypt gera e guarda o salt como parte do próprio hash (ver security.py);
    # não é preciso guardar o salt numa coluna separada.
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    shopping_lists = relationship(
        "ShoppingList", back_populates="user", cascade="all, delete-orphan"
    )
    sessions = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """Token de sessão emitido no login/registo (ver Aplicacao_Mobile.docx,
    casos de uso "Autenticar-se" e "Terminar Sessão"). É guardado em base de
    dados, em vez de ser um JWT sem estado, precisamente para que "Terminar
    Sessão" possa invalidar o token do lado do servidor de forma imediata."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(
        String, unique=True, index=True, nullable=False,
        default=lambda: secrets.token_urlsafe(32),
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="sessions")


class ShoppingList(Base):
    """Uma lista de compras guardada por um utilizador da app mobile (caso
    de uso "Guardar Lista de Compras"). Contribui também, pesada por
    Settings.user_weight, para as recomendações pessoais futuras desse
    mesmo utilizador."""

    __tablename__ = "shopping_lists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Título opcional dado pelo utilizador (ex.: "Jantar de sábado"). Se
    # ficar vazio, a app mostra um título por omissão baseado na data.
    title = Column(String(80), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    user = relationship("User", back_populates="shopping_lists")
    items = relationship(
        "ShoppingListItem", back_populates="shopping_list", cascade="all, delete-orphan"
    )


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id = Column(Integer, primary_key=True, index=True)
    shopping_list_id = Column(Integer, ForeignKey("shopping_lists.id"), nullable=False)
    item_name = Column(String, nullable=False)

    shopping_list = relationship("ShoppingList", back_populates="items")


class Settings(Base):
    """Linha única com os parâmetros do motor de recomendação.

    Configurados no backoffice (página "Opções") e lidos pela API sempre
    que calcula regras/recomendações - tanto para o backoffice como para a
    app mobile - para que ambos usem sempre os mesmos valores.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    min_support = Column(Float, nullable=False, default=0.01)
    min_confidence = Column(Float, nullable=False, default=0.2)
    # Quantas vezes cada lista de compras guardada por um utilizador da app
    # mobile é repetida no cálculo das SUAS recomendações pessoais (ver
    # RecommendationEngine.build_dataset). Não afeta as estatísticas globais
    # do backoffice, que usam sempre só o dataset base.
    user_weight = Column(Integer, nullable=False, default=1000)
