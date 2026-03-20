"""Image recognition for motorcycle part identification via OpenAI Vision."""

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

VISION_PROMPT = (
    "Voce e um especialista em pecas de motos. "
    "Que peca de moto aparece nesta imagem? "
    "Retorne apenas o nome da peca e modelo/marca se visivel. "
    "Se nao conseguir identificar, diga 'nao identificado'."
)


async def identify_part_from_image(
    client: httpx.AsyncClient,
    image_url: str,
) -> str:
    """Send image to OpenAI Vision API and return part description.

    Uses the chat completions endpoint with image_url content type.
    Returns empty string on error or when vision is disabled.
    """
    if not settings.VISION_ENABLED:
        return ""

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, cannot identify image")
        return ""

    try:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={
                "model": settings.VISION_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {"type": "text", "text": VISION_PROMPT},
                        ],
                    }
                ],
                "max_tokens": 150,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        description = data["choices"][0]["message"]["content"].strip()
        logger.info("Vision identified: %s", description)
        return description
    except httpx.HTTPStatusError as e:
        logger.error("Vision API error: %s — %s", e.response.status_code, e.response.text)
        return ""
    except Exception:
        logger.exception("Failed to identify part from image")
        return ""
