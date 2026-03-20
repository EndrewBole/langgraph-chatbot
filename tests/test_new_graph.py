import pytest
from unittest.mock import patch, MagicMock


def test_graph_compiles():
    from src.graph.builder import graph

    assert graph is not None
    node_names = list(graph.nodes.keys())
    assert "chatbot" in node_names
    assert "tools" in node_names
    assert "respond" in node_names
    assert "human_handoff" in node_names
    assert "send_response" in node_names
    assert "check_status" not in node_names  # removido, usa START


def test_checkpointer_memory_saver():
    from src.memory.checkpointer import get_checkpointer

    cp = get_checkpointer(use_postgres=False)
    assert cp is not None


def test_checkpointer_postgres_with_env():
    mock_conn = MagicMock()
    mock_saver = MagicMock()
    with patch(
        "src.memory.checkpointer.settings"
    ) as mock_settings, patch(
        "psycopg.Connection.connect",
        return_value=mock_conn,
    ) as mock_connect, patch(
        "langgraph.checkpoint.postgres.PostgresSaver",
        return_value=mock_saver,
    ) as mock_pg_saver_cls:
        mock_settings.DATABASE_URL = "postgresql://user:pass@localhost:5432/testdb"

        from src.memory.checkpointer import get_checkpointer

        cp = get_checkpointer(use_postgres=True)

        mock_connect.assert_called_once_with(
            "postgresql://user:pass@localhost:5432/testdb",
            autocommit=True,
        )
        mock_pg_saver_cls.assert_called_once_with(mock_conn)
        mock_saver.setup.assert_called_once()
        assert cp is mock_saver
