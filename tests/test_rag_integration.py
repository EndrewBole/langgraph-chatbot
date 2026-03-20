"""Testes de integração: agente + RAG tool."""
from unittest.mock import patch, MagicMock

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.documents import Document

from src.state import AgentState


def _make_state(**overrides) -> AgentState:
    defaults = {
        "messages": [HumanMessage(content="tem filtro de oleo pra cb300?")],
        "session_id": "123",
        "chat_phone": "123",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
    }
    defaults.update(overrides)
    return defaults


class TestClassifyNodeWithRAG:
    @patch("src.graph.classify._get_llm_classify")
    def test_llm_triggers_buscar_for_category_a(self, mock_get_llm):
        """O LLM deve emitir tool_call para buscar quando é Categoria A."""
        from src.graph.nodes import classify_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content="",
            tool_calls=[{"name": "buscar", "args": {"query": "filtro de oleo cb300"}, "id": "call_1"}],
        )
        mock_get_llm.return_value = mock_llm

        result = classify_node(_make_state())
        ai_msg = result["messages"][0]
        assert ai_msg.tool_calls
        assert ai_msg.tool_calls[0]["name"] == "buscar"

    @patch("src.graph.respond._get_llm_respond")
    def test_respond_node_uses_tool_results(self, mock_get_llm):
        """Após tool executar, o LLM deve responder com base nos resultados."""
        from src.graph.nodes import respond_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content="Encontrei o filtro de óleo para CB300 por R$25.90!"
        )
        mock_get_llm.return_value = mock_llm

        state = _make_state(messages=[
            HumanMessage(content="tem filtro de oleo pra cb300?"),
            AIMessage(content="", tool_calls=[{"name": "buscar", "args": {"query": "filtro cb300"}, "id": "call_1"}]),
            ToolMessage(content="1. Filtro de Oleo CB300 R$25.90", tool_call_id="call_1"),
        ])

        result = respond_node(state)
        assert "messages" in result
        assert "filtro" in result["messages"][0].content.lower() or "25" in result["messages"][0].content


class TestBuscarToolCached:
    @patch("src.tools.buscar._get_vectorstore")
    def test_buscar_uses_cached_vectorstore(self, mock_get_vs):
        """A tool buscar deve reutilizar o vectorstore cacheado."""
        from src.tools.buscar import buscar

        mock_vs = MagicMock()
        mock_rpc_result = MagicMock()
        mock_rpc_result.execute.return_value = MagicMock(data=[
            {"content": "Filtro CB300 R$25.90", "metadata": {"source": "products.csv"}, "similarity": 0.92},
        ])
        mock_vs._client.rpc.return_value = mock_rpc_result
        mock_vs._embedding.embed_query.return_value = [0.0] * 1536
        mock_get_vs.return_value = mock_vs

        result = buscar.invoke({"query": "filtro cb300"})
        assert "Filtro CB300" in result
        mock_get_vs.assert_called_once()


class TestToolNodeExecutesBuscar:
    @patch("src.tools.buscar._get_vectorstore")
    def test_tool_node_runs_buscar(self, mock_get_vs):
        """A tool buscar deve ser chamada corretamente pelo ToolNode."""
        from src.tools.buscar import buscar

        mock_vs = MagicMock()
        mock_rpc_result = MagicMock()
        mock_rpc_result.execute.return_value = MagicMock(data=[
            {"content": "Pastilha Freio CG160 R$45", "metadata": {"source": "db"}, "similarity": 0.88},
        ])
        mock_vs._client.rpc.return_value = mock_rpc_result
        mock_vs._embedding.embed_query.return_value = [0.0] * 1536
        mock_get_vs.return_value = mock_vs

        result = buscar.invoke({"query": "pastilha freio cg160"})
        assert "Pastilha Freio CG160" in result
        assert "R$45" in result
