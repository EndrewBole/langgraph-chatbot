"""Testes async da integracao Evolution API."""
import pytest
import httpx
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_response_success():
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 201
    resp.json.return_value = {"key": {"id": "ABCDEF123"}, "status": "PENDING"}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_response_error():
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 400
    resp.text = "Bad Request"
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=MagicMock(), response=resp
    )
    return resp


class TestSendWhatsAppMessageAsync:
    @pytest.mark.asyncio
    async def test_success(self, mock_response_success):
        from src.integrations.evolution import send_whatsapp_message

        client = MagicMock(spec=httpx.AsyncClient)

        async def mock_post(*args, **kwargs):
            return mock_response_success

        client.post = mock_post

        result = await send_whatsapp_message(client, "5511999999999", "Ola!")
        assert result is True

    @pytest.mark.asyncio
    async def test_failure(self, mock_response_error):
        from src.integrations.evolution import send_whatsapp_message

        client = MagicMock(spec=httpx.AsyncClient)

        async def mock_post(*args, **kwargs):
            return mock_response_error

        client.post = mock_post

        result = await send_whatsapp_message(client, "5511999999999", "Ola!")
        assert result is False

    @pytest.mark.asyncio
    async def test_network_error_returns_false(self):
        from src.integrations.evolution import send_whatsapp_message

        client = MagicMock(spec=httpx.AsyncClient)

        async def mock_post(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        client.post = mock_post

        result = await send_whatsapp_message(client, "5511999999999", "Ola!")
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self, mock_response_success):
        from src.integrations.evolution import send_whatsapp_message

        client = MagicMock(spec=httpx.AsyncClient)
        captured_kwargs = {}

        async def mock_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_response_success

        client.post = mock_post

        await send_whatsapp_message(client, "5511999999999", "Ola!")
        assert captured_kwargs["json"] == {"number": "5511999999999", "text": "Ola!"}

    @pytest.mark.asyncio
    async def test_sends_correct_headers(self, mock_response_success):
        from src.integrations.evolution import send_whatsapp_message

        client = MagicMock(spec=httpx.AsyncClient)
        captured_kwargs = {}

        async def mock_post(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_response_success

        client.post = mock_post

        await send_whatsapp_message(client, "5511999999999", "Ola!")
        assert "apikey" in captured_kwargs["headers"]


class TestSendMessageSync:
    @patch("src.integrations.evolution.httpx.post")
    def test_success(self, mock_post):
        from src.integrations.evolution import send_message

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = send_message("5511999999999", "Ola!")
        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"] == {"number": "5511999999999", "text": "Ola!"}

    @patch("src.integrations.evolution.httpx.post")
    def test_failure(self, mock_post):
        from src.integrations.evolution import send_message

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp
        )
        mock_post.return_value = mock_resp

        result = send_message("5511999999999", "Ola!")
        assert result is False

    @patch("src.integrations.evolution.httpx.post")
    def test_network_error_returns_false(self, mock_post):
        from src.integrations.evolution import send_message

        mock_post.side_effect = httpx.ConnectError("connection refused")

        result = send_message("5511999999999", "Ola!")
        assert result is False


class TestSendLinkButton:
    @patch("src.integrations.evolution.httpx.post")
    def test_success_sends_text_with_url(self, mock_post):
        from src.integrations.evolution import send_link_button

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = send_link_button("5511999999999", "https://mercadolivre.com.br/produto")
        assert result is True
        payload = mock_post.call_args.kwargs["json"]
        assert "https://mercadolivre.com.br/produto" in payload["text"]

    @patch("src.integrations.evolution.httpx.post")
    def test_includes_message_before_url(self, mock_post):
        from src.integrations.evolution import send_link_button

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        send_link_button(
            "5511999999999",
            "https://mercadolivre.com.br/produto",
            message="Confira o produto",
        )
        payload = mock_post.call_args.kwargs["json"]
        assert "Confira o produto" in payload["text"]
        assert "https://mercadolivre.com.br/produto" in payload["text"]

    @patch("src.integrations.evolution.httpx.post")
    def test_uses_title_when_no_message(self, mock_post):
        from src.integrations.evolution import send_link_button

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        send_link_button(
            "5511999999999",
            "https://mercadolivre.com.br/produto",
            title="Comprar agora",
        )
        payload = mock_post.call_args.kwargs["json"]
        assert "Comprar agora" in payload["text"]

    @patch("src.integrations.evolution.httpx.post")
    def test_http_error_returns_false(self, mock_post):
        from src.integrations.evolution import send_link_button

        mock_post.side_effect = httpx.ConnectError("refused")
        result = send_link_button("5511999999999", "https://mercadolivre.com.br/produto")
        assert result is False

    @patch("src.integrations.evolution.httpx.post")
    def test_status_error_returns_false(self, mock_post):
        from src.integrations.evolution import send_link_button

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp
        )
        mock_post.return_value = mock_resp
        result = send_link_button("5511999999999", "https://mercadolivre.com.br/produto")
        assert result is False

    @patch("src.integrations.evolution.httpx.post")
    def test_uses_sendtext_endpoint(self, mock_post):
        """Uses /message/sendText for reliable delivery."""
        from src.integrations.evolution import send_link_button

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        send_link_button("5511999999999", "https://mercadolivre.com.br/produto")
        url_called = mock_post.call_args[0][0]
        assert "/message/sendText/" in url_called
