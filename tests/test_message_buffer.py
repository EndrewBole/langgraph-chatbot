"""Testes do agregador de mensagens (buffer por telefone)."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def clear_buffer():
    """Limpa buffer e tasks entre testes."""
    import src.api.routes.whatsapp as module
    module._msg_buffer.clear()
    module._msg_tasks.clear()
    yield
    for task in list(module._msg_tasks.values()):
        task.cancel()
    module._msg_buffer.clear()
    module._msg_tasks.clear()


def _parsed(phone: str) -> dict:
    return {"chat_phone": phone, "session_id": phone}


@pytest.mark.asyncio
async def test_single_message_processed_after_wait():
    from src.api.routes.whatsapp import _buffer_message

    with patch("src.api.routes.whatsapp.settings") as mock_s, \
         patch("src.api.routes.whatsapp.process_message", new_callable=AsyncMock) as mock_p:
        mock_s.MESSAGE_BUFFER_WAIT_SECONDS = 0.1

        await _buffer_message("5511999", _parsed("5511999"), "preciso de filtro")
        await asyncio.sleep(0.3)

        mock_p.assert_called_once()
        assert mock_p.call_args[0][1] == "preciso de filtro"


@pytest.mark.asyncio
async def test_multiple_messages_combined():
    from src.api.routes.whatsapp import _buffer_message

    with patch("src.api.routes.whatsapp.settings") as mock_s, \
         patch("src.api.routes.whatsapp.process_message", new_callable=AsyncMock) as mock_p:
        mock_s.MESSAGE_BUFFER_WAIT_SECONDS = 0.2

        await _buffer_message("5511999", _parsed("5511999"), "preciso de filtro")
        await asyncio.sleep(0.05)
        await _buffer_message("5511999", _parsed("5511999"), "para honda cb300")
        await asyncio.sleep(0.4)

        mock_p.assert_called_once()
        combined = mock_p.call_args[0][1]
        assert "preciso de filtro" in combined
        assert "para honda cb300" in combined


@pytest.mark.asyncio
async def test_timer_resets_on_new_message():
    from src.api.routes.whatsapp import _buffer_message

    with patch("src.api.routes.whatsapp.settings") as mock_s, \
         patch("src.api.routes.whatsapp.process_message", new_callable=AsyncMock) as mock_p:
        mock_s.MESSAGE_BUFFER_WAIT_SECONDS = 0.2

        await _buffer_message("5511999", _parsed("5511999"), "msg 1")
        await asyncio.sleep(0.15)  # quase no limite, ainda não processou
        await _buffer_message("5511999", _parsed("5511999"), "msg 2")  # reseta o timer
        await asyncio.sleep(0.15)  # ainda dentro do novo timer

        mock_p.assert_not_called()

        await asyncio.sleep(0.15)  # agora expirou
        mock_p.assert_called_once()


@pytest.mark.asyncio
async def test_different_phones_buffered_separately():
    from src.api.routes.whatsapp import _buffer_message

    with patch("src.api.routes.whatsapp.settings") as mock_s, \
         patch("src.api.routes.whatsapp.process_message", new_callable=AsyncMock) as mock_p:
        mock_s.MESSAGE_BUFFER_WAIT_SECONDS = 0.1

        await _buffer_message("5511111", _parsed("5511111"), "msg phone 1")
        await _buffer_message("5522222", _parsed("5522222"), "msg phone 2")
        await asyncio.sleep(0.3)

        assert mock_p.call_count == 2
        phones = {call[0][0]["chat_phone"] for call in mock_p.call_args_list}
        assert "5511111" in phones
        assert "5522222" in phones
