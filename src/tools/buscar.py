"""Tool de busca RAG no catálogo Temporalis AI."""

import logging
import os

from langchain_core.tools import tool
from supabase import create_client

from src.config import settings
from src.rag.retriever import retrieve

logger = logging.getLogger(__name__)

_vectorstore = None


def _get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        from src.rag.indexer import load_vectorstore
        _vectorstore = load_vectorstore()
    return _vectorstore


def _log_search(query: str, result_count: int, session_id: str = "") -> None:
    """Log search query to Supabase for analytics (fire-and-forget)."""
    if not settings.ANALYTICS_ENABLED:
        return
    try:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        client.table("search_log").insert({
            "query": query,
            "result_count": result_count,
            "session_id": session_id,
        }).execute()
    except Exception:
        logger.warning("Failed to log search analytics", exc_info=True)


@tool
def buscar(query: str, limit: int = 3) -> str:
    """Busca peças e produtos no catálogo da Temporalis AI.
    - query: termos de busca (nome da peça, modelo da moto, etc.)
    - limit: máximo de resultados (padrão 3; use 10 para listar todas as peças de um modelo)
    Use esta ferramenta APENAS para perguntas sobre peças de moto (Categoria A)."""
    try:
        vectorstore = _get_vectorstore()
    except Exception as e:
        logger.error("Erro ao conectar ao vectorstore: %s", e)
        return "Catálogo indisponível no momento. Tente novamente mais tarde."

    results = retrieve(
        query,
        vectorstore=vectorstore,
        threshold=settings.RAG_SIMILARITY_THRESHOLD,
        top_k=max(settings.RAG_TOP_K, limit * 2),
        rerank_top_n=limit,
    )

    _log_search(query, len(results))

    if not results:
        return "Nenhuma peça encontrada para essa busca. Tente com outros termos."

    output_lines = []
    for i, doc in enumerate(results, 1):
        meta = doc.metadata
        line = f"{i}. {doc.page_content}"
        if meta.get("source"):
            line += f" (fonte: {os.path.basename(meta['source'])})"
        output_lines.append(line)

    return "\n".join(output_lines)
