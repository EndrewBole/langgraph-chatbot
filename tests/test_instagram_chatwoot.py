"""Tests for Instagram DM support via Chatwoot bridge."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from langchain_core.messages import HumanMessage, AIMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chatwoot_message_created_payload(
    content: str = "Oi, preciso de filtro",
    channel: str = "Channel::Instagram",
    message_type: str = "incoming",
    conversation_id: int = 42,
    contact_id: int = 100,
    sender_name: str = "João",
) -> dict:
    """Helper para gerar payload Chatwoot message_created."""
    return {
        "event": "message_created",
        "message_type": message_type,
        "content": content,
        "conversation": {
            "id": conversation_id,
            "channel": channel,
            "status": "open",
            "meta": {
                "sender": {
                    "id": contact_id,
                    "name": sender_name,
                    "phone_number": "",
                },
            },
            "contact_inbox": {
                "source_id": f"ig_{contact_id}",
            },
        },
        "sender": {
            "id": contact_id,
            "name": sender_name,
            "type": "contact",
        },
    }


def _make_state(**overrides):
    defaults = {
        "messages": [HumanMessage(content="oi")],
        "session_id": "ig_100",
        "chat_phone": "ig_100",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
        "awaiting_reply": False,
        "follow_up_sent": False,
        "channel": "instagram",
        "chatwoot_conversation_id": 42,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# send_chatwoot_message tests
# ---------------------------------------------------------------------------


class TestSendChatwootMessage:
    @patch("src.integrations.chatwoot.httpx.post")
    @patch("src.integrations.chatwoot.settings")
    def test_send_chatwoot_message_success(self, mock_settings, mock_post):
        """send_chatwoot_message POSTs to Chatwoot conversations API."""
        from src.integrations.chatwoot import send_chatwoot_message

        mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
        mock_settings.CHATWOOT_API_KEY = "test-token"
        mock_settings.CHATWOOT_ACCOUNT_ID = "1"

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = send_chatwoot_message(42, "Olá!")
        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "/conversations/42/messages" in call_kwargs.args[0]
        assert call_kwargs.kwargs["json"]["content"] == "Olá!"
        assert call_kwargs.kwargs["json"]["message_type"] == "outgoing"

    @patch("src.integrations.chatwoot.httpx.post")
    def test_send_chatwoot_message_failure(self, mock_post):
        """Returns False on network error."""
        from src.integrations.chatwoot import send_chatwoot_message

        mock_post.side_effect = httpx.HTTPError("connection failed")
        result = send_chatwoot_message(42, "Olá!")
        assert result is False

    @patch("src.integrations.chatwoot.httpx.post")
    def test_send_chatwoot_message_no_config(self, mock_post):
        """Returns False when Chatwoot not configured."""
        from src.integrations.chatwoot import send_chatwoot_message

        with patch("src.integrations.chatwoot.settings") as mock_settings:
            mock_settings.CHATWOOT_API_URL = ""
            mock_settings.CHATWOOT_API_KEY = ""
            result = send_chatwoot_message(42, "Olá!")
        assert result is False
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# AgentState channel fields
# ---------------------------------------------------------------------------


class TestAgentStateChannelFields:
    def test_state_has_channel_field(self):
        from src.state import AgentState
        annotations = AgentState.__annotations__
        assert "channel" in annotations

    def test_state_has_chatwoot_conversation_id_field(self):
        from src.state import AgentState
        annotations = AgentState.__annotations__
        assert "chatwoot_conversation_id" in annotations


# ---------------------------------------------------------------------------
# send_response_node channel-aware dispatch
# ---------------------------------------------------------------------------


class TestSendResponseNodeInstagram:
    @patch("src.graph.send.send_chatwoot_message", return_value=True)
    @patch("src.graph.send.send_message", return_value=True)
    def test_instagram_uses_chatwoot(self, mock_evolution, mock_chatwoot):
        """When channel=instagram, sends via Chatwoot API."""
        from src.graph.send import send_response_node

        state = _make_state(
            messages=[HumanMessage(content="oi"), AIMessage(content="Olá!")],
        )
        send_response_node(state)
        mock_chatwoot.assert_called_once_with(42, "Olá!")
        mock_evolution.assert_not_called()

    @patch("src.graph.send.send_chatwoot_message", return_value=True)
    @patch("src.graph.send.send_message", return_value=True)
    def test_whatsapp_uses_evolution(self, mock_evolution, mock_chatwoot):
        """Default channel (whatsapp) still uses Evolution API."""
        from src.graph.send import send_response_node

        state = _make_state(
            messages=[HumanMessage(content="oi"), AIMessage(content="Olá!")],
            channel="whatsapp",
            chat_phone="5511999999999",
        )
        send_response_node(state)
        mock_evolution.assert_called_once()
        mock_chatwoot.assert_not_called()

    @patch("src.graph.send.send_chatwoot_message", return_value=True)
    @patch("src.graph.send.send_link_button", return_value=True)
    @patch("src.graph.send.send_message", return_value=True)
    def test_instagram_product_with_link_sends_text(self, mock_evolution, mock_btn, mock_chatwoot):
        """Instagram products send link as plain text (no button card)."""
        from src.graph.send import send_response_node

        content = "*1. Filtro*\n\n- Preço: R$ 89,90\n[BTN:https://ml.com/filtro]\n\nPosso ajudar?"
        state = _make_state(
            messages=[HumanMessage(content="filtro"), AIMessage(content=content)],
        )
        send_response_node(state)
        assert mock_chatwoot.call_count >= 2  # product + closing text
        mock_evolution.assert_not_called()
        mock_btn.assert_not_called()


# ---------------------------------------------------------------------------
# Chatwoot webhook — message_created for Instagram
# ---------------------------------------------------------------------------


class TestChatwootInstagramWebhook:
    @pytest.mark.asyncio
    @patch("src.api.routes.chatwoot.graph")
    async def test_instagram_message_triggers_graph(self, mock_graph):
        """message_created from Instagram inbox invokes graph."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_graph.invoke = MagicMock()
        mock_graph.get_state = MagicMock(side_effect=Exception("no state"))

        payload = _chatwoot_message_created_payload()

        with patch("src.api.routes.chatwoot.graph", mock_graph):
            with TestClient(app) as client:
                response = client.post("/webhook/chatwoot", json=payload)

        assert response.status_code == 200
        mock_graph.invoke.assert_called_once()
        call_args = mock_graph.invoke.call_args
        state_input = call_args.args[0]
        assert state_input["channel"] == "instagram"
        assert state_input["chatwoot_conversation_id"] == 42

    @pytest.mark.asyncio
    @patch("src.api.routes.chatwoot.graph")
    async def test_whatsapp_message_created_ignored(self, mock_graph):
        """message_created from WhatsApp channel is ignored (handled by Evolution)."""
        from fastapi.testclient import TestClient
        from src.main import app

        payload = _chatwoot_message_created_payload(channel="Channel::Whatsapp")

        with patch("src.api.routes.chatwoot.graph", mock_graph):
            with TestClient(app) as client:
                response = client.post("/webhook/chatwoot", json=payload)

        assert response.status_code == 200
        mock_graph.invoke.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.api.routes.chatwoot.graph")
    async def test_outgoing_message_ignored(self, mock_graph):
        """Outgoing messages (bot/agent replies) are not processed."""
        from fastapi.testclient import TestClient
        from src.main import app

        payload = _chatwoot_message_created_payload(message_type="outgoing")

        with patch("src.api.routes.chatwoot.graph", mock_graph):
            with TestClient(app) as client:
                response = client.post("/webhook/chatwoot", json=payload)

        assert response.status_code == 200
        mock_graph.invoke.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.api.routes.chatwoot.graph")
    async def test_instagram_thread_id_format(self, mock_graph):
        """Thread ID uses ig_{contact_id} format."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_graph.invoke = MagicMock()
        mock_graph.get_state = MagicMock(side_effect=Exception("no state"))

        payload = _chatwoot_message_created_payload(contact_id=777)

        with patch("src.api.routes.chatwoot.graph", mock_graph):
            with TestClient(app) as client:
                client.post("/webhook/chatwoot", json=payload)

        config = mock_graph.invoke.call_args.args[1]
        assert config["configurable"]["thread_id"] == "ig_777"

    @pytest.mark.asyncio
    @patch("src.api.routes.chatwoot.graph")
    async def test_empty_content_ignored(self, mock_graph):
        """Empty message content is ignored."""
        from fastapi.testclient import TestClient
        from src.main import app

        payload = _chatwoot_message_created_payload(content="")

        with patch("src.api.routes.chatwoot.graph", mock_graph):
            with TestClient(app) as client:
                response = client.post("/webhook/chatwoot", json=payload)

        assert response.status_code == 200
        mock_graph.invoke.assert_not_called()


# Need httpx for the error test
import httpx
