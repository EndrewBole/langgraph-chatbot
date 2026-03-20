"""Tests for frustration detection (sentiment analysis).

RED phase: these tests should fail with ImportError until the functions
are implemented in src/graph/nodes.py.
"""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


def _make_state(**overrides):
    defaults = {
        "messages": [HumanMessage(content="oi")],
        "session_id": "123",
        "chat_phone": "123",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
        "awaiting_reply": False,
        "follow_up_sent": False,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# FRUSTRATION_SIGNALS constant
# ---------------------------------------------------------------------------

EXPECTED_FRUSTRATION_SIGNALS = [
    "absurdo", "p\u00e9ssimo", "horr\u00edvel", "nunca mais", "bagun\u00e7a",
    "n\u00e3o funciona", "engana\u00e7\u00e3o", "fraude", "rid\u00edculo",
    "vergonha", "lixo", "roubo", "palha\u00e7ada",
]


# ---------------------------------------------------------------------------
# has_frustration_signal tests
# ---------------------------------------------------------------------------

class TestHasFrustrationSignal:
    def test_detects_single_keyword(self):
        """Each keyword in FRUSTRATION_SIGNALS must trigger True."""
        from src.graph.nodes import has_frustration_signal

        for keyword in EXPECTED_FRUSTRATION_SIGNALS:
            assert has_frustration_signal(keyword) is True, (
                f"Expected True for keyword: {keyword!r}"
            )

    def test_case_insensitive(self):
        """Detection must be case-insensitive."""
        from src.graph.nodes import has_frustration_signal

        assert has_frustration_signal("ABSURDO") is True
        assert has_frustration_signal("Horr\u00edvel") is True
        assert has_frustration_signal("P\u00c9SSIMO") is True

    def test_in_sentence(self):
        """Keywords embedded in a sentence must be detected."""
        from src.graph.nodes import has_frustration_signal

        assert has_frustration_signal("isso \u00e9 um absurdo total") is True
        assert has_frustration_signal("esse atendimento \u00e9 uma palha\u00e7ada") is True
        assert has_frustration_signal("n\u00e3o funciona nada aqui") is True

    def test_normal_text_returns_false(self):
        """Normal product queries must NOT trigger frustration."""
        from src.graph.nodes import has_frustration_signal

        assert has_frustration_signal("quero filtro de \u00f3leo para cg 150") is False
        assert has_frustration_signal("tem pastilha de freio?") is False
        assert has_frustration_signal("qual o pre\u00e7o do kit rela\u00e7\u00e3o?") is False

    def test_empty_string_returns_false(self):
        """Empty string must return False."""
        from src.graph.nodes import has_frustration_signal

        assert has_frustration_signal("") is False


# ---------------------------------------------------------------------------
# _get_last_human_message tests
# ---------------------------------------------------------------------------

class TestGetLastHumanMessage:
    def test_returns_text(self):
        """Should extract content from the last HumanMessage."""
        from src.graph.nodes import _get_last_human_message

        state = _make_state(
            messages=[HumanMessage(content="isso \u00e9 um absurdo")]
        )
        assert _get_last_human_message(state) == "isso \u00e9 um absurdo"

    def test_no_human_returns_none(self):
        """Should return None when there are only AIMessages."""
        from src.graph.nodes import _get_last_human_message

        state = _make_state(
            messages=[AIMessage(content="Ol\u00e1!"), AIMessage(content="Como posso ajudar?")]
        )
        assert _get_last_human_message(state) is None

    def test_multiple_returns_last(self):
        """Should return the LAST human message, not the first."""
        from src.graph.nodes import _get_last_human_message

        state = _make_state(
            messages=[
                HumanMessage(content="primeira mensagem"),
                AIMessage(content="resposta"),
                HumanMessage(content="\u00faltima mensagem"),
            ]
        )
        assert _get_last_human_message(state) == "\u00faltima mensagem"


# ---------------------------------------------------------------------------
# classify_node frustration hint injection tests
# ---------------------------------------------------------------------------

FRUSTRATION_HINT_MARKER = "categoria e"

class TestClassifyNodeFrustrationHint:
    @patch("src.graph.classify._get_llm_classify")
    def test_injects_frustration_hint(self, mock_get_llm):
        """When frustration is detected, an extra SystemMessage hint must be
        injected into the messages list passed to the LLM. The hint is a
        separate SystemMessage (not the main SYSTEM_PROMPT) that steers the
        LLM toward Category E."""
        from src.graph.nodes import classify_node, SYSTEM_PROMPT

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Entendo. #HUMANO#")
        mock_get_llm.return_value = mock_llm

        state = _make_state(
            messages=[HumanMessage(content="isso \u00e9 um absurdo, p\u00e9ssimo atendimento")]
        )
        classify_node(state)

        call_args = mock_llm.invoke.call_args[0][0]
        # Filter SystemMessages that are NOT the main SYSTEM_PROMPT
        extra_system_messages = [
            m for m in call_args
            if isinstance(m, SystemMessage) and m.content != SYSTEM_PROMPT
        ]
        assert len(extra_system_messages) >= 1, (
            "Expected an extra SystemMessage (frustration hint) beyond SYSTEM_PROMPT, "
            f"but only found {len(extra_system_messages)} extra SystemMessage(s). "
            f"Total messages: {len(call_args)}"
        )
        # The hint should mention Category E or frustration
        hint_contents = " ".join(m.content.lower() for m in extra_system_messages)
        assert FRUSTRATION_HINT_MARKER in hint_contents or "frustra" in hint_contents, (
            f"Extra SystemMessage does not mention frustration/category E: "
            f"{[m.content[:100] for m in extra_system_messages]}"
        )

    @patch("src.graph.classify._get_llm_classify")
    def test_no_hint_for_normal_text(self, mock_get_llm):
        """Normal text must NOT inject any extra SystemMessage beyond SYSTEM_PROMPT."""
        from src.graph.nodes import classify_node, SYSTEM_PROMPT

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Ol\u00e1!")
        mock_get_llm.return_value = mock_llm

        state = _make_state(
            messages=[HumanMessage(content="quero filtro de \u00f3leo para cg 150")]
        )
        classify_node(state)

        call_args = mock_llm.invoke.call_args[0][0]
        # Filter SystemMessages that are NOT the main SYSTEM_PROMPT
        extra_system_messages = [
            m for m in call_args
            if isinstance(m, SystemMessage) and m.content != SYSTEM_PROMPT
        ]
        assert len(extra_system_messages) == 0, (
            "Expected no extra SystemMessage for normal text, "
            f"but found: {[m.content[:80] for m in extra_system_messages]}"
        )


# ---------------------------------------------------------------------------
# Multi-language support in SYSTEM_PROMPT
# ---------------------------------------------------------------------------

class TestMultiLanguage:
    """Tests for multi-language support in SYSTEM_PROMPT."""

    def test_system_prompt_contains_multilanguage_rule(self):
        """SYSTEM_PROMPT must instruct the LLM to reply in the customer's language."""
        from src.graph.nodes import SYSTEM_PROMPT
        lower = SYSTEM_PROMPT.lower()
        # Identity section: language detection near the top
        assert "idioma" in lower, "SYSTEM_PROMPT must mention 'idioma' for language detection"
        assert "sempre" in lower, "SYSTEM_PROMPT must use 'SEMPRE' to enforce language rule"
        # REGRAS section: strengthened rule
        assert "idioma obrigatório" in lower, (
            "SYSTEM_PROMPT REGRAS must contain 'IDIOMA OBRIGATÓRIO'"
        )
        assert "nunca responda em português se a mensagem foi em outro idioma" in lower
