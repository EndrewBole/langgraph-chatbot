"""Testes da integração Whisper (async)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx

from src.integrations.whisper import transcribe_audio


@pytest.mark.asyncio
async def test_transcribe_audio_returns_text():
    mock_download = MagicMock()
    mock_download.content = b"fake-audio-bytes"
    mock_download.raise_for_status = MagicMock()

    mock_transcribe = MagicMock()
    mock_transcribe.json.return_value = {"text": "preciso de um filtro de óleo"}
    mock_transcribe.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_download
    mock_client.post.return_value = mock_transcribe

    result = await transcribe_audio(client=mock_client, media_url="https://api.twilio.com/media/audio.ogg")
    assert result == "preciso de um filtro de óleo"


@pytest.mark.asyncio
async def test_transcribe_audio_error_returns_empty():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectError("network error")

    result = await transcribe_audio(client=mock_client, media_url="https://api.twilio.com/media/audio.ogg")
    assert result == ""


@pytest.mark.asyncio
async def test_transcribe_http_status_error_returns_empty():
    """HTTPStatusError no POST do Whisper retorna string vazia."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    download_resp = MagicMock()
    download_resp.content = b"audio_bytes"
    download_resp.raise_for_status = MagicMock()
    mock_client.get.return_value = download_resp

    transcribe_resp = MagicMock()
    transcribe_resp.status_code = 400
    transcribe_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "bad request", request=MagicMock(), response=transcribe_resp
    )
    mock_client.post.return_value = transcribe_resp

    result = await transcribe_audio(client=mock_client, media_url="https://audio.ogg")
    assert result == ""
