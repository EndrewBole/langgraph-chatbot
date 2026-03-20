"""Tests for Chatwoot webhook — conversation_resolved resets human handoff."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    app.state.http_client = AsyncMock()
    with TestClient(app) as c:
        yield c


def _chatwoot_payload(
    event: str = "conversation_status_changed",
    phone: str = "+5511999999999",
    conversation_id: int = 123,
    status: str = "resolved",
) -> dict:
    """Helper para gerar payload Chatwoot webhook."""
    return {
        "event": event,
        "account": {"id": 1, "name": "Temporalis"},
        "conversation": {
            "id": conversation_id,
            "inbox_id": 1,
            "status": status,
            "meta": {
                "sender": {
                    "phone_number": phone,
                }
            },
        },
    }


# ---------------------------------------------------------------------------
# Test: conversation_resolved resets human handoff state
# ---------------------------------------------------------------------------

@patch("src.api.routes.chatwoot.send_whatsapp_message", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_conversation_resolved_resets_state(mock_graph, mock_send, client):
    """conversation_resolved deve resetar em_atendimento_humano via graph.update_state."""
    payload = _chatwoot_payload(event="conversation_status_changed", phone="+5511999999999")

    response = client.post("/webhook/chatwoot", json=payload)

    assert response.status_code == 200
    assert response.text == "OK"

    mock_graph.update_state.assert_called_once_with(
        {"configurable": {"thread_id": "5511999999999"}},
        {"em_atendimento_humano": False, "requer_humano": False, "tentativas_categoria_e": 0},
    )


# ---------------------------------------------------------------------------
# Test: unknown events return OK without action
# ---------------------------------------------------------------------------

@patch("src.api.routes.chatwoot.send_whatsapp_message", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_unknown_event_returns_ok_without_action(mock_graph, mock_send, client):
    """Eventos desconhecidos devem retornar OK sem chamar update_state."""
    payload = _chatwoot_payload(event="message_created")

    response = client.post("/webhook/chatwoot", json=payload)

    assert response.status_code == 200
    assert response.text == "OK"
    mock_graph.update_state.assert_not_called()
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Test: phone number with + prefix is stripped correctly
# ---------------------------------------------------------------------------

@patch("src.api.routes.chatwoot.send_whatsapp_message", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_phone_plus_prefix_stripped(mock_graph, mock_send, client):
    """Numero com prefixo + deve ser limpo para formato sem +."""
    payload = _chatwoot_payload(phone="+5511988887777")

    response = client.post("/webhook/chatwoot", json=payload)

    assert response.status_code == 200
    mock_graph.update_state.assert_called_once()
    call_args = mock_graph.update_state.call_args
    assert call_args[0][0] == {"configurable": {"thread_id": "5511988887777"}}


# ---------------------------------------------------------------------------
# Test: bot reactivation message is sent
# ---------------------------------------------------------------------------

@patch("src.api.routes.chatwoot.send_whatsapp_message", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_bot_reactivation_message_sent(mock_graph, mock_send, client):
    """Apos resolver conversa, deve enviar mensagem de reativacao ao cliente."""
    payload = _chatwoot_payload(phone="+5511999999999")

    response = client.post("/webhook/chatwoot", json=payload)

    assert response.status_code == 200
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args[0][1] == "5511999999999"  # to_phone
    assert "Atendimento encerrado" in call_args[0][2]  # body


# ---------------------------------------------------------------------------
# Test: phone without + prefix works too
# ---------------------------------------------------------------------------

@patch("src.api.routes.chatwoot.send_whatsapp_message", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_phone_without_plus_works(mock_graph, mock_send, client):
    """Numero sem prefixo + tambem deve funcionar."""
    payload = _chatwoot_payload(phone="5511999999999")

    response = client.post("/webhook/chatwoot", json=payload)

    assert response.status_code == 200
    call_args = mock_graph.update_state.call_args
    assert call_args[0][0] == {"configurable": {"thread_id": "5511999999999"}}


# ===========================================================================
# Tests: /webhook/chatwoot/outgoing proxy
# ===========================================================================


def _outgoing_payload(
    content: str = "Olá cliente!",
    message_type: str = "outgoing",
    phone: str = "+5511930851865",
) -> dict:
    """Helper para gerar payload Chatwoot outgoing message."""
    return {
        "content": content,
        "message_type": message_type,
        "conversation": {
            "meta": {
                "sender": {
                    "phone_number": phone,
                }
            },
            "contact_inbox": {
                "source_id": "5511930851865@s.whatsapp.net",
            },
        },
    }


@patch("src.api.routes.chatwoot._forward_to_evolution", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_outgoing_bot_command_not_forwarded(mock_graph, mock_forward, client):
    """#BOT# deve resetar handoff e NAO encaminhar ao Evolution API."""
    payload = _outgoing_payload(content="#BOT#")

    response = client.post("/webhook/chatwoot/outgoing", json=payload)

    assert response.status_code == 200
    mock_graph.update_state.assert_called_once()
    call_args = mock_graph.update_state.call_args
    assert call_args[0][1]["em_atendimento_humano"] is False
    mock_forward.assert_not_called()


@patch("src.api.routes.chatwoot._forward_to_evolution", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_outgoing_bot_command_with_whitespace(mock_graph, mock_forward, client):
    """#BOT# com espacos/newlines extras ainda deve ser detectado."""
    payload = _outgoing_payload(content="  #BOT#  \n\n")

    response = client.post("/webhook/chatwoot/outgoing", json=payload)

    assert response.status_code == 200
    mock_graph.update_state.assert_called_once()
    mock_forward.assert_not_called()


@patch("src.api.routes.chatwoot._forward_to_evolution", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_outgoing_normal_message_forwarded(mock_graph, mock_forward, client):
    """Mensagens normais devem ser encaminhadas ao Evolution API."""
    payload = _outgoing_payload(content="Olá, como posso ajudar?\n\n\n")

    response = client.post("/webhook/chatwoot/outgoing", json=payload)

    assert response.status_code == 200
    mock_graph.update_state.assert_not_called()
    mock_forward.assert_called_once()
    # Verifica que newlines extras foram removidas
    forwarded = mock_forward.call_args[0][0]
    assert forwarded["content"] == "Olá, como posso ajudar?"


@patch("src.api.routes.chatwoot._forward_to_evolution", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_outgoing_strips_trailing_newlines(mock_graph, mock_forward, client):
    """Quebras de linha extras no final devem ser removidas."""
    payload = _outgoing_payload(content="Mensagem com newlines\n\n\n\n")

    response = client.post("/webhook/chatwoot/outgoing", json=payload)

    assert response.status_code == 200
    forwarded = mock_forward.call_args[0][0]
    assert forwarded["content"] == "Mensagem com newlines"


@patch("src.api.routes.chatwoot._forward_to_evolution", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_outgoing_non_outgoing_type_forwarded(mock_graph, mock_forward, client):
    """Mensagens que nao sao outgoing (ex: incoming) sao encaminhadas sem filtro."""
    payload = _outgoing_payload(content="#BOT#", message_type="incoming")

    response = client.post("/webhook/chatwoot/outgoing", json=payload)

    assert response.status_code == 200
    mock_graph.update_state.assert_not_called()
    mock_forward.assert_called_once()


@patch("src.api.routes.chatwoot._forward_to_evolution", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_outgoing_extracts_phone_from_source_id(mock_graph, mock_forward, client):
    """Deve extrair telefone do source_id quando phone_number ausente."""
    payload = _outgoing_payload(content="#BOT#", phone="")

    response = client.post("/webhook/chatwoot/outgoing", json=payload)

    assert response.status_code == 200
    mock_graph.update_state.assert_called_once()
    call_args = mock_graph.update_state.call_args
    assert call_args[0][0] == {"configurable": {"thread_id": "5511930851865"}}


# ===========================================================================
# Tests: Instagram resolved conversation
# ===========================================================================


@patch("src.api.routes.chatwoot.send_chatwoot_message")
@patch("src.api.routes.chatwoot.graph")
def test_instagram_resolved_resets_state(mock_graph, mock_send_cw, client):
    """Instagram resolved conversation resets state using ig_{contact_id} thread."""
    payload = {
        "event": "conversation_status_changed",
        "conversation": {
            "id": 456,
            "status": "resolved",
            "channel": "Channel::Instagram",
            "meta": {"sender": {"id": 99}},
        },
    }
    response = client.post("/webhook/chatwoot", json=payload)
    assert response.status_code == 200
    mock_graph.update_state.assert_called_once_with(
        {"configurable": {"thread_id": "ig_99"}},
        {"em_atendimento_humano": False, "requer_humano": False, "tentativas_categoria_e": 0},
    )
    mock_send_cw.assert_called_once_with(456, "Atendimento encerrado. Estou de volta para ajudar!")


# ===========================================================================
# Tests: Resolved without phone returns OK
# ===========================================================================


@patch("src.api.routes.chatwoot.send_whatsapp_message", new_callable=AsyncMock)
@patch("src.api.routes.chatwoot.graph")
def test_resolved_no_phone_returns_ok(mock_graph, mock_send, client):
    """WhatsApp resolved with empty phone returns OK without calling update_state."""
    payload = {
        "event": "conversation_status_changed",
        "conversation": {
            "status": "resolved",
            "meta": {"sender": {"phone_number": ""}},
        },
    }
    response = client.post("/webhook/chatwoot", json=payload)
    assert response.status_code == 200
    mock_graph.update_state.assert_not_called()


# ===========================================================================
# Tests: Non-resolved status returns OK
# ===========================================================================


@patch("src.api.routes.chatwoot.graph")
def test_non_resolved_status_returns_ok(mock_graph, client):
    """Status != resolved returns OK without action."""
    payload = {
        "event": "conversation_status_changed",
        "conversation": {"status": "pending", "meta": {"sender": {"phone_number": "+5511999"}}},
    }
    response = client.post("/webhook/chatwoot", json=payload)
    assert response.status_code == 200
    mock_graph.update_state.assert_not_called()


# ===========================================================================
# Tests: _forward_to_evolution error handling
# ===========================================================================


@pytest.mark.asyncio
async def test_forward_to_evolution_error():
    """_forward_to_evolution handles connection errors gracefully."""
    from src.api.routes.chatwoot import _forward_to_evolution

    with patch("src.api.routes.chatwoot.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = httpx.ConnectError("fail")
        MockClient.return_value = mock_client
        # Should not raise
        await _forward_to_evolution({"content": "test"})


# ===========================================================================
# Tests: _extract_phone_from_payload returns None
# ===========================================================================


def test_extract_phone_no_data():
    """Returns None when no phone_number and no source_id."""
    from src.api.routes.chatwoot import _extract_phone_from_payload

    result = _extract_phone_from_payload(
        {"conversation": {"meta": {"sender": {}}, "contact_inbox": {}}}
    )
    assert result is None
