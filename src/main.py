"""Aplicação FastAPI — Temporalis AI Chatbot."""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from langchain_core.messages import HumanMessage

from src.api.routes.chatwoot import router as chatwoot_router
from src.api.routes.health import router as health_router
from src.api.routes.whatsapp import router as whatsapp_router
from src.config import settings
from src.graph import graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia recursos compartilhados (startup/shutdown)."""
    app.state.http_client = httpx.AsyncClient()
    logger.info("httpx.AsyncClient iniciado")

    follow_up_task: asyncio.Task | None = None
    if settings.FOLLOW_UP_ENABLED:
        from src.scheduler.follow_up import follow_up_loop

        follow_up_task = asyncio.create_task(follow_up_loop())
        logger.info("Follow-up scheduler ativado")

    catalog_reindex_task: asyncio.Task | None = None
    if settings.CATALOG_REINDEX_ENABLED:
        from src.scheduler.catalog_reindex import catalog_reindex_loop

        catalog_reindex_task = asyncio.create_task(catalog_reindex_loop())
        logger.info("Catalog reindex scheduler ativado")

    yield

    if catalog_reindex_task is not None:
        catalog_reindex_task.cancel()
        try:
            await catalog_reindex_task
        except asyncio.CancelledError:
            pass
        logger.info("Catalog reindex scheduler encerrado")

    if follow_up_task is not None:
        follow_up_task.cancel()
        try:
            await follow_up_task
        except asyncio.CancelledError:
            pass
        logger.info("Follow-up scheduler encerrado")

    await app.state.http_client.aclose()
    logger.info("httpx.AsyncClient encerrado")


app = FastAPI(title="Temporalis AI Chatbot", lifespan=lifespan)
app.include_router(chatwoot_router)
app.include_router(health_router)
app.include_router(whatsapp_router)


def chat(user_input: str) -> str:
    """Modo CLI interativo."""
    config = {"configurable": {"thread_id": "local"}}
    result = graph.invoke(
        {
            "messages": [HumanMessage(content=user_input)],
            "session_id": "local",
            "chat_phone": "local",
        },
        config=config,
    )
    return result["messages"][-1].content


if __name__ == "__main__":
    import sys

    if "--serve" in sys.argv:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() in ("quit", "exit"):
                    break
                response = chat(user_input)
                print(f"Bot: {response}")
            except (KeyboardInterrupt, EOFError):
                break
