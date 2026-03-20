"""Tests for Chatwoot API integration — handoff notifications."""

from unittest.mock import MagicMock, patch

import httpx

from src.integrations.chatwoot import notify_handoff, resolve_conversation


@patch("src.integrations.chatwoot.settings")
@patch("src.integrations.chatwoot.httpx")
def test_notify_handoff_adds_label_note_and_pending(mock_httpx, mock_settings):
    """notify_handoff deve adicionar label, nota interna e status pending."""
    mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
    mock_settings.CHATWOOT_API_KEY = "test-key"
    mock_settings.CHATWOOT_ACCOUNT_ID = "1"

    # Mock search response
    search_resp = MagicMock()
    search_resp.json.return_value = {"payload": [{"id": 4}]}

    # Mock conversations response
    conv_resp = MagicMock()
    conv_resp.json.return_value = {"payload": [{"id": 2}]}

    # Mock get conversation (for current labels)
    get_conv_resp = MagicMock()
    get_conv_resp.json.return_value = {"labels": []}

    # Mock post responses
    post_resp = MagicMock()

    mock_httpx.get.side_effect = [search_resp, conv_resp, get_conv_resp]
    mock_httpx.post.return_value = post_resp

    result = notify_handoff("5511930851865")

    assert result is True
    assert mock_httpx.post.call_count == 4  # label + note + status + assignment(id=1)


@patch("src.integrations.chatwoot.settings")
def test_notify_handoff_skips_when_not_configured(mock_settings):
    """Deve retornar False quando Chatwoot nao esta configurado."""
    mock_settings.CHATWOOT_API_URL = ""
    mock_settings.CHATWOOT_API_KEY = ""

    result = notify_handoff("5511930851865")
    assert result is False


@patch("src.integrations.chatwoot.settings")
@patch("src.integrations.chatwoot.httpx")
def test_notify_handoff_returns_false_when_no_conversation(mock_httpx, mock_settings):
    """Deve retornar False quando conversa nao encontrada."""
    mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
    mock_settings.CHATWOOT_API_KEY = "test-key"
    mock_settings.CHATWOOT_ACCOUNT_ID = "1"

    search_resp = MagicMock()
    search_resp.json.return_value = {"payload": []}
    mock_httpx.get.return_value = search_resp

    result = notify_handoff("5511999999999")
    assert result is False


@patch("src.integrations.chatwoot.settings")
@patch("src.integrations.chatwoot.httpx")
def test_resolve_conversation_resolves_and_assigns_bot(mock_httpx, mock_settings):
    """resolve_conversation deve resolver conversa, remover label e atribuir ao bot."""
    mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
    mock_settings.CHATWOOT_API_KEY = "test-key"
    mock_settings.CHATWOOT_ACCOUNT_ID = "1"

    # Mock search response
    search_resp = MagicMock()
    search_resp.json.return_value = {"payload": [{"id": 4}]}

    # Mock conversations response
    conv_resp = MagicMock()
    conv_resp.json.return_value = {"payload": [{"id": 2}]}

    # Mock get conversation (for current labels)
    get_conv_resp = MagicMock()
    get_conv_resp.json.return_value = {"labels": ["atendimento-humano"]}

    mock_httpx.get.side_effect = [search_resp, conv_resp, get_conv_resp]
    mock_httpx.post.return_value = MagicMock()

    result = resolve_conversation("5511930851865")

    assert result is True
    # 2 posts: toggle_status(resolved) + labels(remove)
    assert mock_httpx.post.call_count == 2


@patch("src.integrations.chatwoot.settings")
def test_resolve_conversation_skips_when_not_configured(mock_settings):
    """Deve retornar False quando Chatwoot nao esta configurado."""
    mock_settings.CHATWOOT_API_URL = ""
    mock_settings.CHATWOOT_API_KEY = ""

    result = resolve_conversation("5511930851865")
    assert result is False


# ===========================================================================
# Tests: _find_conversation_by_phone error handling
# ===========================================================================


class TestFindConversationByPhone:
    @patch("src.integrations.chatwoot.httpx.get")
    @patch("src.integrations.chatwoot.settings")
    def test_find_conversation_error_returns_none(self, mock_settings, mock_get):
        """Network error in _find_conversation_by_phone returns None."""
        from src.integrations.chatwoot import _find_conversation_by_phone

        mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
        mock_settings.CHATWOOT_API_KEY = "token"
        mock_settings.CHATWOOT_ACCOUNT_ID = "1"
        mock_get.side_effect = httpx.ConnectError("fail")
        result = _find_conversation_by_phone("5511999")
        assert result is None


# ===========================================================================
# Tests: notify_handoff error handling
# ===========================================================================


class TestNotifyHandoffErrors:
    @patch("src.integrations.chatwoot.httpx.get")
    @patch("src.integrations.chatwoot.httpx.post")
    @patch("src.integrations.chatwoot._find_conversation_by_phone", return_value=42)
    @patch("src.integrations.chatwoot.settings")
    def test_label_error_returns_false(self, mock_settings, mock_find, mock_post, mock_get):
        """Label step failure makes notify_handoff return False."""
        mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
        mock_settings.CHATWOOT_API_KEY = "token"
        mock_settings.CHATWOOT_ACCOUNT_ID = "1"
        # GET for labels fails
        mock_get.side_effect = httpx.ConnectError("fail")
        # POST for internal note + toggle_status + assignments succeed
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        result = notify_handoff("5511999")
        assert result is False

    @patch("src.integrations.chatwoot.httpx.get")
    @patch("src.integrations.chatwoot.httpx.post")
    @patch("src.integrations.chatwoot._find_conversation_by_phone", return_value=42)
    @patch("src.integrations.chatwoot.settings")
    def test_note_error_returns_false(self, mock_settings, mock_find, mock_post, mock_get):
        """Note step failure makes notify_handoff return False."""
        mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
        mock_settings.CHATWOOT_API_KEY = "token"
        mock_settings.CHATWOOT_ACCOUNT_ID = "1"
        # GET for labels succeeds
        mock_get_resp = MagicMock()
        mock_get_resp.raise_for_status = MagicMock()
        mock_get_resp.json.return_value = {"labels": []}
        mock_get.return_value = mock_get_resp
        # All POST calls fail
        mock_post.side_effect = httpx.ConnectError("fail")
        result = notify_handoff("5511999")
        assert result is False


# ===========================================================================
# Tests: resolve_conversation error handling
# ===========================================================================


class TestResolveConversationErrors:
    @patch("src.integrations.chatwoot.httpx.get")
    @patch("src.integrations.chatwoot.httpx.post")
    @patch("src.integrations.chatwoot._find_conversation_by_phone", return_value=42)
    @patch("src.integrations.chatwoot.settings")
    def test_resolve_toggle_error(self, mock_settings, mock_find, mock_post, mock_get):
        """Toggle status failure makes resolve_conversation return False."""
        mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
        mock_settings.CHATWOOT_API_KEY = "token"
        mock_settings.CHATWOOT_ACCOUNT_ID = "1"
        mock_post.side_effect = httpx.ConnectError("fail")
        mock_get_resp = MagicMock()
        mock_get_resp.raise_for_status = MagicMock()
        mock_get_resp.json.return_value = {"labels": ["atendimento-humano"]}
        mock_get.return_value = mock_get_resp
        result = resolve_conversation("5511999")
        assert result is False
