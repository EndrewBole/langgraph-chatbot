"""Tests for src/scheduler/catalog_reindex.py — catalog auto-reindex scheduler."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from langchain_core.documents import Document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(content: str, file_type: str = "xlsx") -> Document:
    return Document(page_content=content, metadata={"file_type": file_type, "source": "test"})


# Patch targets point to the original modules (lazy-imported inside run_reindex)
_LOADERS = "src.rag.loaders.load_all_from_dir"
_SPLIT_PROD = "src.rag.splitters.split_products"
_SPLIT_DOCS = "src.rag.splitters.split_documents"
_CREATE_VS = "src.rag.indexer.create_vectorstore"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_reindex_calls_pipeline(tmp_path):
    """run_reindex loads, splits, and indexes documents via create_vectorstore."""
    fake_docs = [_make_doc("Filtro de Ar | Honda | Biz 125")]
    fake_chunks = [_make_doc("Filtro de Ar chunk")]

    with (
        patch("src.scheduler.catalog_reindex.settings") as mock_settings,
        patch(_LOADERS, return_value=fake_docs) as mock_load,
        patch(_SPLIT_PROD, return_value=fake_chunks) as mock_split_prod,
        patch(_SPLIT_DOCS, return_value=[]),
        patch(_CREATE_VS, return_value=MagicMock()) as mock_create,
    ):
        mock_settings.CATALOG_REINDEX_ENABLED = True
        mock_settings.DATA_DIR = str(tmp_path)

        from src.scheduler.catalog_reindex import run_reindex

        result = await run_reindex()

    mock_load.assert_called_once_with(str(tmp_path))
    mock_split_prod.assert_called_once_with(fake_docs)
    mock_create.assert_called_once_with(fake_chunks)
    assert result == len(fake_chunks)


@pytest.mark.asyncio
async def test_run_reindex_skips_when_disabled():
    """When CATALOG_REINDEX_ENABLED is False, run_reindex returns 0 immediately."""
    with patch("src.scheduler.catalog_reindex.settings") as mock_settings:
        mock_settings.CATALOG_REINDEX_ENABLED = False

        from src.scheduler.catalog_reindex import run_reindex

        result = await run_reindex()

    assert result == 0


@pytest.mark.asyncio
async def test_run_reindex_handles_empty_dir(tmp_path):
    """Empty data directory returns 0 without crashing."""
    with (
        patch("src.scheduler.catalog_reindex.settings") as mock_settings,
        patch(_LOADERS, return_value=[]) as mock_load,
    ):
        mock_settings.CATALOG_REINDEX_ENABLED = True
        mock_settings.DATA_DIR = str(tmp_path)

        from src.scheduler.catalog_reindex import run_reindex

        result = await run_reindex()

    mock_load.assert_called_once()
    assert result == 0


@pytest.mark.asyncio
async def test_run_reindex_handles_error_gracefully():
    """Exception in the pipeline is caught and logged, returns 0."""
    with (
        patch("src.scheduler.catalog_reindex.settings") as mock_settings,
        patch(_LOADERS, side_effect=RuntimeError("disk error")),
        patch("src.scheduler.catalog_reindex.logger") as mock_logger,
    ):
        mock_settings.CATALOG_REINDEX_ENABLED = True
        mock_settings.DATA_DIR = "/nonexistent"

        from src.scheduler.catalog_reindex import run_reindex

        result = await run_reindex()

    assert result == 0
    mock_logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_run_reindex_logs_result(tmp_path, caplog):
    """Verify logging of indexed document count."""
    fake_docs = [_make_doc("Peca A"), _make_doc("Peca B")]
    fake_chunks = [_make_doc("chunk1"), _make_doc("chunk2")]

    with (
        patch("src.scheduler.catalog_reindex.settings") as mock_settings,
        patch(_LOADERS, return_value=fake_docs),
        patch(_SPLIT_PROD, return_value=fake_chunks),
        patch(_SPLIT_DOCS, return_value=[]),
        patch(_CREATE_VS, return_value=MagicMock()),
    ):
        mock_settings.CATALOG_REINDEX_ENABLED = True
        mock_settings.DATA_DIR = str(tmp_path)

        with caplog.at_level(logging.INFO, logger="src.scheduler.catalog_reindex"):
            from src.scheduler.catalog_reindex import run_reindex

            result = await run_reindex()

    assert result == 2
    assert any("2 new documents indexed" in msg for msg in caplog.messages)


@pytest.mark.asyncio
async def test_run_reindex_returns_zero_when_all_already_indexed(tmp_path):
    """When create_vectorstore returns None (all dupes), run_reindex returns 0."""
    fake_docs = [_make_doc("Peca A")]
    fake_chunks = [_make_doc("chunk1")]

    with (
        patch("src.scheduler.catalog_reindex.settings") as mock_settings,
        patch(_LOADERS, return_value=fake_docs),
        patch(_SPLIT_PROD, return_value=fake_chunks),
        patch(_SPLIT_DOCS, return_value=[]),
        patch(_CREATE_VS, return_value=None) as mock_create,
    ):
        mock_settings.CATALOG_REINDEX_ENABLED = True
        mock_settings.DATA_DIR = str(tmp_path)

        from src.scheduler.catalog_reindex import run_reindex

        result = await run_reindex()

    assert result == 0
    mock_create.assert_called_once()
