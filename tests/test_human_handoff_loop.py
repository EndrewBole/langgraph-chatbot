"""Tests for Human Handoff Loop — Part A, B, C.

Part A: Agent notification when em_atendimento_humano first becomes True.
Part B: Forward fromMe messages to customer when in human service.
Part C: Release customer back to bot with #BOT# command.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides):
    defaults = {
        "messages": [HumanMessage(content="quero falar com humano")],
        "session_id": "5511999999999",
        "chat_phone": "5511999999999",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
    }
    defaults.update(overrides)
    return defaults


def _evolution_payload(
    phone: str = "5511999999999",
    from_me: bool = False,
    is_group: bool = False,
    text: str | None = None,
    message_id: str = "MSG1",
) -> dict:
    """Helper para gerar payload Evolution API messages.upsert."""
    suffix = "@g.us" if is_group else "@s.whatsapp.net"
    remote_jid = f"{phone}{suffix}"
    message = {}
    if text:
        message["conversation"] = text
    return {
        "event": "messages.upsert",
        "instance": "temporalis",
        "data": {
            "key": {
                "remoteJid": remote_jid,
                "fromMe": from_me,
                "id": message_id,
            },
            "message": message,
            "messageType": "conversation" if text else "unknown",
        },
    }


# ---------------------------------------------------------------------------
# Part A — Agent notification
# ---------------------------------------------------------------------------

class TestAgentNotification:
    """human_handoff_node notifies store owner when threshold is reached."""

    @patch("src.graph.handoff.send_message")
    def test_notification_sent_when_threshold_reached(self, mock_send):
        """Notification goes to STORE_OWNER_PHONE when tentativas hits 3."""
        from src.graph.nodes import human_handoff_node

        with patch("src.graph.handoff.settings") as mock_settings:
            mock_settings.STORE_OWNER_PHONE = "5511888888888"
            mock_settings.HANDOFF_THRESHOLD = 3  # not used directly but consistent

            state = _make_state(
                messages=[
                    HumanMessage(content="preciso de humano"),
                    AIMessage(content="Vou transferir. #HUMANO#"),
                ],
                tentativas_categoria_e=2,  # this call will push to 3 -> threshold
                chat_phone="5511999999999",
            )

            human_handoff_node(state)

            # Owner must receive a notification
            owner_calls = [
                call for call in mock_send.call_args_list
                if call.args[0] == "5511888888888"
            ]
            assert len(owner_calls) == 1
            assert "5511999999999" in owner_calls[0].args[1]

    @patch("src.graph.handoff.send_message")
    def test_no_notification_when_below_threshold(self, mock_send):
        """No owner notification when tentativas < 3."""
        from src.graph.nodes import human_handoff_node

        with patch("src.graph.handoff.settings") as mock_settings:
            mock_settings.STORE_OWNER_PHONE = "5511888888888"

            state = _make_state(
                messages=[
                    HumanMessage(content="quero humano"),
                    AIMessage(content="Entendo. #HUMANO#"),
                ],
                tentativas_categoria_e=1,  # will reach 2, not 3
            )

            human_handoff_node(state)

            owner_calls = [
                call for call in mock_send.call_args_list
                if call.args[0] == "5511888888888"
            ]
            assert len(owner_calls) == 0

    @patch("src.graph.handoff.send_message")
    def test_no_notification_when_store_owner_phone_empty(self, mock_send):
        """No notification when STORE_OWNER_PHONE is not configured."""
        from src.graph.nodes import human_handoff_node

        with patch("src.graph.handoff.settings") as mock_settings:
            mock_settings.STORE_OWNER_PHONE = ""

            state = _make_state(
                messages=[
                    HumanMessage(content="quero humano"),
                    AIMessage(content="Entendo. #HUMANO#"),
                ],
                tentativas_categoria_e=2,
            )

            human_handoff_node(state)

            # send_message may be called for customer, but not for empty owner
            owner_calls = [
                call for call in mock_send.call_args_list
                if call.args[0] == ""
            ]
            assert len(owner_calls) == 0

    @patch("src.graph.handoff.send_message")
    def test_no_duplicate_notification_already_in_handoff(self, mock_send):
        """No repeated notification when already em_atendimento_humano=True."""
        from src.graph.nodes import human_handoff_node

        with patch("src.graph.handoff.settings") as mock_settings:
            mock_settings.STORE_OWNER_PHONE = "5511888888888"

            state = _make_state(
                messages=[
                    HumanMessage(content="quero humano"),
                    AIMessage(content="Aguarde. #HUMANO#"),
                ],
                tentativas_categoria_e=5,       # already past threshold
                em_atendimento_humano=True,     # already in handoff
            )

            human_handoff_node(state)

            owner_calls = [
                call for call in mock_send.call_args_list
                if call.args[0] == "5511888888888"
            ]
            assert len(owner_calls) == 0


# ---------------------------------------------------------------------------
# Part B — Forward fromMe messages to customer
# ---------------------------------------------------------------------------

class TestHumanAgentReplyForwarding:
    """When fromMe=True and customer is in human service, forward the message."""

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp.send_whatsapp_message", new_callable=AsyncMock, return_value=True)
    @patch("src.api.routes.whatsapp.graph")
    async def test_forwards_message_when_in_human_service(self, mock_graph, mock_send, mock_validate):
        """fromMe=True message is forwarded when customer em_atendimento_humano=True."""
        from fastapi.testclient import TestClient
        from src.main import app

        # Graph state shows customer is in human service
        mock_snapshot = MagicMock()
        mock_snapshot.values = {"em_atendimento_humano": True}
        mock_graph.get_state.return_value = mock_snapshot

        with patch("src.api.routes.whatsapp.graph", mock_graph), \
             patch("src.api.routes.whatsapp.send_whatsapp_message", mock_send):

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/webhook/whatsapp",
                    json=_evolution_payload(
                        from_me=True,
                        text="Ola, sou o atendente!",
                        message_id="MSG_FROM_ME_1",
                    ),
                )

            assert response.status_code == 200
            # send_whatsapp_message must have been called to forward to customer
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args.args[1] == "5511999999999"
            assert "Ola, sou o atendente!" in call_args.args[2]

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp.send_whatsapp_message", new_callable=AsyncMock, return_value=True)
    @patch("src.api.routes.whatsapp.graph")
    async def test_does_not_forward_when_not_in_human_service(self, mock_graph, mock_send, mock_validate):
        """fromMe=True message is ignored when customer is NOT in human service."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_snapshot = MagicMock()
        mock_snapshot.values = {"em_atendimento_humano": False}
        mock_graph.get_state.return_value = mock_snapshot

        with patch("src.api.routes.whatsapp.graph", mock_graph), \
             patch("src.api.routes.whatsapp.send_whatsapp_message", mock_send):

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/webhook/whatsapp",
                    json=_evolution_payload(
                        from_me=True,
                        text="mensagem qualquer",
                        message_id="MSG_FROM_ME_2",
                    ),
                )

            assert response.status_code == 200
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp.send_whatsapp_message", new_callable=AsyncMock, return_value=True)
    @patch("src.api.routes.whatsapp.graph")
    async def test_does_not_forward_group_messages(self, mock_graph, mock_send, mock_validate):
        """Group messages (fromMe=True, isGroup=True) are always ignored."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_snapshot = MagicMock()
        mock_snapshot.values = {"em_atendimento_humano": True}
        mock_graph.get_state.return_value = mock_snapshot

        with patch("src.api.routes.whatsapp.graph", mock_graph), \
             patch("src.api.routes.whatsapp.send_whatsapp_message", mock_send):

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/webhook/whatsapp",
                    json=_evolution_payload(
                        from_me=True,
                        is_group=True,
                        text="grupo",
                        message_id="MSG_FROM_ME_3",
                    ),
                )

            assert response.status_code == 200
            mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Part C — Release back to bot with #BOT# command
# ---------------------------------------------------------------------------

class TestReleaseToBotCommand:
    """When fromMe=True message contains HUMAN_RELEASE_COMMAND, reset state."""

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.send_whatsapp_message", new_callable=AsyncMock, return_value=True)
    @patch("src.api.routes.whatsapp.graph")
    async def test_release_command_resets_human_service_state(self, mock_graph, mock_send):
        """#BOT# command resets em_atendimento_humano and requer_humano to False."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_snapshot = MagicMock()
        mock_snapshot.values = {"em_atendimento_humano": True}
        mock_graph.get_state.return_value = mock_snapshot
        mock_graph.update_state = MagicMock()

        with patch("src.api.routes.whatsapp.graph", mock_graph), \
             patch("src.api.routes.whatsapp.send_whatsapp_message", mock_send), \
             patch("src.api.routes.whatsapp.settings") as mock_settings:

            mock_settings.EVOLUTION_API_KEY = ""
            mock_settings.HUMAN_RELEASE_COMMAND = "#BOT#"
            mock_settings.STORE_OWNER_PHONE = "5511888888888"
            mock_settings.MESSAGE_BUFFER_WAIT_SECONDS = 7

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/webhook/whatsapp",
                    json=_evolution_payload(
                        from_me=True,
                        text="#BOT#",
                        message_id="MSG_RELEASE_1",
                    ),
                )

            assert response.status_code == 200
            # graph.update_state must be called to reset the flags
            mock_graph.update_state.assert_called_once()
            call_kwargs = mock_graph.update_state.call_args
            updated_values = call_kwargs.args[1]
            assert updated_values.get("em_atendimento_humano") is False
            assert updated_values.get("requer_humano") is False

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.send_whatsapp_message", new_callable=AsyncMock, return_value=True)
    @patch("src.api.routes.whatsapp.graph")
    async def test_release_command_sends_confirmation_to_owner(self, mock_graph, mock_send):
        """After #BOT# release, owner receives confirmation message."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_snapshot = MagicMock()
        mock_snapshot.values = {"em_atendimento_humano": True}
        mock_graph.get_state.return_value = mock_snapshot
        mock_graph.update_state = MagicMock()

        with patch("src.api.routes.whatsapp.graph", mock_graph), \
             patch("src.api.routes.whatsapp.send_whatsapp_message", mock_send), \
             patch("src.api.routes.whatsapp.settings") as mock_settings:

            mock_settings.EVOLUTION_API_KEY = ""
            mock_settings.HUMAN_RELEASE_COMMAND = "#BOT#"
            mock_settings.STORE_OWNER_PHONE = "5511888888888"
            mock_settings.MESSAGE_BUFFER_WAIT_SECONDS = 7

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/webhook/whatsapp",
                    json=_evolution_payload(
                        from_me=True,
                        text="#BOT#",
                        message_id="MSG_RELEASE_2",
                    ),
                )

            assert response.status_code == 200
            # Confirmation to owner
            owner_calls = [
                call for call in mock_send.call_args_list
                if call.args[1] == "5511888888888"
            ]
            assert len(owner_calls) == 1

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.send_whatsapp_message", new_callable=AsyncMock, return_value=True)
    @patch("src.api.routes.whatsapp.graph")
    async def test_release_command_not_forwarded_to_customer(self, mock_graph, mock_send):
        """The #BOT# command itself is NOT forwarded to the customer."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_snapshot = MagicMock()
        mock_snapshot.values = {"em_atendimento_humano": True}
        mock_graph.get_state.return_value = mock_snapshot
        mock_graph.update_state = MagicMock()

        with patch("src.api.routes.whatsapp.graph", mock_graph), \
             patch("src.api.routes.whatsapp.send_whatsapp_message", mock_send), \
             patch("src.api.routes.whatsapp.settings") as mock_settings:

            mock_settings.EVOLUTION_API_KEY = ""
            mock_settings.HUMAN_RELEASE_COMMAND = "#BOT#"
            mock_settings.STORE_OWNER_PHONE = "5511888888888"
            mock_settings.MESSAGE_BUFFER_WAIT_SECONDS = 7

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/webhook/whatsapp",
                    json=_evolution_payload(
                        from_me=True,
                        text="#BOT#",
                        message_id="MSG_RELEASE_3",
                    ),
                )

            # Must NOT be forwarded to customer phone
            customer_calls = [
                call for call in mock_send.call_args_list
                if call.args[1] == "5511999999999"
            ]
            assert len(customer_calls) == 0

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.send_whatsapp_message", new_callable=AsyncMock, return_value=True)
    @patch("src.api.routes.whatsapp.graph")
    async def test_normal_message_forwarded_not_release(self, mock_graph, mock_send):
        """Non-release fromMe message is forwarded to customer (not treated as #BOT#)."""
        from fastapi.testclient import TestClient
        from src.main import app

        mock_snapshot = MagicMock()
        mock_snapshot.values = {"em_atendimento_humano": True}
        mock_graph.get_state.return_value = mock_snapshot

        with patch("src.api.routes.whatsapp.graph", mock_graph), \
             patch("src.api.routes.whatsapp.send_whatsapp_message", mock_send), \
             patch("src.api.routes.whatsapp.settings") as mock_settings:

            mock_settings.EVOLUTION_API_KEY = ""
            mock_settings.HUMAN_RELEASE_COMMAND = "#BOT#"
            mock_settings.STORE_OWNER_PHONE = "5511888888888"
            mock_settings.MESSAGE_BUFFER_WAIT_SECONDS = 7

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/webhook/whatsapp",
                    json=_evolution_payload(
                        from_me=True,
                        text="Estamos resolvendo seu problema!",
                        message_id="MSG_FWD_1",
                    ),
                )

            assert response.status_code == 200
            # Must be forwarded to customer
            customer_calls = [
                call for call in mock_send.call_args_list
                if call.args[1] == "5511999999999"
            ]
            assert len(customer_calls) == 1
            # Must NOT call update_state (no release)
            mock_graph.update_state.assert_not_called()


# ---------------------------------------------------------------------------
# Settings — new fields
# ---------------------------------------------------------------------------

class TestNewSettings:
    def test_store_owner_phone_default_empty(self):
        """STORE_OWNER_PHONE defaults to empty string."""
        from src.config.settings import Settings
        s = Settings()
        assert hasattr(s, "STORE_OWNER_PHONE")
        assert isinstance(s.STORE_OWNER_PHONE, str)

    def test_human_release_command_default(self):
        """HUMAN_RELEASE_COMMAND defaults to #BOT#."""
        from src.config.settings import Settings
        s = Settings()
        assert hasattr(s, "HUMAN_RELEASE_COMMAND")
        assert s.HUMAN_RELEASE_COMMAND == "#BOT#"

    def test_store_owner_phone_from_env(self, monkeypatch):
        """STORE_OWNER_PHONE reads from environment variable."""
        monkeypatch.setenv("STORE_OWNER_PHONE", "5511777777777")
        import importlib
        import src.config
        settings_module = importlib.import_module("src.config.settings")
        importlib.reload(settings_module)
        assert settings_module.Settings().STORE_OWNER_PHONE == "5511777777777"

    def test_human_release_command_from_env(self, monkeypatch):
        """HUMAN_RELEASE_COMMAND reads from environment variable."""
        monkeypatch.setenv("HUMAN_RELEASE_COMMAND", "#LIBERAR#")
        import importlib
        settings_module = importlib.import_module("src.config.settings")
        importlib.reload(settings_module)
        assert settings_module.Settings().HUMAN_RELEASE_COMMAND == "#LIBERAR#"
