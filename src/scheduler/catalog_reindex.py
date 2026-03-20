"""Scheduled catalog reindex — re-runs RAG ingestion pipeline periodically."""

import asyncio
import logging

from src.config import settings

logger = logging.getLogger(__name__)


async def run_reindex() -> int:
    """Run the RAG ingestion pipeline. Returns count of new documents indexed."""
    if not settings.CATALOG_REINDEX_ENABLED:
        logger.debug("Catalog reindex disabled")
        return 0

    try:
        # Lazy imports to avoid loading heavy modules (embeddings, vectorstore) at startup
        from src.rag.loaders import load_all_from_dir
        from src.rag.splitters import split_products, split_documents
        from src.rag.indexer import create_vectorstore

        data_dir = settings.DATA_DIR
        logger.info("Starting catalog reindex from %s", data_dir)

        # Run sync loader in thread to not block event loop
        docs = await asyncio.to_thread(load_all_from_dir, data_dir)

        if not docs:
            logger.info("No documents found in %s, skipping reindex", data_dir)
            return 0

        # Split into products vs documents based on file_type metadata
        product_docs = [d for d in docs if d.metadata.get("file_type") in ("csv", "xlsx")]
        other_docs = [d for d in docs if d.metadata.get("file_type") not in ("csv", "xlsx")]

        chunks = []
        if product_docs:
            chunks.extend(split_products(product_docs))
        if other_docs:
            chunks.extend(split_documents(other_docs))

        if not chunks:
            logger.info("No chunks after splitting, skipping reindex")
            return 0

        # create_vectorstore handles dedup internally (hash-based)
        count = len(chunks)
        result = await asyncio.to_thread(create_vectorstore, chunks)

        if result is None:
            logger.info("All documents already indexed, nothing new")
            return 0

        logger.info("Catalog reindex complete: %d new documents indexed", count)
        return count

    except Exception:
        logger.exception("Catalog reindex failed")
        return 0


async def catalog_reindex_loop() -> None:
    """Background loop that periodically re-indexes the catalog."""
    interval = settings.CATALOG_REINDEX_INTERVAL_HOURS * 3600
    logger.info(
        "Catalog reindex scheduler started (interval=%dh, enabled=%s)",
        settings.CATALOG_REINDEX_INTERVAL_HOURS,
        settings.CATALOG_REINDEX_ENABLED,
    )
    while True:
        await asyncio.sleep(interval)
        await run_reindex()
