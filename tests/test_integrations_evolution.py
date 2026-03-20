"""Testes da integracao Evolution API — parsing e validacao."""
from unittest.mock import MagicMock, patch

import httpx

from src.integrations.evolution import parse_incoming_message, validate_api_key


def test_parse_text_message():
    """Extrai texto de mensagem Evolution API messages.upsert."""
    payload = {
        "event": "messages.upsert",
        "instance": "temporalis",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "ABCDEF123",
            },
            "message": {
                "conversation": "preciso de filtro para cb300",
            },
            "messageType": "conversation",
        },
    }
    result = parse_incoming_message(payload)
    assert result["session_id"] == "5511999999999"
    assert result["chat_phone"] == "5511999999999"
    assert result["body"] == "preciso de filtro para cb300"
    assert result["media_url"] == ""
    assert result["message_id"] == "ABCDEF123"


def test_parse_extended_text_message():
    """Extrai texto de extendedTextMessage."""
    payload = {
        "event": "messages.upsert",
        "instance": "temporalis",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "MSG789",
            },
            "message": {
                "extendedTextMessage": {
                    "text": "quero vela para biz 125",
                },
            },
            "messageType": "extendedTextMessage",
        },
    }
    result = parse_incoming_message(payload)
    assert result["body"] == "quero vela para biz 125"


def test_parse_audio_message():
    """Extrai URL de audio de audioMessage."""
    payload = {
        "event": "messages.upsert",
        "instance": "temporalis",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "MSG456",
            },
            "message": {
                "audioMessage": {
                    "url": "https://mmg.whatsapp.net/audio/abc.ogg",
                    "mimetype": "audio/ogg; codecs=opus",
                },
            },
            "messageType": "audioMessage",
        },
    }
    result = parse_incoming_message(payload)
    assert result["body"] == ""
    assert result["media_url"] == "https://mmg.whatsapp.net/audio/abc.ogg"


def test_parse_strips_whatsapp_suffix():
    """Remove @s.whatsapp.net do remoteJid."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "MSG1",
            },
            "message": {},
        },
    }
    result = parse_incoming_message(payload)
    assert result["session_id"] == "5511999999999"
    assert result["chat_phone"] == "5511999999999"


def test_parse_detects_group():
    """Detecta mensagem de grupo pelo sufixo @g.us."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "120363012345678901@g.us",
                "fromMe": False,
                "id": "GRPMSG1",
            },
            "message": {"conversation": "oi"},
        },
    }
    result = parse_incoming_message(payload)
    assert result["is_group"] is True


def test_parse_from_me_flag():
    """Detecta mensagem fromMe=True."""
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": True,
                "id": "MSG2",
            },
            "message": {"conversation": "oi"},
        },
    }
    result = parse_incoming_message(payload)
    assert result["from_me"] is True


def test_parse_missing_data_uses_defaults():
    """Payload vazio retorna defaults seguros."""
    result = parse_incoming_message({})
    assert result["session_id"] == ""
    assert result["body"] == ""
    assert result["media_url"] == ""
    assert result["from_me"] is False
    assert result["is_group"] is False


def test_parse_non_upsert_event():
    """Eventos que nao sao messages.upsert retornam evento no campo event."""
    payload = {
        "event": "connection.update",
        "data": {},
    }
    result = parse_incoming_message(payload)
    assert result["event"] == "connection.update"


class TestValidateApiKey:
    def test_skips_when_no_expected_key(self):
        """Pula validacao em dev mode (sem chave configurada)."""
        assert validate_api_key("any", "") is True

    def test_rejects_invalid_key(self):
        assert validate_api_key("wrong", "correct_key") is False

    def test_accepts_valid_key(self):
        assert validate_api_key("my_key", "my_key") is True


class TestValidateApiKeyInstanceToken:
    def test_instance_token_matches_api_key(self):
        """instance_token == api_key should pass validation."""
        assert validate_api_key("instance-tok", "expected", "instance-tok") is True

    def test_instance_token_matches_expected(self):
        """instance_token == expected_key should pass validation."""
        assert validate_api_key("something", "expected", "expected") is True

    def test_instance_token_no_match(self):
        """Neither api_key nor instance_token match should fail."""
        assert validate_api_key("wrong", "expected", "also-wrong") is False


class TestResolveLidToPhone:
    @patch("src.integrations.evolution.httpx.post")
    @patch("src.integrations.evolution.settings")
    def test_resolve_lid_success(self, mock_settings, mock_post):
        """Successful LID resolution returns phone number."""
        from src.integrations.evolution import resolve_lid_to_phone

        mock_settings.EVOLUTION_API_URL = "http://evo:8080"
        mock_settings.EVOLUTION_INSTANCE_NAME = "test"
        mock_settings.EVOLUTION_API_KEY = "key"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [
            {"remoteJid": "5511999@s.whatsapp.net", "pushName": "John"}
        ]
        mock_post.return_value = mock_resp
        result = resolve_lid_to_phone("John")
        assert result == "5511999"

    @patch("src.integrations.evolution.httpx.post")
    @patch("src.integrations.evolution.settings")
    def test_resolve_lid_no_match(self, mock_settings, mock_post):
        """No matching contacts returns empty string."""
        from src.integrations.evolution import resolve_lid_to_phone

        mock_settings.EVOLUTION_API_URL = "http://evo:8080"
        mock_settings.EVOLUTION_INSTANCE_NAME = "test"
        mock_settings.EVOLUTION_API_KEY = "key"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = []
        mock_post.return_value = mock_resp
        result = resolve_lid_to_phone("Unknown")
        assert result == ""

    def test_resolve_lid_empty_push_name(self):
        """Empty pushName returns empty string immediately."""
        from src.integrations.evolution import resolve_lid_to_phone

        assert resolve_lid_to_phone("") == ""

    @patch("src.integrations.evolution.httpx.post")
    @patch("src.integrations.evolution.settings")
    def test_resolve_lid_network_error(self, mock_settings, mock_post):
        """Network error returns empty string."""
        from src.integrations.evolution import resolve_lid_to_phone

        mock_settings.EVOLUTION_API_URL = "http://evo:8080"
        mock_settings.EVOLUTION_INSTANCE_NAME = "test"
        mock_settings.EVOLUTION_API_KEY = "key"
        mock_post.side_effect = httpx.ConnectError("fail")
        result = resolve_lid_to_phone("John")
        assert result == ""
