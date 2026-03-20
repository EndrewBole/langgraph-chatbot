"""Integracao Chatwoot API — notificacoes de handoff."""

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def _get_base_url() -> str:
    return f"{settings.CHATWOOT_API_URL}/api/v1/accounts/{settings.CHATWOOT_ACCOUNT_ID}"


def _get_headers() -> dict[str, str]:
    return {
        "api_access_token": settings.CHATWOOT_API_KEY,
        "Content-Type": "application/json",
    }


def _find_conversation_by_phone(phone: str) -> int | None:
    """Busca conversation_id no Chatwoot pelo telefone do contato."""
    url = f"{_get_base_url()}/contacts/search"
    try:
        response = httpx.get(url, params={"q": phone}, headers=_get_headers(), timeout=10)
        response.raise_for_status()
        contacts = response.json().get("payload", [])
        for contact in contacts:
            contact_id = contact.get("id")
            if not contact_id:
                continue
            # Buscar conversas desse contato
            conv_url = f"{_get_base_url()}/contacts/{contact_id}/conversations"
            conv_resp = httpx.get(conv_url, headers=_get_headers(), timeout=10)
            conv_resp.raise_for_status()
            convs = conv_resp.json().get("payload", [])
            if convs:
                return convs[0].get("id")
    except Exception:
        logger.exception("Erro ao buscar conversa Chatwoot para %s", phone)
    return None


def notify_handoff(phone: str) -> bool:
    """Notifica Chatwoot quando handoff para humano e ativado.

    1. Adiciona label 'atendimento-humano'
    2. Envia nota interna alertando o agente
    3. Muda status para 'pending'
    """
    if not settings.CHATWOOT_API_URL or not settings.CHATWOOT_API_KEY:
        logger.debug("Chatwoot nao configurado, pulando notificacao")
        return False

    conversation_id = _find_conversation_by_phone(phone)
    if not conversation_id:
        logger.warning("Conversa Chatwoot nao encontrada para %s", phone)
        return False

    base = _get_base_url()
    headers = _get_headers()
    conv_url = f"{base}/conversations/{conversation_id}"
    success = True

    # 1) Adicionar label 'atendimento-humano'
    try:
        resp = httpx.get(conv_url, headers=headers, timeout=10)
        resp.raise_for_status()
        current_labels = resp.json().get("labels", [])
        if "atendimento-humano" not in current_labels:
            current_labels.append("atendimento-humano")
            label_resp = httpx.post(
                f"{conv_url}/labels",
                json={"labels": current_labels},
                headers=headers,
                timeout=10,
            )
            label_resp.raise_for_status()
            logger.info("Label 'atendimento-humano' adicionada na conversa %d", conversation_id)
    except Exception:
        logger.exception("Erro ao adicionar label Chatwoot")
        success = False

    # 2) Enviar nota interna
    try:
        httpx.post(
            f"{conv_url}/messages",
            json={
                "content": f"⚠️ Cliente {phone} solicitou atendimento humano. Bot pausado.",
                "message_type": "activity",
                "private": True,
            },
            headers=headers,
            timeout=10,
        ).raise_for_status()
        logger.info("Nota interna enviada na conversa %d", conversation_id)
    except Exception:
        logger.exception("Erro ao enviar nota Chatwoot")
        success = False

    # 3) Mudar status para pending
    try:
        httpx.post(
            f"{conv_url}/toggle_status",
            json={"status": "pending"},
            headers=headers,
            timeout=10,
        ).raise_for_status()
        logger.info("Conversa %d marcada como pending", conversation_id)
    except Exception:
        logger.exception("Erro ao mudar status Chatwoot")
        success = False

    # 4) Atribuir ao agente id 1
    try:
        httpx.post(
            f"{conv_url}/assignments",
            json={"assignee_id": 1},
            headers=headers,
            timeout=10,
        ).raise_for_status()
        logger.info("Conversa %d atribuida ao agente 1", conversation_id)
    except Exception:
        logger.exception("Erro ao atribuir agente Chatwoot")
        success = False

    return success


def send_chatwoot_message(conversation_id: int, text: str) -> bool:
    """Envia mensagem outgoing via Chatwoot API."""
    if not settings.CHATWOOT_API_URL or not settings.CHATWOOT_API_KEY:
        logger.debug("Chatwoot nao configurado, pulando envio")
        return False

    url = f"{_get_base_url()}/conversations/{conversation_id}/messages"
    try:
        resp = httpx.post(
            url,
            json={"content": text, "message_type": "outgoing"},
            headers=_get_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Mensagem enviada via Chatwoot na conversa %d", conversation_id)
        return True
    except Exception:
        logger.exception("Erro ao enviar mensagem Chatwoot na conversa %d", conversation_id)
        return False


def resolve_conversation(phone: str) -> bool:
    """Resolve conversa no Chatwoot e atribui ao agente bot (Temporalis CHAT).

    Chamado quando #BOT# e enviado — encerra handoff no Chatwoot.
    1. Muda status para 'resolved'
    2. Remove label 'atendimento-humano'
    3. Atribui ao agente bot (Temporalis CHAT)
    """
    if not settings.CHATWOOT_API_URL or not settings.CHATWOOT_API_KEY:
        return False

    conversation_id = _find_conversation_by_phone(phone)
    if not conversation_id:
        logger.warning("Conversa Chatwoot nao encontrada para %s", phone)
        return False

    base = _get_base_url()
    headers = _get_headers()
    conv_url = f"{base}/conversations/{conversation_id}"
    success = True

    # 1) Mudar status para resolved
    try:
        httpx.post(
            f"{conv_url}/toggle_status",
            json={"status": "resolved"},
            headers=headers,
            timeout=10,
        ).raise_for_status()
        logger.info("Conversa %d marcada como resolved", conversation_id)
    except Exception:
        logger.exception("Erro ao resolver conversa Chatwoot")
        success = False

    # 2) Remover label 'atendimento-humano'
    try:
        resp = httpx.get(conv_url, headers=headers, timeout=10)
        resp.raise_for_status()
        current_labels = resp.json().get("labels", [])
        if "atendimento-humano" in current_labels:
            current_labels.remove("atendimento-humano")
            httpx.post(
                f"{conv_url}/labels",
                json={"labels": current_labels},
                headers=headers,
                timeout=10,
            ).raise_for_status()
            logger.info("Label 'atendimento-humano' removida da conversa %d", conversation_id)
    except Exception:
        logger.exception("Erro ao remover label Chatwoot")
        success = False

    return success
