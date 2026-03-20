"""Rota webhook Chatwoot -- eventos de conversa e proxy de mensagens outgoing."""

import asyncio
import logging
import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage

from src.config import settings
from src.graph import graph
from src.integrations.chatwoot import resolve_conversation, send_chatwoot_message
from src.integrations.evolution import send_whatsapp_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["chatwoot"])


# ── Instagram DM via Chatwoot bridge ─────────────────────────────────────────

_INSTAGRAM_CHANNELS = {"Channel::Instagram", "instagram"}


def _is_instagram_channel(payload: dict) -> bool:
    """Detecta se o payload vem de um inbox Instagram."""
    channel = payload.get("conversation", {}).get("channel", "")
    return channel in _INSTAGRAM_CHANNELS


async def _process_instagram_message(payload: dict) -> None:
    """Processa mensagem Instagram DM via LangGraph pipeline."""
    content = payload.get("content", "").strip()
    if not content:
        return

    conversation = payload.get("conversation", {})
    conversation_id = conversation.get("id")
    sender = payload.get("sender", {})
    contact_id = sender.get("id", 0)

    thread_id = f"ig_{contact_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # Session timeout check
    session_start = 0
    try:
        snapshot = graph.get_state(config)
        last_activity = snapshot.values.get("last_activity", 0)
        if last_activity and (time.time() - last_activity) > settings.SESSION_TIMEOUT_HOURS * 3600:
            session_start = len(snapshot.values.get("messages", []))
            logger.info("Instagram session expired for %s — new session at %d", thread_id, session_start)
        else:
            session_start = snapshot.values.get("session_start", 0)
    except Exception:
        logger.debug("No checkpoint for Instagram thread %s", thread_id)

    try:
        await asyncio.to_thread(
            graph.invoke,
            {
                "messages": [HumanMessage(content=content)],
                "session_id": thread_id,
                "chat_phone": thread_id,
                "last_activity": time.time(),
                "session_start": session_start,
                "channel": "instagram",
                "chatwoot_conversation_id": conversation_id,
            },
            config,
        )
    except Exception:
        logger.exception("Erro ao processar mensagem Instagram para %s", thread_id)


# ── Webhook endpoint ─────────────────────────────────────────────────────────


@router.post("/chatwoot")
async def chatwoot_webhook(request: Request) -> PlainTextResponse:
    """Recebe webhook do Chatwoot para eventos de conversa."""
    payload = await request.json()
    event = payload.get("event")

    # Instagram DM: message_created from Instagram inbox
    if event == "message_created":
        message_type = payload.get("message_type")
        if message_type != "incoming":
            return PlainTextResponse("OK")
        if not _is_instagram_channel(payload):
            return PlainTextResponse("OK")
        content = payload.get("content", "").strip()
        if not content:
            return PlainTextResponse("OK")
        asyncio.create_task(_process_instagram_message(payload))
        return PlainTextResponse("OK")

    # conversation_status_changed fires for all status changes; filter resolved only
    if event != "conversation_status_changed":
        return PlainTextResponse("OK")

    status = payload.get("conversation", {}).get("status")
    if status != "resolved":
        return PlainTextResponse("OK")

    # Detect channel for resolved handler
    is_instagram = _is_instagram_channel(payload)

    if is_instagram:
        # Instagram resolved: use contact_id thread
        sender = payload.get("conversation", {}).get("meta", {}).get("sender", {})
        contact_id = sender.get("id", 0)
        thread_id = f"ig_{contact_id}"
        conversation_id = payload.get("conversation", {}).get("id")

        config = {"configurable": {"thread_id": thread_id}}
        await asyncio.to_thread(
            graph.update_state,
            config,
            {"em_atendimento_humano": False, "requer_humano": False, "tentativas_categoria_e": 0},
        )
        logger.info("Chatwoot resolved Instagram conversation for %s -- bot reactivated", thread_id)

        if conversation_id:
            send_chatwoot_message(conversation_id, "Atendimento encerrado. Estou de volta para ajudar!")
    else:
        # WhatsApp resolved: existing flow
        phone = (
            payload.get("conversation", {})
            .get("meta", {})
            .get("sender", {})
            .get("phone_number", "")
        )
        phone = phone.lstrip("+")

        if not phone:
            logger.warning("Chatwoot webhook sem phone_number no payload")
            return PlainTextResponse("OK")

        config = {"configurable": {"thread_id": phone}}
        await asyncio.to_thread(
            graph.update_state,
            config,
            {"em_atendimento_humano": False, "requer_humano": False, "tentativas_categoria_e": 0},
        )
        logger.info("Chatwoot resolved conversation for %s -- bot reactivated", phone)

        http_client = getattr(request.app.state, "http_client", None)
        if http_client:
            await send_whatsapp_message(
                http_client,
                phone,
                "Atendimento encerrado. Estou de volta para ajudar!",
            )

    return PlainTextResponse("OK")


# ── Chatwoot outgoing proxy ──────────────────────────────────────────────────


@router.post("/chatwoot/outgoing")
async def chatwoot_outgoing_proxy(request: Request) -> PlainTextResponse:
    """Proxy entre Chatwoot e Evolution API para mensagens outgoing.

    Intercepta mensagens do agente antes de enviar ao WhatsApp:
    - Filtra #BOT# (reseta handoff, nao envia ao cliente)
    - Remove quebras de linha extras no final
    - Responde rapido ao Chatwoot (evita timeout)
    """
    payload = await request.json()

    # Extrair conteudo da mensagem
    content = payload.get("content", "")
    message_type = payload.get("message_type")

    # Somente processar mensagens outgoing (agente -> cliente)
    if message_type != "outgoing":
        # Encaminhar ao Evolution API sem alteracao
        asyncio.create_task(_forward_to_evolution(payload))
        return PlainTextResponse("OK")

    # Verificar se e o comando de liberacao #BOT#
    release_command = settings.HUMAN_RELEASE_COMMAND
    if release_command and content.strip() == release_command:
        logger.info("Comando %s recebido via Chatwoot — resetando handoff", release_command)
        # Extrair telefone do contato
        phone = _extract_phone_from_payload(payload)
        if phone:
            config = {"configurable": {"thread_id": phone}}
            await asyncio.to_thread(
                graph.update_state,
                config,
                {"em_atendimento_humano": False, "requer_humano": False, "tentativas_categoria_e": 0},
            )
            # Resolver conversa e atribuir ao bot no Chatwoot
            await asyncio.to_thread(resolve_conversation, phone)
            logger.info("Handoff encerrado para %s via Chatwoot", phone)
        # NAO encaminha ao Evolution API — mensagem nao chega ao cliente
        return PlainTextResponse("OK")

    # Limpar quebras de linha extras no final
    if content:
        payload["content"] = content.rstrip("\n\r ")

    # Encaminhar ao Evolution API em background (responde rapido ao Chatwoot)
    asyncio.create_task(_forward_to_evolution(payload))
    return PlainTextResponse("OK")


def _extract_phone_from_payload(payload: dict) -> str | None:
    """Extrai telefone do contato a partir do payload Chatwoot outgoing."""
    # Tenta conversation.meta.sender.phone_number
    phone = (
        payload.get("conversation", {})
        .get("meta", {})
        .get("sender", {})
        .get("phone_number", "")
    )
    if phone:
        return phone.lstrip("+")
    # Tenta conversation.contact_inbox.source_id (formato: phone@s.whatsapp.net)
    source_id = (
        payload.get("conversation", {})
        .get("contact_inbox", {})
        .get("source_id", "")
    )
    if source_id and "@" in source_id:
        return source_id.split("@")[0]
    return None


async def _forward_to_evolution(payload: dict) -> None:
    """Encaminha payload ao Evolution API Chatwoot webhook."""
    evolution_url = f"{settings.EVOLUTION_API_URL}/chatwoot/webhook/{settings.EVOLUTION_INSTANCE_NAME}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(evolution_url, json=payload)
            resp.raise_for_status()
            logger.debug("Payload encaminhado ao Evolution API: %s", resp.status_code)
    except Exception:
        logger.exception("Erro ao encaminhar payload ao Evolution API")
