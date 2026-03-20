"""Transcrição de áudio via OpenAI Whisper — async."""

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(
    client: httpx.AsyncClient,
    media_url: str,
) -> str:
    """Baixa áudio e transcreve via Whisper."""
    try:
        audio_response = await client.get(
            media_url,
            timeout=30,
        )
        audio_response.raise_for_status()
        audio_bytes = audio_response.content

        response = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            files={"file": ("audio.ogg", audio_bytes, "audio/ogg")},
            data={"model": settings.WHISPER_MODEL},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("text", "")
    except httpx.HTTPStatusError as e:
        logger.error("Whisper API error: %s", e.response.status_code)
        return ""
    except httpx.HTTPError as e:
        logger.error("Whisper request error: %s", e)
        return ""
