import logging

from langgraph.checkpoint.memory import MemorySaver

from src.config import settings

logger = logging.getLogger(__name__)


def get_checkpointer(use_postgres: bool = False):
    """Return a LangGraph checkpointer (MemorySaver or PostgresSaver)."""
    if use_postgres:
        from psycopg import Connection

        logger.info("Initializing PostgresSaver checkpointer")
        conn = Connection.connect(settings.DATABASE_URL, autocommit=True)
        from langgraph.checkpoint.postgres import PostgresSaver

        saver = PostgresSaver(conn)
        saver.setup()
        return saver

    logger.info("Using in-memory MemorySaver checkpointer")
    return MemorySaver()
