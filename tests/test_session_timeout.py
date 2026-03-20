"""Testes do reset de sessão por inatividade (sem apagar histórico)."""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage


def _parsed(phone: str = "5511999") -> dict:
    return {"session_id": phone, "chat_phone": phone}


def _snapshot(last_activity: float, messages: list = None, session_start: int = 0) -> MagicMock:
    snap = MagicMock()
    snap.values = {
        "last_activity": last_activity,
        "messages": messages or [],
        "session_start": session_start,
    }
    return snap


# --- process_message: controle de sessão ---

@pytest.mark.asyncio
async def test_expired_session_preserves_thread_id():
    """Sessão expirada NÃO muda o thread_id — histórico preservado."""
    from src.api.routes.whatsapp import process_message

    expired = time.time() - (5 * 3600)
    msgs = [HumanMessage(content="oi"), AIMessage(content="olá")]

    with patch("src.api.routes.whatsapp.graph") as mock_graph, \
         patch("src.api.routes.whatsapp.settings") as mock_s, \
         patch("src.api.routes.whatsapp.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:

        mock_s.SESSION_TIMEOUT_HOURS = 4
        mock_graph.get_state.return_value = _snapshot(expired, msgs)
        mock_thread.return_value = {"messages": []}

        await process_message(_parsed(), "nova mensagem")

        config = mock_thread.call_args[0][2]
        assert config["configurable"]["thread_id"] == "5511999"


@pytest.mark.asyncio
async def test_expired_session_updates_session_start():
    """Sessão expirada atualiza session_start para o número atual de mensagens."""
    from src.api.routes.whatsapp import process_message

    expired = time.time() - (5 * 3600)
    msgs = [HumanMessage(content="oi"), AIMessage(content="olá")]  # 2 msgs antigas

    with patch("src.api.routes.whatsapp.graph") as mock_graph, \
         patch("src.api.routes.whatsapp.settings") as mock_s, \
         patch("src.api.routes.whatsapp.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:

        mock_s.SESSION_TIMEOUT_HOURS = 4
        mock_graph.get_state.return_value = _snapshot(expired, msgs)
        mock_thread.return_value = {"messages": []}

        await process_message(_parsed(), "nova mensagem")

        state = mock_thread.call_args[0][1]
        assert state["session_start"] == 2  # aponta para após as 2 msgs antigas


@pytest.mark.asyncio
async def test_active_session_keeps_session_start():
    """Sessão ativa mantém session_start existente."""
    from src.api.routes.whatsapp import process_message

    recent = time.time() - (1 * 3600)

    with patch("src.api.routes.whatsapp.graph") as mock_graph, \
         patch("src.api.routes.whatsapp.settings") as mock_s, \
         patch("src.api.routes.whatsapp.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:

        mock_s.SESSION_TIMEOUT_HOURS = 4
        mock_graph.get_state.return_value = _snapshot(recent, [], session_start=3)
        mock_thread.return_value = {"messages": []}

        await process_message(_parsed(), "oi")

        state = mock_thread.call_args[0][1]
        assert state["session_start"] == 3


@pytest.mark.asyncio
async def test_last_activity_updated_on_every_message():
    """last_activity é sempre atualizado ao processar mensagem."""
    from src.api.routes.whatsapp import process_message

    snap = MagicMock()
    snap.values = {}

    with patch("src.api.routes.whatsapp.graph") as mock_graph, \
         patch("src.api.routes.whatsapp.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:

        mock_graph.get_state.return_value = snap
        mock_thread.return_value = {"messages": []}

        before = time.time()
        await process_message(_parsed(), "oi")
        after = time.time()

        state = mock_thread.call_args[0][1]
        assert "last_activity" in state
        assert before <= state["last_activity"] <= after


# --- nodes: slicing de mensagens por session_start ---

def _make_state(messages, session_start=0, **extra):
    return {
        "messages": messages,
        "session_id": "5511999",
        "chat_phone": "5511999",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
        "session_start": session_start,
        **extra,
    }


def test_classify_node_only_sees_current_session_messages():
    """classify_node envia ao LLM apenas mensagens a partir de session_start."""
    from unittest.mock import patch, MagicMock
    from langchain_core.messages import AIMessage

    old_msgs = [HumanMessage(content="SESSAO_VELHA_XYZ"), AIMessage(content="RESPOSTA_VELHA_XYZ")]
    new_msg = HumanMessage(content="nova sessao começo")
    all_msgs = old_msgs + [new_msg]

    with patch("src.graph.classify._get_llm_classify") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="ok")
        mock_get_llm.return_value = mock_llm

        from src.graph.nodes import classify_node
        classify_node(_make_state(all_msgs, session_start=2))

        call_msgs = mock_llm.invoke.call_args[0][0]
        contents = [m.content for m in call_msgs]
        assert "SESSAO_VELHA_XYZ" not in str(contents)
        assert "nova sessao começo" in str(contents)


def test_respond_node_only_sees_current_session_messages():
    """respond_node envia ao LLM apenas mensagens a partir de session_start."""
    from unittest.mock import patch, MagicMock
    from langchain_core.messages import AIMessage, ToolMessage

    old_msgs = [HumanMessage(content="SESSAO_VELHA_XYZ"), AIMessage(content="RESPOSTA_VELHA_XYZ")]
    new_msgs = [HumanMessage(content="filtro cb300"), ToolMessage(content="resultado", tool_call_id="1")]
    all_msgs = old_msgs + new_msgs

    with patch("src.graph.respond._get_llm_respond") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="ok")
        mock_get_llm.return_value = mock_llm

        from src.graph.nodes import respond_node
        respond_node(_make_state(all_msgs, session_start=2))

        call_msgs = mock_llm.invoke.call_args[0][0]
        contents = [m.content for m in call_msgs]
        assert "SESSAO_VELHA_XYZ" not in str(contents)
        assert "filtro cb300" in str(contents)
