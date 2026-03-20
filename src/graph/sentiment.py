"""Frustration detection and message utilities."""

from langchain_core.messages import HumanMessage

from src.state import AgentState

FRUSTRATION_SIGNALS: list[str] = [
    "absurdo", "péssimo", "horrível", "nunca mais", "bagunça",
    "não funciona", "enganação", "fraude", "ridículo",
    "vergonha", "lixo", "roubo", "palhaçada",
]


def has_frustration_signal(text: str) -> bool:
    """Detecta sinais de frustração extrema no texto do cliente."""
    lower = text.lower()
    return any(signal in lower for signal in FRUSTRATION_SIGNALS)


def _get_last_human_message(state: AgentState) -> str | None:
    """Retorna o conteúdo da última mensagem humana no estado."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return None
