"""Testes da tool buscar com Supabase."""
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document


@patch("src.tools.buscar._get_vectorstore")
def test_buscar_returns_string(mock_get_vs):
    from src.tools.buscar import buscar

    mock_vs = MagicMock()
    mock_rpc_result = MagicMock()
    mock_rpc_result.execute.return_value = MagicMock(data=[
        {"content": "Filtro CB300", "metadata": {"source": "test.csv"}, "similarity": 0.9},
    ])
    mock_vs._client.rpc.return_value = mock_rpc_result
    mock_vs._embedding.embed_query.return_value = [0.0] * 1536
    mock_get_vs.return_value = mock_vs

    result = buscar.invoke({"query": "filtro de oleo cb300"})
    assert isinstance(result, str)
    assert "Filtro CB300" in result


@patch("src.tools.buscar._get_vectorstore")
def test_buscar_without_connection_returns_warning(mock_get_vs):
    """Se o vectorstore falhar, deve retornar aviso."""
    from src.tools.buscar import buscar

    mock_get_vs.side_effect = Exception("connection refused")

    result = buscar.invoke({"query": "filtro"})
    assert "indexado" in result.lower() or "indisponível" in result.lower() or "erro" in result.lower()


def test_buscar_has_docstring():
    from src.tools.buscar import buscar
    assert buscar.description
    assert "peça" in buscar.description.lower() or "catálogo" in buscar.description.lower()


def test_get_vectorstore_lazy_init():
    """_get_vectorstore carrega apenas uma vez (lazy + cached)."""
    from src.tools.buscar import _get_vectorstore
    import src.tools.buscar as _buscar_module
    import importlib
    import sys

    # Get the actual module (not the tool object)
    buscar_mod = sys.modules["src.tools.buscar"]
    buscar_mod._vectorstore = None  # reset

    mock_vs = MagicMock()
    with patch("src.rag.indexer.load_vectorstore", return_value=mock_vs) as mock_load:
        vs1 = _get_vectorstore()
        vs2 = _get_vectorstore()  # deve usar cache

        assert vs1 is mock_vs
        assert vs2 is mock_vs
        assert mock_load.call_count == 1

    buscar_mod._vectorstore = None  # cleanup


@patch("src.tools.buscar._get_vectorstore")
@patch("src.tools.buscar.retrieve")
def test_buscar_limit_param_passed_to_retrieve(mock_retrieve, mock_get_vs):
    """Parâmetro limit é repassado para retrieve como rerank_top_n."""
    from src.tools.buscar import buscar

    mock_get_vs.return_value = MagicMock()
    mock_retrieve.return_value = [Document(page_content="Peca X", metadata={})]

    buscar.invoke({"query": "biz 125", "limit": 10})
    _, kwargs = mock_retrieve.call_args
    assert kwargs["rerank_top_n"] == 10


@patch("src.tools.buscar._get_vectorstore")
@patch("src.tools.buscar.retrieve")
def test_buscar_default_limit_is_3(mock_retrieve, mock_get_vs):
    """Sem limit, rerank_top_n padrão é 3."""
    from src.tools.buscar import buscar

    mock_get_vs.return_value = MagicMock()
    mock_retrieve.return_value = [Document(page_content="Peca X", metadata={})]

    buscar.invoke({"query": "filtro cb300"})
    _, kwargs = mock_retrieve.call_args
    assert kwargs["rerank_top_n"] == 3


@patch("src.tools.buscar._get_vectorstore")
@patch("src.tools.buscar.retrieve")
def test_buscar_empty_results_returns_not_found(mock_retrieve, mock_get_vs):
    """Quando retrieve retorna lista vazia, buscar informa que nao encontrou."""
    from src.tools.buscar import buscar

    mock_get_vs.return_value = MagicMock()
    mock_retrieve.return_value = []

    result = buscar.invoke({"query": "peca inexistente xyz"})
    assert "nenhuma" in result.lower()
