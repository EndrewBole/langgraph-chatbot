"""Testes da integracao Evolution API — redirect do antigo test_integrations_zapi.

Este arquivo agora testa a integracao Evolution API (migrado de Z-API).
Os testes principais estao em test_integrations_evolution.py.
"""
from src.integrations.evolution import parse_incoming_message, validate_api_key


def test_parse_text_message():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "MSG123",
            },
            "message": {"conversation": "preciso de filtro para cb300"},
        },
    }
    result = parse_incoming_message(payload)
    assert result["session_id"] == "5511999999999"
    assert result["chat_phone"] == "5511999999999"
    assert result["body"] == "preciso de filtro para cb300"
    assert result["media_url"] == ""


def test_parse_audio_message():
    payload = {
        "event": "messages.upsert",
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
        },
    }
    result = parse_incoming_message(payload)
    assert result["body"] == ""
    assert result["media_url"] == "https://mmg.whatsapp.net/audio/abc.ogg"


def test_parse_strips_phone():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False, "id": "1"},
            "message": {},
        },
    }
    result = parse_incoming_message(payload)
    assert result["session_id"] == "5511999999999"
    assert result["chat_phone"] == "5511999999999"


def test_parse_missing_fields_use_defaults():
    result = parse_incoming_message({})
    assert result["session_id"] == ""
    assert result["body"] == ""
    assert result["media_url"] == ""


def test_parse_from_me_flag():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": True, "id": "2"},
            "message": {"conversation": "oi"},
        },
    }
    result = parse_incoming_message(payload)
    assert result["from_me"] is True


def test_parse_group_flag():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "120363012345678901@g.us", "fromMe": False, "id": "3"},
            "message": {},
        },
    }
    result = parse_incoming_message(payload)
    assert result["is_group"] is True


class TestValidateApiKey:
    def test_skips_when_no_token(self):
        assert validate_api_key("any", "") is True

    def test_rejects_invalid_token(self):
        assert validate_api_key("wrong", "correct_token") is False

    def test_accepts_valid_token(self):
        assert validate_api_key("my_token", "my_token") is True
