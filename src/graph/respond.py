"""Respond node — LLM formulates final response after tool execution."""

import logging

from langchain_core.messages import SystemMessage

from src.graph.classify import _detect_language_hint
from src.graph.llm import _get_llm_respond, _session_messages
from src.graph.prompt import SYSTEM_PROMPT
from src.graph.sentiment import _get_last_human_message
from src.state import AgentState

logger = logging.getLogger(__name__)


def respond_node(state: AgentState) -> dict:
    """Nó de resposta: após tool executar, o LLM formula a resposta final ao cliente."""
    system_msg = SystemMessage(content=SYSTEM_PROMPT)
    messages = [system_msg] + _session_messages(state)

    # Language detection: reinforce language rule for respond node
    last_human = _get_last_human_message(state)
    if last_human:
        lang_hint = _detect_language_hint(last_human)
        if lang_hint:
            messages.append(SystemMessage(content=lang_hint))

    response = _get_llm_respond().invoke(messages)
    return {"messages": [response]}
