from unittest.mock import MagicMock, patch
from langchain_core.documents import Document


def _mock_vectorstore_rpc(mock_vs, rpc_data: list[dict]):
    """Configure a mock vectorstore to return rpc_data via the RPC chain."""
    mock_vs._embedding.embed_query.return_value = [0.0] * 1536
    mock_rpc_result = MagicMock()
    mock_rpc_result.execute.return_value = MagicMock(data=rpc_data)
    mock_vs._client.rpc.return_value = mock_rpc_result


def test_retrieve_filters_by_threshold():
    from src.rag.retriever import retrieve

    mock_vs = MagicMock()
    _mock_vectorstore_rpc(mock_vs, [
        {"content": "Filtro CB300", "metadata": {}, "similarity": 0.90},
        {"content": "Pastilha CG160", "metadata": {}, "similarity": 0.80},
        {"content": "Irrelevante", "metadata": {}, "similarity": 0.50},
    ])

    results = retrieve("filtro cb300", vectorstore=mock_vs, threshold=0.75, top_k=10, rerank_top_n=3)
    assert len(results) == 2
    assert all("Irrelevante" not in r.page_content for r in results)


def test_retrieve_limits_rerank_top_n():
    from src.rag.retriever import retrieve

    mock_vs = MagicMock()
    _mock_vectorstore_rpc(mock_vs, [
        {"content": f"Produto {i}", "metadata": {}, "similarity": 0.90 - i * 0.01}
        for i in range(10)
    ])

    results = retrieve("produto", vectorstore=mock_vs, threshold=0.0, top_k=10, rerank_top_n=3)
    assert len(results) == 3


def test_retrieve_empty_returns_empty():
    from src.rag.retriever import retrieve

    mock_vs = MagicMock()
    _mock_vectorstore_rpc(mock_vs, [])

    results = retrieve("nada", vectorstore=mock_vs, threshold=0.75, top_k=10, rerank_top_n=3)
    assert results == []
