"""Rota webhook WhatsApp — recebe mensagens Evolution API."""

import asyncio
import logging
import time
from collections import OrderedDict
from threading import Lock

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage

from src.config import settings
from src.graph import graph
from src.integrations.evolution import get_base64_from_media, parse_incoming_message, resolve_lid_to_phone, send_whatsapp_message, validate_api_key
from src.integrations.vision import identify_part_from_image
from src.integrations.whisper import transcribe_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["whatsapp"])

# Agregador de mensagens por telefone (evita processar mensagens fragmentadas)
_msg_buffer: dict[str, dict] = {}   # phone -> {"texts": [...], "parsed": {...}}
_msg_tasks: dict[str, asyncio.Task] = {}  # phone -> timer task
_buffer_lock = asyncio.Lock()


async def _flush_buffer(phone: str) -> None:
    """Aguarda o timer e processa todas as mensagens acumuladas do buffer."""
    await asyncio.sleep(settings.MESSAGE_BUFFER_WAIT_SECONDS)
    async with _buffer_lock:
        entry = _msg_buffer.pop(phone, None)
        _msg_tasks.pop(phone, None)
    if entry and entry["texts"]:
        combined = "\n".join(entry["texts"])
        await process_message(entry["parsed"], combined)


async def _buffer_message(phone: str, parsed: dict, text: str) -> None:
    """Adiciona mensagem ao buffer e (re)inicia o timer de espera."""
    async with _buffer_lock:
        if phone not in _msg_buffer:
            _msg_buffer[phone] = {"texts": [], "parsed": parsed}
        _msg_buffer[phone]["texts"].append(text)
        if phone in _msg_tasks and not _msg_tasks[phone].done():
            _msg_tasks[phone].cancel()
        _msg_tasks[phone] = asyncio.create_task(_flush_buffer(phone))


# Deduplicacao de messageId (TTL 60s, max 1000 entries)
_seen_messages: OrderedDict[str, float] = OrderedDict()
_seen_lock = Lock()
_DEDUP_TTL = 60
_DEDUP_MAX = 1000


def _is_duplicate(message_id: str) -> bool:
    """Verifica se messageId ja foi processado (TTL 60s)."""
    if not message_id:
        return False
    now = time.time()
    with _seen_lock:
        # Limpar expirados
        expired = [k for k, t in _seen_messages.items() if now - t > _DEDUP_TTL]
        for k in expired:
            del _seen_messages[k]
        # Limitar tamanho
        while len(_seen_messages) >= _DEDUP_MAX:
            _seen_messages.popitem(last=False)
        # Verificar duplicata
        if message_id in _seen_messages:
            return True
        _seen_messages[message_id] = now
        return False


# --- Rate limiting (per-phone) -------------------------------------------
_rate_limit: dict[str, list[float]] = {}
_rate_lock = Lock()


def _is_rate_limited(phone: str) -> bool:
    """Return True if phone exceeded RATE_LIMIT_MAX messages in RATE_LIMIT_WINDOW."""
    now = time.time()
    window = settings.RATE_LIMIT_WINDOW
    max_msgs = settings.RATE_LIMIT_MAX

    with _rate_lock:
        timestamps = _rate_limit.get(phone, [])
        # Remove expired timestamps
        timestamps = [t for t in timestamps if now - t < window]

        if len(timestamps) >= max_msgs:
            _rate_limit[phone] = timestamps
            return True

        timestamps.append(now)
        _rate_limit[phone] = timestamps
        return False


async def process_message(parsed: dict, message_text: str) -> None:
    """Processa mensagem pelo grafo LangGraph em thread separada."""
    phone = parsed["session_id"]
    config = {"configurable": {"thread_id": phone}}

    # Verifica timeout de sessao — preserva historico (LGPD/auditoria),
    # mas avanca session_start para o agente tratar como nova conversa
    session_start = 0
    try:
        snapshot = graph.get_state(config)
        last_activity = snapshot.values.get("last_activity", 0)
        if last_activity and (time.time() - last_activity) > settings.SESSION_TIMEOUT_HOURS * 3600:
            session_start = len(snapshot.values.get("messages", []))
            logger.info(
                "Sessao expirada para %s — nova sessao a partir da mensagem %d",
                parsed["session_id"], session_start,
            )
        else:
            session_start = snapshot.values.get("session_start", 0)
    except Exception:
        logger.debug("Sem checkpoint anterior para %s", parsed["session_id"])

    try:
        await asyncio.to_thread(
            graph.invoke,
            {
                "messages": [HumanMessage(content=message_text)],
                "session_id": parsed["session_id"],
                "chat_phone": parsed["chat_phone"],
                "last_activity": time.time(),
                "session_start": session_start,
            },
            config,
        )
    except Exception:
        logger.exception(
            "Erro ao processar mensagem para %s", parsed["session_id"]
        )


async def _handle_human_agent_message(parsed: dict, message_text: str, http_client) -> None:
    """Handles a fromMe=True message when customer is in human service.

    - If the message is the release command (#BOT#), resets the state and confirms to owner.
    - Otherwise, forwards the message to the customer.
    """
    phone = parsed["chat_phone"]
    config = {"configurable": {"thread_id": phone}}

    release_command = settings.HUMAN_RELEASE_COMMAND
    is_release = release_command and message_text.strip() == release_command

    if is_release:
        # Reset human service flags
        await asyncio.to_thread(
            graph.update_state,
            config,
            {"em_atendimento_humano": False, "requer_humano": False},
        )
        logger.info("Atendimento humano encerrado para %s — bot reativado", phone)
        # Confirm back to owner
        owner_phone = settings.STORE_OWNER_PHONE
        if owner_phone and http_client:
            confirmation = f"Atendimento humano encerrado para {phone}. Bot reativado."
            await send_whatsapp_message(http_client, owner_phone, confirmation)
    else:
        # Forward to customer
        if http_client:
            await send_whatsapp_message(http_client, phone, message_text)
            logger.info("Mensagem do atendente encaminhada para %s", phone)


async def _resolve_message_text(parsed: dict, request: Request) -> str:
    """Resolve message text from body, audio transcription, or image recognition."""
    message_text = parsed["body"]

    if not message_text and parsed["media_url"]:
        http_client = getattr(request.app.state, "http_client", None)
        message_text = await transcribe_audio(
            client=http_client, media_url=parsed["media_url"]
        )

    # Image recognition — download via Evolution API (WhatsApp URLs are encrypted)
    if not message_text and parsed.get("image_url"):
        http_client = getattr(request.app.state, "http_client", None)
        base64_uri = ""
        if http_client:
            base64_uri = await get_base64_from_media(
                http_client,
                parsed["raw_key"],
                parsed["raw_message"],
            )
        if base64_uri:
            message_text = await identify_part_from_image(
                http_client, base64_uri
            )
        else:
            logger.warning(
                "Could not download image as base64 for %s", parsed["chat_phone"]
            )
        if parsed.get("image_caption"):
            message_text = f"{parsed['image_caption']} {message_text}".strip()

    return message_text or ""


# ── Webhook Endpoint ─────────────────────────────────────────────────────────


@router.post("/whatsapp")
async def receive_whatsapp(request: Request):
    """Recebe webhook da Evolution API WhatsApp."""
    payload = await request.json()

    # Validar API key do header (skip em dev quando vazio)
    api_key = request.headers.get("apikey", "")
    instance_token = payload.get("apikey", "")
    if not validate_api_key(api_key, settings.EVOLUTION_API_KEY, instance_token):
        logger.warning("API key Evolution invalida")
        return PlainTextResponse("Forbidden", status_code=403)

    # Ignorar eventos que nao sao messages.upsert
    event = payload.get("event", "")
    if event != "messages.upsert":
        return PlainTextResponse("OK")

    parsed = parse_incoming_message(payload)

    # Resolve LID to real phone number
    if parsed.get("is_lid"):
        resolved = await asyncio.to_thread(resolve_lid_to_phone, parsed["push_name"])
        if resolved:
            parsed["session_id"] = resolved
            parsed["chat_phone"] = resolved
        else:
            logger.warning("Could not resolve LID for pushName=%s", parsed["push_name"])
            return PlainTextResponse("OK")

    # Ignorar mensagens de grupos
    if parsed.get("is_group"):
        return PlainTextResponse("OK")

    # Mensagens do proprio bot (fromMe=True): verificar se e resposta de atendente humano
    if parsed.get("from_me"):
        message_text = parsed["body"]
        if not message_text:
            return PlainTextResponse("OK")

        phone = parsed["chat_phone"]
        config = {"configurable": {"thread_id": phone}}
        try:
            snapshot = await asyncio.to_thread(graph.get_state, config)
            in_human_service = snapshot.values.get("em_atendimento_humano", False)
        except Exception:
            logger.debug("Sem checkpoint para %s — ignorando fromMe", phone)
            return PlainTextResponse("OK")

        if in_human_service:
            http_client = getattr(request.app.state, "http_client", None)
            await _handle_human_agent_message(parsed, message_text, http_client)

        return PlainTextResponse("OK")

    # Deduplicacao: ignorar messageId ja processado
    message_id = parsed.get("message_id", "")
    if _is_duplicate(message_id):
        logger.debug("Mensagem duplicada ignorada: %s", message_id)
        return PlainTextResponse("OK")

    # Rate limiting: ignorar telefone que excedeu limite
    phone = parsed["chat_phone"]
    if _is_rate_limited(phone):
        logger.warning("Rate limited phone=%s", phone)
        return PlainTextResponse("OK")

    message_text = await _resolve_message_text(parsed, request)
    if not message_text:
        return PlainTextResponse("OK")

    await _buffer_message(parsed["chat_phone"], parsed, message_text)

    return PlainTextResponse("OK")
