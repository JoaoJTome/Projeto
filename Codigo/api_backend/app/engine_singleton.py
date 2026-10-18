"""Instância única e partilhada do motor de recomendação.

"""
from functools import lru_cache

from .recommendation_engine import RecommendationEngine


@lru_cache
def get_engine() -> RecommendationEngine:
    return RecommendationEngine()
