"""Classify node — LLM classifies intent, may invoke buscar tool."""

import logging

from langchain_core.messages import SystemMessage

from src.graph.llm import _get_llm_classify, _session_messages
from src.graph.prompt import SYSTEM_PROMPT
from src.graph.sentiment import _get_last_human_message, has_frustration_signal
from src.state import AgentState

logger = logging.getLogger(__name__)


def _detect_language_hint(text: str) -> str | None:
    """Retorna hint de idioma se a mensagem não parece ser em português."""
    lower = text.lower()
    en_signals = ["hello", "hi ", "please", "thank", "need", "want", "have", "how much", "do you"]
    es_signals = ["hola", "necesito", "quiero", "tienen", "cuánto", "gracias", "por favor", "buenas"]
    if any(w in lower for w in en_signals):
        return "⚠️ O cliente está escrevendo em INGLÊS. Responda TODA a mensagem em inglês."
    if any(w in lower for w in es_signals):
        return "⚠️ El cliente está escribiendo en ESPAÑOL. Responda TODA la mensagem en español."
    return None


def classify_node(state: AgentState) -> dict:
    """Nó de classificação: envia mensagens ao LLM que decide se usa tool ou responde direto."""
    system_msg = SystemMessage(content=SYSTEM_PROMPT)
    messages = [system_msg] + _session_messages(state)

    last_human = _get_last_human_message(state)

    # Sentiment detection: inject hint for frustrated customers
    if last_human and has_frustration_signal(last_human):
        messages.append(SystemMessage(content="⚠️ Frustração detectada na mensagem do cliente. Trate como Categoria E."))

    # Language detection: reinforce language rule
    if last_human:
        lang_hint = _detect_language_hint(last_human)
        if lang_hint:
            messages.append(SystemMessage(content=lang_hint))

    response = _get_llm_classify().invoke(messages)
    return {"messages": [response], "awaiting_reply": False}
