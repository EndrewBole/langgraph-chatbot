"""Lazy-loaded LLM singletons and session utilities."""

import threading

from langchain_openai import ChatOpenAI

from src.config import settings
from src.state import AgentState
from src.tools import buscar

_llm_classify = None
_llm_respond = None
_llm_lock = threading.Lock()


def _get_llm_classify():
    """LLM com tools bound para o nó de classificação."""
    global _llm_classify
    if _llm_classify is None:
        with _llm_lock:
            if _llm_classify is None:
                _llm_classify = ChatOpenAI(model=settings.MODEL_NAME).bind_tools([buscar])
    return _llm_classify


def _get_llm_respond():
    """LLM sem tools para o nó de resposta final."""
    global _llm_respond
    if _llm_respond is None:
        with _llm_lock:
            if _llm_respond is None:
                _llm_respond = ChatOpenAI(model=settings.MODEL_NAME)
    return _llm_respond


def _session_messages(state: AgentState) -> list:
    """Retorna apenas as mensagens da sessão atual (a partir de session_start)."""
    start = state.get("session_start", 0)
    return list(state["messages"])[start:]
