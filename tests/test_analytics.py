"""Tests for search analytics logging."""

from unittest.mock import MagicMock, patch

import pytest


class TestLogSearch:
    """Tests for _log_search function."""

    @patch("src.tools.buscar.create_client")
    def test_log_search_inserts_record(self, mock_create_client: MagicMock) -> None:
        """Verify _log_search inserts correct data into search_log table."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert

        from src.tools.buscar import _log_search

        _log_search("filtro oleo", 3, "session1")

        mock_client.table.assert_called_once_with("search_log")
        mock_table.insert.assert_called_once_with({
            "query": "filtro oleo",
            "result_count": 3,
            "session_id": "session1",
        })
        mock_insert.execute.assert_called_once()

    @patch("src.tools.buscar.settings")
    def test_log_search_disabled(self, mock_settings: MagicMock) -> None:
        """When ANALYTICS_ENABLED is False, no insert should happen."""
        mock_settings.ANALYTICS_ENABLED = False

        from src.tools.buscar import _log_search

        with patch("src.tools.buscar.create_client") as mock_create_client:
            _log_search("filtro oleo", 3, "session1")
            mock_create_client.assert_not_called()

    @patch("src.tools.buscar.create_client")
    def test_log_search_handles_error_gracefully(
        self, mock_create_client: MagicMock
    ) -> None:
        """If insert raises an exception, _log_search should not crash."""
        mock_create_client.side_effect = Exception("connection refused")

        from src.tools.buscar import _log_search

        # Should not raise
        _log_search("filtro oleo", 3, "session1")

    @patch("src.tools.buscar.create_client")
    def test_log_search_handles_insert_error_gracefully(
        self, mock_create_client: MagicMock
    ) -> None:
        """If table.insert raises, _log_search should not crash."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_client.table.return_value.insert.side_effect = Exception("insert failed")

        from src.tools.buscar import _log_search

        # Should not raise
        _log_search("filtro oleo", 3, "session1")


class TestBuscarCallsLogSearch:
    """Test that buscar() calls _log_search after retrieving results."""

    @patch("src.tools.buscar._log_search")
    @patch("src.tools.buscar.retrieve")
    @patch("src.tools.buscar._get_vectorstore")
    def test_buscar_calls_log_search_with_results(
        self,
        mock_get_vs: MagicMock,
        mock_retrieve: MagicMock,
        mock_log: MagicMock,
    ) -> None:
        """buscar() should call _log_search with query and result count."""
        from langchain_core.documents import Document

        mock_get_vs.return_value = MagicMock()
        mock_retrieve.return_value = [
            Document(page_content="Filtro CB300", metadata={}),
            Document(page_content="Filtro CG160", metadata={}),
        ]

        from src.tools.buscar import buscar

        buscar.invoke({"query": "filtro"})

        mock_log.assert_called_once_with("filtro", 2)

    @patch("src.tools.buscar._log_search")
    @patch("src.tools.buscar.retrieve")
    @patch("src.tools.buscar._get_vectorstore")
    def test_buscar_calls_log_search_zero_results(
        self,
        mock_get_vs: MagicMock,
        mock_retrieve: MagicMock,
        mock_log: MagicMock,
    ) -> None:
        """buscar() should log zero results when retrieve returns empty."""
        mock_get_vs.return_value = MagicMock()
        mock_retrieve.return_value = []

        from src.tools.buscar import buscar

        buscar.invoke({"query": "peca inexistente"})

        mock_log.assert_called_once_with("peca inexistente", 0)
