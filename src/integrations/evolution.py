"""Integracao Evolution API WhatsApp."""

import base64
import hmac
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def _get_base_url() -> str:
    """Retorna a URL base da Evolution API para envio de mensagens."""
    return f"{settings.EVOLUTION_API_URL}/message/sendText/{settings.EVOLUTION_INSTANCE_NAME}"


def _get_headers() -> dict[str, str]:
    """Retorna headers padrao para Evolution API."""
    return {
        "apikey": settings.EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }


def validate_api_key(api_key: str, expected_key: str, instance_token: str = "") -> bool:
    """Valida API key do header Evolution API."""
    if not expected_key:
        return True  # dev mode
    if hmac.compare_digest(api_key, expected_key):
        return True
    if instance_token and hmac.compare_digest(api_key, instance_token):
        return True
    if instance_token and hmac.compare_digest(instance_token, expected_key):
        return True
    return False


def parse_incoming_message(payload: dict) -> dict:
    """Extrai campos do payload JSON do webhook Evolution API.

    Formato esperado: messages.upsert event com data.key e data.message.
    Suporta LID format (remoteJid @lid) usando campo 'sender' do payload.
    """
    event = payload.get("event", "")
    data = payload.get("data") or {}
    key = data.get("key") or {}
    message = data.get("message") or {}

    remote_jid = key.get("remoteJid", "")
    is_group = remote_jid.endswith("@g.us")

    # LID format: mark for async resolution in webhook handler
    is_lid = remote_jid.endswith("@lid")
    phone = remote_jid.replace("@s.whatsapp.net", "").replace("@g.us", "").replace("@lid", "")

    # Text: conversation or extendedTextMessage.text
    text = message.get("conversation", "")
    if not text:
        extended = message.get("extendedTextMessage") or {}
        text = extended.get("text", "")

    # Audio
    audio = message.get("audioMessage") or {}
    audio_url = audio.get("url", "")

    # Image
    image = message.get("imageMessage") or {}
    image_url = image.get("url", "")
    image_caption = image.get("caption", "")

    return {
        "event": event,
        "session_id": phone,
        "chat_phone": phone,
        "body": text,
        "media_url": audio_url,
        "image_url": image_url,
        "image_caption": image_caption,
        "from_me": key.get("fromMe", False),
        "is_group": is_group,
        "is_lid": is_lid,
        "push_name": data.get("pushName", ""),
        "message_id": key.get("id", ""),
        "raw_key": key,
        "raw_message": message,
    }


def resolve_lid_to_phone(push_name: str) -> str:
    """Resolve LID to real phone number via Evolution API contacts lookup.

    Queries contacts by pushName and returns the first match with @s.whatsapp.net.
    Returns empty string if no match found.
    """
    if not push_name:
        return ""
    url = f"{settings.EVOLUTION_API_URL}/chat/findContacts/{settings.EVOLUTION_INSTANCE_NAME}"
    headers = _get_headers()
    try:
        response = httpx.post(
            url,
            json={"where": {"pushName": push_name}},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        contacts = response.json()
        for contact in contacts:
            jid = contact.get("remoteJid", "")
            if jid.endswith("@s.whatsapp.net"):
                phone = jid.replace("@s.whatsapp.net", "")
                logger.info("LID resolved: %s -> %s", push_name, phone)
                return phone
    except Exception:
        logger.exception("Failed to resolve LID for pushName=%s", push_name)
    return ""


async def get_base64_from_media(
    client: httpx.AsyncClient,
    message_key: dict,
    message_data: dict,
) -> str:
    """Get base64 data URI from media message via Evolution API.

    Uses the /chat/getBase64FromMediaMessage endpoint to download encrypted
    WhatsApp media. Returns a data URI string (data:{mimetype};base64,...)
    or empty string on failure.
    """
    url = (
        f"{settings.EVOLUTION_API_URL}"
        f"/chat/getBase64FromMediaMessage/{settings.EVOLUTION_INSTANCE_NAME}"
    )
    headers = _get_headers()
    payload = {
        "message": {
            "key": message_key,
            "message": message_data,
        },
        "convertToMp4": False,
    }

    try:
        response = await client.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        base64_data = data.get("base64", "")
        mimetype = data.get("mimetype", "image/jpeg")
        if base64_data:
            # Strip data URI prefix if Evolution API already includes it
            if base64_data.startswith("data:"):
                return base64_data
            return f"data:{mimetype};base64,{base64_data}"
        return ""
    except Exception:
        logger.exception("Failed to get base64 from Evolution API media endpoint")
        return ""


async def send_whatsapp_message(
    client: httpx.AsyncClient,
    to_phone: str,
    body: str,
) -> bool:
    """Envia mensagem WhatsApp via Evolution API (async)."""
    url = _get_base_url()
    headers = _get_headers()
    json_data = {"number": to_phone, "text": body}

    try:
        response = await client.post(url, json=json_data, headers=headers, timeout=10)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error("Evolution API error: %s — %s", e.response.status_code, e.response.text)
        return False
    except httpx.HTTPError as e:
        logger.error("Evolution API request error: %s", e)
        return False


def send_link_button(
    to_phone: str,
    url: str,
    title: str = "Comprar / Visualizar",
    message: str = "",
) -> bool:
    """Envia texto com link embutido via sendText.

    Inclui o link no final do texto do produto.
    sendButtons nao e confiavel no Baileys (WhatsApp silencia a entrega).
    """
    text = f"{message}\n\n🛒 {title}\n{url}" if message else f"{title}\n{url}"
    endpoint = _get_base_url()
    headers = _get_headers()
    json_data = {"number": to_phone, "text": text}

    try:
        response = httpx.post(endpoint, json=json_data, headers=headers, timeout=10)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error("Evolution API send-link error: %s — %s", e.response.status_code, e.response.text)
        return False
    except httpx.HTTPError as e:
        logger.error("Evolution API send-link request error: %s", e)
        return False


def send_message(to_phone: str, body: str) -> bool:
    """Envia mensagem WhatsApp via Evolution API (sync) — usado pelo graph node."""
    url = _get_base_url()
    headers = _get_headers()
    json_data = {"number": to_phone, "text": body}

    try:
        response = httpx.post(url, json=json_data, headers=headers, timeout=10)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error("Evolution API error: %s — %s", e.response.status_code, e.response.text)
        return False
    except httpx.HTTPError as e:
        logger.error("Evolution API request error: %s", e)
        return False
