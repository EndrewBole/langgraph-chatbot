from langchain_core.documents import Document

from src.rag.splitters import split_products, split_documents


def test_split_products_small_chunks():
    docs = [Document(page_content="Filtro de Oleo CB300 R$25.90", metadata={"source": "db"})]
    chunks = split_products(docs)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert len(chunk.page_content) <= 300  # chunk_size 256 + tolerance


def test_split_documents_larger_chunks():
    long_text = "Especificacao tecnica do filtro de oleo. " * 50
    docs = [Document(page_content=long_text, metadata={"source": "manual.pdf"})]
    chunks = split_documents(docs)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk.page_content) <= 600  # chunk_size 512 + tolerance


def test_split_preserves_metadata():
    docs = [Document(
        page_content="Filtro de Oleo CB300",
        metadata={"source": "catalog.pdf", "nome_peca": "Filtro"},
    )]
    chunks = split_products(docs)
    assert chunks[0].metadata["nome_peca"] == "Filtro"
