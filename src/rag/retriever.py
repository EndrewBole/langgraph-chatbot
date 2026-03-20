import logging

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def retrieve(
    query: str,
    vectorstore,
    threshold: float = 0.40,
    top_k: int = 10,
    rerank_top_n: int = 3,
) -> list[Document]:
    # Usa RPC match_documents via client Supabase (evita bug do postgrest)
    query_embedding = vectorstore._embedding.embed_query(query)
    response = vectorstore._client.rpc(
        "match_documents",
        {"query_embedding": query_embedding, "match_count": top_k},
    ).execute()

    results = [
        (
            Document(page_content=row["content"], metadata=row["metadata"]),
            row["similarity"],
        )
        for row in response.data
    ]

    # Log scores para monitoramento e ajuste do threshold
    if results:
        scores = [score for _, score in results]
        logger.info(
            "RAG query='%s' | top_k=%d scores: max=%.3f min=%.3f mean=%.3f",
            query[:80], len(scores), max(scores), min(scores),
            sum(scores) / len(scores),
        )

    # Filtra por threshold de similaridade
    filtered = [(doc, score) for doc, score in results if score >= threshold]

    if not filtered and results:
        best_score = max(score for _, score in results)
        logger.warning(
            "RAG query='%s' | Nenhum resultado acima do threshold %.2f (melhor score: %.3f)",
            query[:80], threshold, best_score,
        )

    # Rerank: retorna os top N mais relevantes
    filtered.sort(key=lambda x: x[1], reverse=True)
    top_results = filtered[:rerank_top_n]

    return [doc for doc, _ in top_results]
