"""Send response node — sends final response via Evolution API or Chatwoot."""

import logging
import re
import time

from langchain_core.messages import AIMessage

from src.integrations.chatwoot import send_chatwoot_message
from src.integrations.evolution import send_link_button, send_message

logger = logging.getLogger(__name__)

_BTN_PATTERN = re.compile(r"\[BTN:(https?://[^\]\s]+)\]")
_PRODUCT_BLOCK_PATTERN = re.compile(r"(\*\d+\..+?)\[BTN:(https?://[^\]\s]+)\]", re.DOTALL)


def _parse_product_blocks(content: str) -> list[tuple[str, str | None]]:
    """Divide a resposta em blocos (texto, url_compra|None) para envio individual."""
    blocks: list[tuple[str, str | None]] = []
    last_end = 0
    for match in _PRODUCT_BLOCK_PATTERN.finditer(content):
        pre = content[last_end:match.start()].strip()
        if pre:
            blocks.append((pre, None))
        blocks.append((match.group(1).strip(), match.group(2)))
        last_end = match.end()
    remaining = content[last_end:].strip()
    if remaining:
        blocks.append((remaining, None))
    if not blocks:
        blocks.append((content.strip(), None))
    return blocks


def _send_block(state: dict, text: str, url: str | None) -> None:
    """Envia um bloco de texto+url pelo canal correto (Evolution ou Chatwoot)."""
    channel = state.get("channel", "whatsapp")
    phone = state["chat_phone"]
    logger.info("Resposta para %s: %s", phone, text[:100])

    if channel == "instagram":
        conv_id = state.get("chatwoot_conversation_id")
        if conv_id:
            if url:
                send_chatwoot_message(conv_id, f"{text}\n\n🛒 {url}")
            else:
                send_chatwoot_message(conv_id, text)
    else:
        if url:
            send_link_button(phone, url, message=text)
        else:
            send_message(phone, text)


def send_response_node(state: dict) -> dict:
    """Envia a resposta final via Evolution API ou Chatwoot (channel-aware)."""
    last_message = state["messages"][-1]
    has_products = False
    if isinstance(last_message, AIMessage) and last_message.content:
        has_products = bool(
            re.search(r"R\$|^\*\d+\.", last_message.content, re.MULTILINE)
        )
        for text, url in _parse_product_blocks(last_message.content):
            if text or url:
                _send_block(state, text, url)
    result: dict = {"awaiting_reply": has_products}
    if has_products:
        result["last_activity"] = time.time()
        result["follow_up_sent"] = False
    return result
