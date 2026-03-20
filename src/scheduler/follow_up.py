"""Scheduler de follow-up proativo — envia mensagem quando cliente nao responde."""

import asyncio
import logging
import time

from src.config import settings
from src.graph import graph
from src.integrations.evolution import send_message

logger = logging.getLogger(__name__)


async def check_and_send_follow_ups() -> int:
    """Varre conversas ativas e envia follow-up quando necessario.

    Returns number of follow-ups sent.
    """
    if not settings.FOLLOW_UP_ENABLED:
        return 0

    sent_count = 0
    threshold = settings.FOLLOW_UP_HOURS * 3600
    now = time.time()

    try:
        checkpointer = graph.checkpointer
        if not checkpointer:
            logger.debug("No checkpointer available for follow-up scan")
            return 0

        for checkpoint_tuple in checkpointer.list(None):
            config = checkpoint_tuple.config
            thread_id = config.get("configurable", {}).get("thread_id", "")
            if not thread_id:
                continue

            try:
                snapshot = graph.get_state(config)
                values = snapshot.values

                awaiting_reply = values.get("awaiting_reply", False)
                follow_up_sent = values.get("follow_up_sent", False)
                em_atendimento = values.get("em_atendimento_humano", False)
                last_activity = values.get("last_activity", 0)
                chat_phone = values.get("chat_phone", "")

                if not awaiting_reply or follow_up_sent or em_atendimento:
                    continue
                if not last_activity or not chat_phone:
                    continue
                if (now - last_activity) < threshold:
                    continue

                success = send_message(chat_phone, settings.FOLLOW_UP_MESSAGE)
                if success:
                    graph.update_state(
                        config,
                        {"follow_up_sent": True, "awaiting_reply": False},
                    )
                    sent_count += 1
                    logger.info("Follow-up enviado para %s", chat_phone)

            except Exception:
                logger.debug(
                    "Erro ao processar follow-up para thread %s", thread_id
                )
                continue

    except Exception:
        logger.exception("Erro ao varrer conversas para follow-up")

    return sent_count


async def follow_up_loop() -> None:
    """Loop infinito que executa check_and_send_follow_ups periodicamente."""
    interval = settings.FOLLOW_UP_CHECK_INTERVAL_MINUTES * 60
    logger.info(
        "Follow-up scheduler iniciado (intervalo=%dm, threshold=%dh)",
        settings.FOLLOW_UP_CHECK_INTERVAL_MINUTES,
        settings.FOLLOW_UP_HOURS,
    )
    while True:
        await asyncio.sleep(interval)
        try:
            count = await check_and_send_follow_ups()
            if count:
                logger.info("Follow-up: %d mensagens enviadas", count)
        except Exception:
            logger.exception("Erro no follow-up loop")
