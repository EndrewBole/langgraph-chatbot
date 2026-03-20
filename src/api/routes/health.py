"""Rota de health check — status do sistema."""

import logging

from fastapi import APIRouter

from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Retorna status de saude do sistema."""
    database = "connected" if settings.DATABASE_URL else "disconnected"
    evolution = (
        "configured"
        if settings.EVOLUTION_API_URL and settings.EVOLUTION_API_KEY
        else "not_configured"
    )
    chatwoot = (
        "configured"
        if settings.CHATWOOT_API_URL and settings.CHATWOOT_API_KEY
        else "not_configured"
    )
    return {
        "status": "ok",
        "version": "0.12.0",
        "database": database,
        "evolution": evolution,
        "chatwoot": chatwoot,
    }
