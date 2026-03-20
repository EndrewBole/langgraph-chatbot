"""Indexador vetorial com Supabase pgvector."""

import hashlib
import logging

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client

from src.config import settings

logger = logging.getLogger(__name__)


def compute_doc_hash(doc: Document) -> str:
    """Gera hash MD5 do conteúdo para deduplicação."""
    return hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()


def get_embeddings():
    """Retorna instância de embeddings OpenAI."""
    return OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)


def get_supabase_client():
    """Cria client Supabase autenticado."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def fetch_existing_hashes(client) -> set[str]:
    """Consulta hashes já indexados no Supabase para deduplicação cross-execução."""
    try:
        response = client.table("documents").select("metadata->>content_hash").execute()
        return {row["content_hash"] for row in response.data if row.get("content_hash")}
    except Exception:
        logger.warning("Não foi possível consultar hashes existentes, continuando sem dedup cross-execução")
        return set()


def create_vectorstore(
    docs: list[Document],
) -> SupabaseVectorStore | None:
    """Cria vectorstore no Supabase com deduplicação por hash (inclusive cross-execução)."""
    client = get_supabase_client()

    # Busca hashes já indexados no Supabase
    existing_hashes = fetch_existing_hashes(client)

    seen_hashes = set(existing_hashes)
    unique_docs = []
    for doc in docs:
        h = compute_doc_hash(doc)
        if h not in seen_hashes:
            seen_hashes.add(h)
            doc.metadata["content_hash"] = h
            unique_docs.append(doc)

    skipped = len(docs) - len(unique_docs)
    if skipped:
        logger.info("Pulando %d docs já indexados", skipped)

    if not unique_docs:
        logger.info("Nenhum documento novo para indexar")
        return None

    logger.info("Indexando %d docs únicos (de %d total)", len(unique_docs), len(docs))

    embeddings = get_embeddings()

    vectorstore = SupabaseVectorStore.from_documents(
        documents=unique_docs,
        embedding=embeddings,
        client=client,
        table_name="documents",
        query_name="match_documents",
    )
    return vectorstore


def load_vectorstore() -> SupabaseVectorStore:
    """Carrega vectorstore existente do Supabase."""
    client = get_supabase_client()
    embeddings = get_embeddings()
    return SupabaseVectorStore(
        client=client,
        embedding=embeddings,
        table_name="documents",
        query_name="match_documents",
    )
