"""Testes para a funcao chat() do main.py (modo CLI)."""
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage


class TestChatStateNotOverwritten:
    """Garantir que chat() nao sobrescreve campos persistidos do checkpointer."""

    @patch("src.main.graph")
    def test_chat_does_not_pass_tentativas(self, mock_graph):
        """chat() nao deve passar tentativas_categoria_e no input do graph.invoke."""
        mock_graph.invoke.return_value = {
            "messages": [AIMessage(content="Ola!")]
        }

        from src.main import chat

        result = chat("oi")

        call_args = mock_graph.invoke.call_args[0][0]
        assert "tentativas_categoria_e" not in call_args
        assert "requer_humano" not in call_args
        assert "em_atendimento_humano" not in call_args
        assert "category" not in call_args

    @patch("src.main.graph")
    def test_chat_passes_required_fields(self, mock_graph):
        """chat() deve passar messages, session_id e chat_phone."""
        mock_graph.invoke.return_value = {
            "messages": [AIMessage(content="Ola!")]
        }

        from src.main import chat

        result = chat("preciso de filtro")

        call_args = mock_graph.invoke.call_args[0][0]
        assert "messages" in call_args
        assert "session_id" in call_args
        assert "chat_phone" in call_args
        assert result == "Ola!"
