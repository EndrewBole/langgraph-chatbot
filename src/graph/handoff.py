"""Human handoff node — detects #HUMANO# tag, counts attempts, escalates."""

import logging

from langchain_core.messages import AIMessage

from src.config import settings
from src.integrations.chatwoot import notify_handoff
from src.integrations.evolution import send_message

logger = logging.getLogger(__name__)

HUMANO_TAG = "#HUMANO#"
HANDOFF_THRESHOLD = 3
HANDOFF_MESSAGE = (
    "Entendi! Vou transferir você para um de nossos atendentes. "
    "Por favor, aguarde um momento."
)


def human_handoff_node(state: dict) -> dict:
    """Detecta #HUMANO#, conta tentativas e escala para atendente."""
    last_message = state["messages"][-1]

    if not isinstance(last_message, AIMessage):
        return {
            "tentativas_categoria_e": state.get("tentativas_categoria_e", 0),
            "requer_humano": False,
        }

    content = last_message.content
    has_humano_tag = HUMANO_TAG in content
    tentativas = state.get("tentativas_categoria_e", 0)
    em_atendimento = state.get("em_atendimento_humano", False)

    if has_humano_tag:
        tentativas += 1
        clean_content = content.replace(HUMANO_TAG, "").strip()
        clean_msg = AIMessage(content=clean_content)

        just_reached_threshold = (tentativas >= HANDOFF_THRESHOLD and not em_atendimento)
        if just_reached_threshold:
            em_atendimento = True
            clean_msg = AIMessage(content=HANDOFF_MESSAGE)
            customer_phone = state.get("chat_phone", "desconhecido")
            # Notify store owner via WhatsApp
            owner_phone = settings.STORE_OWNER_PHONE
            if owner_phone:
                notification = (
                    f"⚠️ Cliente {customer_phone} solicitou atendimento humano."
                )
                send_message(owner_phone, notification)
                logger.info("Notificação de handoff enviada para %s", owner_phone)
            # Notify Chatwoot (label + nota interna + status pending)
            notify_handoff(customer_phone)

        return {
            "messages": [clean_msg],
            "tentativas_categoria_e": tentativas,
            "requer_humano": True,
            "em_atendimento_humano": em_atendimento,
        }

    return {
        "tentativas_categoria_e": tentativas,
        "requer_humano": False,
    }
