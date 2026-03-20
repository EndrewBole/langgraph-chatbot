"""Testes de reconhecimento de imagem via OpenAI Vision."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.integrations.evolution import parse_incoming_message


# --- Tests for parse_incoming_message image extraction ---


class TestParseIncomingImage:
    def test_parse_incoming_extracts_image_url(self):
        """Payload com imageMessage retorna image_url."""
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "IMG1",
                },
                "message": {
                    "imageMessage": {
                        "url": "https://mmg.whatsapp.net/image/test.jpg",
                    }
                },
            },
        }
        parsed = parse_incoming_message(payload)
        assert parsed["image_url"] == "https://mmg.whatsapp.net/image/test.jpg"
        assert parsed["image_caption"] == ""

    def test_parse_incoming_no_image_returns_none(self):
        """Payload de texto normal retorna image_url vazio."""
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "TXT1",
                },
                "message": {"conversation": "oi preciso de filtro"},
            },
        }
        parsed = parse_incoming_message(payload)
        assert parsed["image_url"] == ""
        assert parsed["image_caption"] == ""

    def test_parse_incoming_image_with_caption(self):
        """imageMessage com caption retorna ambos image_url e image_caption."""
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "IMG2",
                },
                "message": {
                    "imageMessage": {
                        "url": "https://mmg.whatsapp.net/image/part.jpg",
                        "caption": "que peca e essa?",
                    }
                },
            },
        }
        parsed = parse_incoming_message(payload)
        assert parsed["image_url"] == "https://mmg.whatsapp.net/image/part.jpg"
        assert parsed["image_caption"] == "que peca e essa?"

    def test_parse_incoming_returns_raw_key_and_message(self):
        """Parsed result includes raw_key and raw_message for Evolution API media download."""
        payload = {
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "IMG3",
                },
                "message": {
                    "imageMessage": {
                        "url": "https://mmg.whatsapp.net/image/part.jpg",
                        "mimetype": "image/jpeg",
                    }
                },
            },
        }
        parsed = parse_incoming_message(payload)
        assert parsed["raw_key"] == payload["data"]["key"]
        assert parsed["raw_message"] == payload["data"]["message"]


# --- Tests for identify_part_from_image ---


class TestIdentifyPartFromImage:
    @pytest.mark.asyncio
    async def test_identify_part_from_image_success(self):
        """Chamada bem-sucedida ao Vision API retorna descricao da peca."""
        from src.integrations.vision import identify_part_from_image

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "Filtro de oleo Honda CB300"}}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        with patch("src.integrations.vision.settings") as mock_settings:
            mock_settings.VISION_ENABLED = True
            mock_settings.VISION_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_API_KEY = "test-key"

            result = await identify_part_from_image(
                mock_client, "https://mmg.whatsapp.net/image/part.jpg"
            )

        assert result == "Filtro de oleo Honda CB300"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "api.openai.com" in call_kwargs[0][0]

    @pytest.mark.asyncio
    async def test_identify_part_from_image_error_returns_fallback(self):
        """Erro na API retorna string vazia sem crashar."""
        from src.integrations.vision import identify_part_from_image

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = httpx.ConnectError("network error")

        with patch("src.integrations.vision.settings") as mock_settings:
            mock_settings.VISION_ENABLED = True
            mock_settings.VISION_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_API_KEY = "test-key"

            result = await identify_part_from_image(
                mock_client, "https://mmg.whatsapp.net/image/part.jpg"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_identify_no_api_key(self):
        """OPENAI_API_KEY not set returns empty string."""
        from src.integrations.vision import identify_part_from_image

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        with patch("src.integrations.vision.settings") as mock_settings:
            mock_settings.VISION_ENABLED = True
            mock_settings.OPENAI_API_KEY = ""
            result = await identify_part_from_image(mock_client, "https://example.com/img.jpg")
        assert result == ""
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_identify_http_status_error(self):
        """HTTPStatusError returns empty string."""
        from src.integrations.vision import identify_part_from_image

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "rate limited"
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "rate limited", request=MagicMock(), response=mock_response
        )
        with patch("src.integrations.vision.settings") as mock_settings:
            mock_settings.VISION_ENABLED = True
            mock_settings.VISION_MODEL = "gpt-4o-mini"
            mock_settings.OPENAI_API_KEY = "test-key"
            result = await identify_part_from_image(mock_client, "https://example.com/img.jpg")
        assert result == ""

    @pytest.mark.asyncio
    async def test_identify_part_disabled(self):
        """VISION_ENABLED=False retorna string vazia sem chamada a API."""
        from src.integrations.vision import identify_part_from_image

        mock_client = AsyncMock(spec=httpx.AsyncClient)

        with patch("src.integrations.vision.settings") as mock_settings:
            mock_settings.VISION_ENABLED = False

            result = await identify_part_from_image(
                mock_client, "https://mmg.whatsapp.net/image/part.jpg"
            )

        assert result == ""
        mock_client.post.assert_not_called()


# --- Tests for get_base64_from_media ---


class TestGetBase64FromMedia:
    @pytest.mark.asyncio
    async def test_get_base64_success(self):
        """Evolution API returns base64 data, function returns data URI."""
        from src.integrations.evolution import get_base64_from_media

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "base64": "iVBORw0KGgoAAAANS==",
            "mimetype": "image/jpeg",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        key = {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False, "id": "IMG1"}
        message = {"imageMessage": {"url": "https://mmg.whatsapp.net/enc", "mimetype": "image/jpeg"}}

        with patch("src.integrations.evolution.settings") as mock_settings:
            mock_settings.EVOLUTION_API_URL = "http://localhost:8080"
            mock_settings.EVOLUTION_INSTANCE_NAME = "test"
            mock_settings.EVOLUTION_API_KEY = "test-key"

            result = await get_base64_from_media(mock_client, key, message)

        assert result == "data:image/jpeg;base64,iVBORw0KGgoAAAANS=="
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "getBase64FromMediaMessage" in call_kwargs[0][0]

    @pytest.mark.asyncio
    async def test_get_base64_already_has_data_uri_prefix(self):
        """If Evolution API returns base64 with data: prefix, don't double-wrap."""
        from src.integrations.evolution import get_base64_from_media

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "base64": "data:image/png;base64,iVBORw0KGgo==",
            "mimetype": "image/png",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        with patch("src.integrations.evolution.settings") as mock_settings:
            mock_settings.EVOLUTION_API_URL = "http://localhost:8080"
            mock_settings.EVOLUTION_INSTANCE_NAME = "test"
            mock_settings.EVOLUTION_API_KEY = "test-key"

            result = await get_base64_from_media(mock_client, {}, {})

        assert result == "data:image/png;base64,iVBORw0KGgo=="

    @pytest.mark.asyncio
    async def test_get_base64_empty_response(self):
        """Empty base64 in response returns empty string."""
        from src.integrations.evolution import get_base64_from_media

        mock_response = MagicMock()
        mock_response.json.return_value = {"base64": "", "mimetype": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        with patch("src.integrations.evolution.settings") as mock_settings:
            mock_settings.EVOLUTION_API_URL = "http://localhost:8080"
            mock_settings.EVOLUTION_INSTANCE_NAME = "test"
            mock_settings.EVOLUTION_API_KEY = "test-key"

            result = await get_base64_from_media(mock_client, {}, {})

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_base64_network_error(self):
        """Network error returns empty string without crashing."""
        from src.integrations.evolution import get_base64_from_media

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = httpx.ConnectError("connection refused")

        with patch("src.integrations.evolution.settings") as mock_settings:
            mock_settings.EVOLUTION_API_URL = "http://localhost:8080"
            mock_settings.EVOLUTION_INSTANCE_NAME = "test"
            mock_settings.EVOLUTION_API_KEY = "test-key"

            result = await get_base64_from_media(mock_client, {}, {})

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_base64_sends_correct_payload(self):
        """Verify the payload sent to Evolution API has correct structure."""
        from src.integrations.evolution import get_base64_from_media

        mock_response = MagicMock()
        mock_response.json.return_value = {"base64": "abc123", "mimetype": "image/jpeg"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        key = {"remoteJid": "5511999@s.whatsapp.net", "fromMe": False, "id": "X"}
        message = {"imageMessage": {"url": "https://enc.url", "mimetype": "image/jpeg"}}

        with patch("src.integrations.evolution.settings") as mock_settings:
            mock_settings.EVOLUTION_API_URL = "http://evo:8080"
            mock_settings.EVOLUTION_INSTANCE_NAME = "mybot"
            mock_settings.EVOLUTION_API_KEY = "key123"

            await get_base64_from_media(mock_client, key, message)

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://evo:8080/chat/getBase64FromMediaMessage/mybot"
        sent_json = call_args[1]["json"]
        assert sent_json["message"]["key"] == key
        assert sent_json["message"]["message"] == message
        assert sent_json["convertToMp4"] is False


# --- Integration test: webhook image triggers vision ---


class TestWebhookImageIntegration:
    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch(
        "src.api.routes.whatsapp.transcribe_audio",
        new_callable=AsyncMock,
        return_value="",
    )
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_webhook_image_triggers_vision(
        self, mock_buffer, mock_transcribe, mock_validate
    ):
        """Webhook com imagem chama get_base64_from_media + identify_part_from_image."""
        from fastapi.testclient import TestClient
        from src.main import app

        payload = {
            "event": "messages.upsert",
            "instance": "temporalis",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "IMGWEBHOOK1",
                },
                "message": {
                    "imageMessage": {
                        "url": "https://mmg.whatsapp.net/image/part.jpg",
                        "caption": "",
                    }
                },
                "messageType": "imageMessage",
            },
        }

        with patch(
            "src.api.routes.whatsapp.get_base64_from_media",
            new_callable=AsyncMock,
            return_value="data:image/jpeg;base64,abc123",
        ) as mock_base64, patch(
            "src.api.routes.whatsapp.identify_part_from_image",
            new_callable=AsyncMock,
            return_value="Filtro de oleo CB300",
        ) as mock_vision:
            app.state.http_client = AsyncMock(spec=httpx.AsyncClient)
            client = TestClient(app)
            response = client.post("/webhook/whatsapp", json=payload)

        assert response.status_code == 200
        mock_base64.assert_called_once()
        mock_vision.assert_called_once()
        # Vision should receive the base64 URI, not the raw WhatsApp URL
        vision_call_args = mock_vision.call_args[0]
        assert vision_call_args[1] == "data:image/jpeg;base64,abc123"
        mock_buffer.assert_called_once()
        buffer_call_args = mock_buffer.call_args[0]
        assert buffer_call_args[2] == "Filtro de oleo CB300"

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_webhook_image_with_caption_prepends(
        self, mock_buffer, mock_validate
    ):
        """Webhook com imagem e caption combina caption + descricao vision."""
        from fastapi.testclient import TestClient
        from src.main import app

        payload = {
            "event": "messages.upsert",
            "instance": "temporalis",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "IMGWEBHOOK2",
                },
                "message": {
                    "imageMessage": {
                        "url": "https://mmg.whatsapp.net/image/part.jpg",
                        "caption": "que peca e essa?",
                    }
                },
                "messageType": "imageMessage",
            },
        }

        with patch(
            "src.api.routes.whatsapp.get_base64_from_media",
            new_callable=AsyncMock,
            return_value="data:image/jpeg;base64,abc123",
        ), patch(
            "src.api.routes.whatsapp.identify_part_from_image",
            new_callable=AsyncMock,
            return_value="Filtro de oleo CB300",
        ) as mock_vision:
            app.state.http_client = AsyncMock(spec=httpx.AsyncClient)
            client = TestClient(app)
            response = client.post("/webhook/whatsapp", json=payload)

        assert response.status_code == 200
        mock_buffer.assert_called_once()
        buffer_call_args = mock_buffer.call_args[0]
        assert buffer_call_args[2] == "que peca e essa? Filtro de oleo CB300"

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    def test_webhook_image_base64_fails_skips_vision(
        self, mock_buffer, mock_validate
    ):
        """When base64 download fails, vision is not called and message is skipped."""
        from fastapi.testclient import TestClient
        from src.main import app

        payload = {
            "event": "messages.upsert",
            "instance": "temporalis",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": False,
                    "id": "IMGWEBHOOK3",
                },
                "message": {
                    "imageMessage": {
                        "url": "https://mmg.whatsapp.net/image/part.jpg",
                        "caption": "",
                    }
                },
                "messageType": "imageMessage",
            },
        }

        with patch(
            "src.api.routes.whatsapp.get_base64_from_media",
            new_callable=AsyncMock,
            return_value="",
        ) as mock_base64, patch(
            "src.api.routes.whatsapp.identify_part_from_image",
            new_callable=AsyncMock,
        ) as mock_vision:
            app.state.http_client = AsyncMock(spec=httpx.AsyncClient)
            client = TestClient(app)
            response = client.post("/webhook/whatsapp", json=payload)

        assert response.status_code == 200
        mock_base64.assert_called_once()
        mock_vision.assert_not_called()
        mock_buffer.assert_not_called()
