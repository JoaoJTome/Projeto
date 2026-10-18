"""Esquemas Pydantic - validação dos pedidos/respostas da API."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    password_confirmation: str

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.password_confirmation:
            raise ValueError("as palavras-passe não coincidem")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"


class ShoppingListCreate(BaseModel):
    items: List[str] = Field(min_length=1)
    title: Optional[str] = Field(default=None, max_length=80)


class ShoppingListUpdate(BaseModel):
    """Alteração do título de uma lista já guardada. Um título vazio ou
    só com espaços remove o título (a app volta a mostrar o por omissão)."""

    title: Optional[str] = Field(default=None, max_length=80)


class ShoppingListItemOut(BaseModel):
    item_name: str

    model_config = ConfigDict(from_attributes=True)


class ShoppingListOut(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: datetime
    items: List[ShoppingListItemOut]

    model_config = ConfigDict(from_attributes=True)


class RecommendationRequest(BaseModel):
    current_items: List[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    recommended_items: List[str]


class SettingsSchema(BaseModel):
    # Os mesmos limites dos sliders do backoffice. O suporte mínimo tem de ser
    # estritamente positivo: com 0, o Apriori consideraria frequentes todas
    # as combinações de itens.
    min_support: float = Field(gt=0.0, le=1.0)
    min_confidence: float = Field(gt=0.0, le=1.0)
    user_weight: int = Field(ge=1, le=1000)


class AssociationRuleOut(BaseModel):
    antecedents: List[str]
    consequents: List[str]
    support: float
    confidence: float
    lift: float


class TopItemOut(BaseModel):
    item: str
    contagem: int
    percentagem: float
