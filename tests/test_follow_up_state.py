"""Tests for proactive follow-up state tracking (awaiting_reply, follow_up_sent)."""

from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage


def _make_state(**overrides):
    defaults = {
        "messages": [HumanMessage(content="oi")],
        "session_id": "123",
        "chat_phone": "5511999999999",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
        "awaiting_reply": False,
        "follow_up_sent": False,
    }
    defaults.update(overrides)
    return defaults


class TestSendResponseNodeFollowUp:
    """send_response_node sets awaiting_reply based on product content."""

    @patch("src.graph.send.send_message")
    def test_sets_awaiting_reply_true_when_products_present(self, mock_send):
        from src.graph.nodes import send_response_node

        product_content = (
            "*1. Filtro de Oleo*\n\n"
            "- 💰 Preco: R$ 25,90\n"
            "- Marca: Vedamotors\n"
        )
        state = _make_state(
            messages=[
                HumanMessage(content="filtro cb300"),
                AIMessage(content=product_content),
            ],
        )
        result = send_response_node(state)
        assert result.get("awaiting_reply") is True

    @patch("src.graph.send.send_message")
    def test_sets_awaiting_reply_false_when_no_products(self, mock_send):
        from src.graph.nodes import send_response_node

        state = _make_state(
            messages=[
                HumanMessage(content="oi"),
                AIMessage(content="Ola! Sou a Lis, como posso ajudar?"),
            ],
        )
        result = send_response_node(state)
        assert result.get("awaiting_reply") is False

    @patch("src.graph.send.send_message")
    def test_detects_price_pattern(self, mock_send):
        from src.graph.nodes import send_response_node

        state = _make_state(
            messages=[
                HumanMessage(content="vela biz"),
                AIMessage(content="Encontrei a vela por R$ 12,50."),
            ],
        )
        result = send_response_node(state)
        assert result.get("awaiting_reply") is True

    @patch("src.graph.send.send_message")
    def test_detects_numbered_product_pattern(self, mock_send):
        from src.graph.nodes import send_response_node

        state = _make_state(
            messages=[
                HumanMessage(content="pastilha"),
                AIMessage(content="*1. Pastilha de Freio*\nDescricao aqui"),
            ],
        )
        result = send_response_node(state)
        assert result.get("awaiting_reply") is True


class TestClassifyNodeFollowUp:
    """classify_node resets awaiting_reply when customer sends a new message."""

    @patch("src.graph.classify._get_llm_classify")
    def test_resets_awaiting_reply(self, mock_get_llm):
        from src.graph.nodes import classify_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Resposta")
        mock_get_llm.return_value = mock_llm

        state = _make_state(awaiting_reply=True)
        result = classify_node(state)
        assert result.get("awaiting_reply") is False

    @patch("src.graph.classify._get_llm_classify")
    def test_does_not_reset_follow_up_sent(self, mock_get_llm):
        from src.graph.nodes import classify_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Resposta")
        mock_get_llm.return_value = mock_llm

        state = _make_state(follow_up_sent=True, awaiting_reply=True)
        result = classify_node(state)
        # follow_up_sent should NOT be in the returned dict (not reset per message)
        assert "follow_up_sent" not in result


class TestAgentStateFields:
    """AgentState has the new follow-up fields."""

    def test_state_has_awaiting_reply_field(self):
        from src.state import AgentState
        annotations = AgentState.__annotations__
        assert "awaiting_reply" in annotations

    def test_state_has_follow_up_sent_field(self):
        from src.state import AgentState
        annotations = AgentState.__annotations__
        assert "follow_up_sent" in annotations
