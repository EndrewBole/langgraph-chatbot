"""Facade: re-exports all node functions and constants for backward compatibility.

All existing `from src.graph.nodes import X` continue to work.
For @patch targets, use the canonical module (e.g., src.graph.classify, src.graph.handoff).
"""

from langgraph.prebuilt import ToolNode

from src.graph.classify import _detect_language_hint, classify_node  # noqa: F401
from src.graph.handoff import (  # noqa: F401
    HANDOFF_MESSAGE,
    HANDOFF_THRESHOLD,
    HUMANO_TAG,
    human_handoff_node,
)
from src.graph.llm import (  # noqa: F401
    _get_llm_classify,
    _get_llm_respond,
    _llm_classify,
    _llm_lock,
    _llm_respond,
    _session_messages,
)
from src.graph.prompt import SYSTEM_PROMPT  # noqa: F401
from src.graph.respond import respond_node  # noqa: F401
from src.graph.send import (  # noqa: F401
    _BTN_PATTERN,
    _PRODUCT_BLOCK_PATTERN,
    _parse_product_blocks,
    send_response_node,
)
from src.graph.sentiment import (  # noqa: F401
    FRUSTRATION_SIGNALS,
    _get_last_human_message,
    has_frustration_signal,
)
from src.tools import buscar  # noqa: F401

tool_node = ToolNode(tools=[buscar])
