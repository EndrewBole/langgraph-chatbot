"""Testes do indexer com Supabase pgvector."""
from unittest.mock import patch, MagicMock, call
from langchain_core.documents import Document


def test_indexer_creates_vectorstore():
    """create_vectorstore deve criar SupabaseVectorStore com docs unicos."""
    from src.rag.indexer import create_vectorstore

    docs = [
        Document(page_content="Filtro de Oleo CB300", metadata={"source": "test"}),
        Document(page_content="Pastilha de Freio CG160", metadata={"source": "test"}),
    ]

    mock_client = MagicMock()
    mock_embeddings = MagicMock()

    # Simula nenhum hash existente no Supabase
    mock_response = MagicMock()
    mock_response.data = []
    mock_client.table.return_value.select.return_value.execute.return_value = (
        mock_response
    )

    with patch("src.rag.indexer.get_supabase_client", return_value=mock_client), \
         patch("src.rag.indexer.get_embeddings", return_value=mock_embeddings), \
         patch("src.rag.indexer.SupabaseVectorStore.from_documents") as mock_from_docs:

        mock_vs = MagicMock()
        mock_from_docs.return_value = mock_vs

        result = create_vectorstore(docs)
        assert result is mock_vs
        mock_from_docs.assert_called_once()
        # Verifica que passou 2 docs unicos
        call_args = mock_from_docs.call_args
        assert len(call_args.kwargs["documents"]) == 2


def test_indexer_deduplicates_by_hash():
    from src.rag.indexer import compute_doc_hash

    doc1 = Document(page_content="Filtro de Oleo CB300", metadata={})
    doc2 = Document(page_content="Filtro de Oleo CB300", metadata={})
    doc3 = Document(page_content="Pastilha de Freio", metadata={})

    assert compute_doc_hash(doc1) == compute_doc_hash(doc2)
    assert compute_doc_hash(doc1) != compute_doc_hash(doc3)


def test_load_vectorstore_returns_supabase_instance():
    """load_vectorstore deve retornar SupabaseVectorStore."""
    from src.rag.indexer import load_vectorstore

    mock_client = MagicMock()
    mock_embeddings = MagicMock()
    mock_vs = MagicMock()

    with patch("src.rag.indexer.get_supabase_client", return_value=mock_client), \
         patch("src.rag.indexer.get_embeddings", return_value=mock_embeddings), \
         patch("src.rag.indexer.SupabaseVectorStore") as MockVS:

        MockVS.return_value = mock_vs
        result = load_vectorstore()
        assert result is mock_vs
        MockVS.assert_called_once_with(
            client=mock_client,
            embedding=mock_embeddings,
            table_name="documents",
            query_name="match_documents",
        )


# --- Novos testes para deduplicacao cross-execucao ---


def test_fetch_existing_hashes():
    """fetch_existing_hashes deve retornar set de hashes do Supabase."""
    from src.rag.indexer import fetch_existing_hashes

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [
        {"content_hash": "abc123"},
        {"content_hash": "def456"},
    ]
    mock_client.table.return_value.select.return_value.execute.return_value = (
        mock_response
    )

    result = fetch_existing_hashes(mock_client)
    assert result == {"abc123", "def456"}
    mock_client.table.assert_called_with("documents")


def test_fetch_existing_hashes_handles_error():
    """fetch_existing_hashes deve retornar set vazio se query falhar."""
    from src.rag.indexer import fetch_existing_hashes

    mock_client = MagicMock()
    mock_client.table.side_effect = Exception("connection error")

    result = fetch_existing_hashes(mock_client)
    assert result == set()


def test_create_vectorstore_skips_existing_docs():
    """create_vectorstore deve pular docs com hash ja no Supabase."""
    from src.rag.indexer import create_vectorstore, compute_doc_hash

    existing_doc = Document(
        page_content="Filtro de Oleo CB300", metadata={"source": "test"}
    )
    new_doc = Document(
        page_content="Pastilha de Freio CG160", metadata={"source": "test"}
    )
    existing_hash = compute_doc_hash(existing_doc)

    mock_client = MagicMock()
    mock_embeddings = MagicMock()

    # Simula que existing_doc ja esta no Supabase
    mock_response = MagicMock()
    mock_response.data = [{"content_hash": existing_hash}]
    mock_client.table.return_value.select.return_value.execute.return_value = (
        mock_response
    )

    with patch("src.rag.indexer.get_supabase_client", return_value=mock_client), \
         patch("src.rag.indexer.get_embeddings", return_value=mock_embeddings), \
         patch("src.rag.indexer.SupabaseVectorStore.from_documents") as mock_from_docs:

        mock_vs = MagicMock()
        mock_from_docs.return_value = mock_vs

        result = create_vectorstore([existing_doc, new_doc])
        assert result is mock_vs
        call_args = mock_from_docs.call_args
        docs_passed = call_args.kwargs["documents"]
        assert len(docs_passed) == 1
        assert docs_passed[0].page_content == "Pastilha de Freio CG160"


def test_create_vectorstore_returns_none_when_all_exist():
    """create_vectorstore deve retornar None se todos os docs ja existem."""
    from src.rag.indexer import create_vectorstore, compute_doc_hash

    doc = Document(
        page_content="Filtro de Oleo CB300", metadata={"source": "test"}
    )
    doc_hash = compute_doc_hash(doc)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{"content_hash": doc_hash}]
    mock_client.table.return_value.select.return_value.execute.return_value = (
        mock_response
    )

    with patch("src.rag.indexer.get_supabase_client", return_value=mock_client), \
         patch("src.rag.indexer.get_embeddings", return_value=MagicMock()):

        result = create_vectorstore([doc])
        assert result is None
