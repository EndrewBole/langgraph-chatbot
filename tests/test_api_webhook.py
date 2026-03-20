"""Testes do webhook FastAPI + integracao Evolution API."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


def _evolution_payload(
    phone: str = "5511999999999",
    from_me: bool = False,
    is_group: bool = False,
    text: str | None = None,
    audio_url: str | None = None,
    message_id: str = "MSG1",
) -> dict:
    """Helper para gerar payload Evolution API messages.upsert."""
    suffix = "@g.us" if is_group else "@s.whatsapp.net"
    remote_jid = f"{phone}{suffix}"
    message = {}
    if text:
        message["conversation"] = text
    if audio_url:
        message["audioMessage"] = {"url": audio_url, "mimetype": "audio/ogg; codecs=opus"}
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
            "messageType": "conversation" if text else "audioMessage",
        },
    }


@pytest.fixture
def client():
    from src.main import app
    return TestClient(app)


class TestWebhookEndpoint:
    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_text_message_returns_200(self, mock_buffer, mock_validate, client):
        response = client.post(
            "/webhook/whatsapp",
            json=_evolution_payload(text="oi preciso de filtro"),
        )
        assert response.status_code == 200
        mock_buffer.assert_called_once()

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_empty_message_returns_200_no_process(self, mock_buffer, mock_validate, client):
        response = client.post(
            "/webhook/whatsapp",
            json=_evolution_payload(message_id="MSG2"),
        )
        assert response.status_code == 200
        mock_buffer.assert_not_called()

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp.transcribe_audio", new_callable=AsyncMock, return_value="audio transcrito")
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_audio_message_triggers_transcription(self, mock_buffer, mock_transcribe, mock_validate, client):
        response = client.post(
            "/webhook/whatsapp",
            json=_evolution_payload(
                audio_url="https://mmg.whatsapp.net/audio/test.ogg",
                message_id="MSG3",
            ),
        )
        assert response.status_code == 200
        mock_transcribe.assert_called_once()
        mock_buffer.assert_called_once()

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_ignores_from_me_messages(self, mock_buffer, mock_validate, client):
        response = client.post(
            "/webhook/whatsapp",
            json=_evolution_payload(from_me=True, text="minha propria mensagem", message_id="MSG4"),
        )
        assert response.status_code == 200
        mock_buffer.assert_not_called()

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_ignores_group_messages(self, mock_buffer, mock_validate, client):
        response = client.post(
            "/webhook/whatsapp",
            json=_evolution_payload(is_group=True, text="mensagem de grupo", message_id="MSG5"),
        )
        assert response.status_code == 200
        mock_buffer.assert_not_called()

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_ignores_non_upsert_events(self, mock_buffer, mock_validate, client):
        """Eventos que nao sao messages.upsert devem ser ignorados."""
        response = client.post(
            "/webhook/whatsapp",
            json={"event": "connection.update", "data": {}},
        )
        assert response.status_code == 200
        mock_buffer.assert_not_called()


class TestEvolutionApiKeyValidation:
    def test_rejects_invalid_key(self, client):
        with patch("src.api.routes.whatsapp.settings") as mock_settings:
            mock_settings.EVOLUTION_API_KEY = "real_key"
            response = client.post(
                "/webhook/whatsapp",
                json=_evolution_payload(text="oi"),
                headers={"apikey": "wrong_key"},
            )
            assert response.status_code == 403

    @patch("src.api.routes.whatsapp.process_message", new_callable=AsyncMock)
    def test_skips_validation_when_no_key(self, mock_process, client):
        with patch("src.api.routes.whatsapp.settings") as mock_settings:
            mock_settings.EVOLUTION_API_KEY = ""
            mock_settings.MESSAGE_BUFFER_WAIT_SECONDS = 7
            response = client.post(
                "/webhook/whatsapp",
                json=_evolution_payload(text="oi"),
            )
            assert response.status_code == 200


class TestProcessMessageAsync:
    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.graph")
    async def test_process_message_uses_to_thread(self, mock_graph):
        from src.api.routes.whatsapp import process_message
        mock_graph.invoke.return_value = {"messages": []}
        parsed = {"session_id": "5511999", "chat_phone": "5511999"}
        with patch("src.api.routes.whatsapp.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"messages": []}
            await process_message(parsed, "oi")
            mock_to_thread.assert_called_once()


class TestStateNotOverwritten:
    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.graph")
    async def test_invoke_does_not_pass_tentativas(self, mock_graph):
        from src.api.routes.whatsapp import process_message
        mock_graph.invoke.return_value = {"messages": []}
        parsed = {"session_id": "5511999", "chat_phone": "5511999"}
        with patch("src.api.routes.whatsapp.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"messages": []}
            await process_message(parsed, "oi")
            call_args = mock_to_thread.call_args[0][1]
            assert "tentativas_categoria_e" not in call_args
            assert "requer_humano" not in call_args
            assert "em_atendimento_humano" not in call_args

    @pytest.mark.asyncio
    @patch("src.api.routes.whatsapp.graph")
    async def test_invoke_passes_required_fields(self, mock_graph):
        from src.api.routes.whatsapp import process_message
        mock_graph.invoke.return_value = {"messages": []}
        parsed = {"session_id": "5511999", "chat_phone": "5511999"}
        with patch("src.api.routes.whatsapp.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"messages": []}
            await process_message(parsed, "filtro")
            call_args = mock_to_thread.call_args[0][1]
            assert "messages" in call_args
            assert "session_id" in call_args
            assert "chat_phone" in call_args


def test_app_lifespan_creates_http_client():
    """Lifespan cria e fecha httpx.AsyncClient corretamente."""
    from src.main import app
    with TestClient(app) as client:
        assert hasattr(app.state, "http_client")
