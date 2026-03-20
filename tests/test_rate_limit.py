"""Tests for per-phone rate limiting."""
import time
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


def _evolution_payload(
    phone: str = "5511999999999",
    text: str = "oi",
    message_id: str = "MSG1",
) -> dict:
    """Helper para gerar payload Evolution API messages.upsert."""
    return {
        "event": "messages.upsert",
        "instance": "temporalis",
        "data": {
            "key": {
                "remoteJid": f"{phone}@s.whatsapp.net",
                "fromMe": False,
                "id": message_id,
            },
            "message": {"conversation": text},
            "messageType": "conversation",
        },
    }


class TestIsRateLimited:
    """Unit tests for _is_rate_limited function."""

    def setup_method(self):
        """Clear rate limit state before each test."""
        from src.api.routes.whatsapp import _rate_limit
        _rate_limit.clear()

    def test_allows_normal_traffic(self):
        """Send 5 messages for same phone within window, all return False."""
        from src.api.routes.whatsapp import _is_rate_limited
        for _ in range(5):
            assert _is_rate_limited("5511999999999") is False

    @patch("src.api.routes.whatsapp.settings")
    def test_blocks_after_max(self, mock_settings):
        """Send RATE_LIMIT_MAX+1 messages, last one returns True."""
        mock_settings.RATE_LIMIT_WINDOW = 60
        mock_settings.RATE_LIMIT_MAX = 10
        from src.api.routes.whatsapp import _is_rate_limited
        for _ in range(10):
            assert _is_rate_limited("5511999999999") is False
        assert _is_rate_limited("5511999999999") is True

    @patch("src.api.routes.whatsapp.settings")
    def test_resets_after_window(self, mock_settings):
        """Send max messages, advance time past window, next message allowed."""
        mock_settings.RATE_LIMIT_WINDOW = 60
        mock_settings.RATE_LIMIT_MAX = 10
        from src.api.routes.whatsapp import _is_rate_limited

        for _ in range(10):
            _is_rate_limited("5511999999999")

        # Advance time past the window
        with patch("src.api.routes.whatsapp.time") as mock_time:
            mock_time.time.return_value = time.time() + 61
            assert _is_rate_limited("5511999999999") is False

    @patch("src.api.routes.whatsapp.settings")
    def test_independent_per_phone(self, mock_settings):
        """Phone A hits limit, phone B still allowed."""
        mock_settings.RATE_LIMIT_WINDOW = 60
        mock_settings.RATE_LIMIT_MAX = 3
        from src.api.routes.whatsapp import _is_rate_limited

        # Phone A hits limit
        for _ in range(3):
            _is_rate_limited("5511111111111")
        assert _is_rate_limited("5511111111111") is True

        # Phone B still allowed
        assert _is_rate_limited("5522222222222") is False

    @patch("src.api.routes.whatsapp.settings")
    def test_cleans_old_entries(self, mock_settings):
        """After window passes, old timestamps are cleaned from the list."""
        mock_settings.RATE_LIMIT_WINDOW = 60
        mock_settings.RATE_LIMIT_MAX = 10
        from src.api.routes.whatsapp import _is_rate_limited, _rate_limit

        # Add 5 messages
        for _ in range(5):
            _is_rate_limited("5511999999999")
        assert len(_rate_limit["5511999999999"]) == 5

        # Advance time past window — next call should clean old entries
        with patch("src.api.routes.whatsapp.time") as mock_time:
            mock_time.time.return_value = time.time() + 61
            _is_rate_limited("5511999999999")
            # Old 5 expired, only the new 1 remains
            assert len(_rate_limit["5511999999999"]) == 1


class TestWebhookRateLimitIntegration:
    """Integration test: rate limited webhook returns 200 but does NOT buffer."""

    def setup_method(self):
        """Clear rate limit and dedup state before each test."""
        from src.api.routes.whatsapp import _rate_limit, _seen_messages
        _rate_limit.clear()
        _seen_messages.clear()

    @patch("src.api.routes.whatsapp.validate_api_key", return_value=True)
    @patch("src.api.routes.whatsapp._buffer_message", new_callable=AsyncMock)
    @patch("src.api.routes.whatsapp.settings")
    def test_webhook_rate_limited_returns_ok_silently(
        self, mock_settings, mock_buffer, mock_validate
    ):
        """When rate limited, webhook returns 200 but does NOT call _buffer_message."""
        mock_settings.RATE_LIMIT_WINDOW = 60
        mock_settings.RATE_LIMIT_MAX = 2
        mock_settings.EVOLUTION_API_KEY = ""
        mock_settings.MESSAGE_BUFFER_WAIT_SECONDS = 7

        from src.main import app
        client = TestClient(app)

        # First 2 messages should be buffered
        for i in range(2):
            response = client.post(
                "/webhook/whatsapp",
                json=_evolution_payload(text=f"msg{i}", message_id=f"RATE{i}"),
            )
            assert response.status_code == 200
        assert mock_buffer.call_count == 2

        # 3rd message should be rate limited — 200 OK but no buffer call
        response = client.post(
            "/webhook/whatsapp",
            json=_evolution_payload(text="spam", message_id="RATE_SPAM"),
        )
        assert response.status_code == 200
        assert mock_buffer.call_count == 2  # Still 2, not 3
