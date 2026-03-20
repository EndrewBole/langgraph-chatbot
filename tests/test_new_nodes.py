from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage


def _make_state(**overrides):
    defaults = {
        "messages": [HumanMessage(content="oi")],
        "session_id": "123",
        "chat_phone": "123",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
    }
    defaults.update(overrides)
    return defaults


class TestClassifyNode:
    @patch("src.graph.classify._get_llm_classify")
    def test_returns_messages(self, mock_get_llm):
        from src.graph.nodes import classify_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Olá!")
        mock_get_llm.return_value = mock_llm

        result = classify_node(_make_state())
        assert "messages" in result

    @patch("src.graph.classify._get_llm_classify")
    def test_system_prompt_included(self, mock_get_llm):
        from src.graph.nodes import classify_node

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="resposta")
        mock_get_llm.return_value = mock_llm

        classify_node(_make_state())
        call_args = mock_llm.invoke.call_args[0][0]
        assert any("Temporalis" in str(m) for m in call_args)


class TestHumanHandoffNode:
    def test_detects_humano_tag(self):
        from src.graph.nodes import human_handoff_node

        state = _make_state(
            messages=[HumanMessage(content="humano"), AIMessage(content="Entendo. #HUMANO#")],
        )
        result = human_handoff_node(state)
        assert result["tentativas_categoria_e"] == 1
        assert result["requer_humano"] is True

    def test_triggers_handoff_at_3(self):
        from src.graph.nodes import human_handoff_node

        state = _make_state(
            messages=[HumanMessage(content="humano"), AIMessage(content="Ok. #HUMANO#")],
            tentativas_categoria_e=2,
        )
        result = human_handoff_node(state)
        assert result["tentativas_categoria_e"] == 3
        assert result["em_atendimento_humano"] is True

    def test_no_tag_passthrough(self):
        from src.graph.nodes import human_handoff_node

        state = _make_state(
            messages=[HumanMessage(content="oi"), AIMessage(content="Olá!")],
        )
        result = human_handoff_node(state)
        assert result["tentativas_categoria_e"] == 0
        assert result["requer_humano"] is False

    def test_strips_humano_tag(self):
        from src.graph.nodes import human_handoff_node

        state = _make_state(
            messages=[HumanMessage(content="humano"), AIMessage(content="Entendo. #HUMANO#")],
        )
        result = human_handoff_node(state)
        last_msg = result["messages"][-1]
        assert "#HUMANO#" not in last_msg.content


class TestParseProductBlocks:
    def test_no_btn_returns_single_block(self):
        from src.graph.nodes import _parse_product_blocks
        blocks = _parse_product_blocks("Olá! Como posso ajudar?")
        assert blocks == [("Olá! Como posso ajudar?", None)]

    def test_one_product_with_btn(self):
        from src.graph.nodes import _parse_product_blocks
        content = "*1. Filtro*\n- Preço: R$ 89,90\n[BTN:https://ml.com/filtro]"
        blocks = _parse_product_blocks(content)
        assert len(blocks) == 1
        assert blocks[0][1] == "https://ml.com/filtro"
        assert "[BTN:" not in blocks[0][0]

    def test_two_products_parsed_separately(self):
        from src.graph.nodes import _parse_product_blocks
        content = "*1. A*\n- Preço: R$ 10\n[BTN:https://a.com]\n\n*2. B*\n- Preço: R$ 20\n[BTN:https://b.com]"
        blocks = _parse_product_blocks(content)
        assert len(blocks) == 2
        assert blocks[0][1] == "https://a.com"
        assert blocks[1][1] == "https://b.com"

    def test_closing_text_after_products(self):
        from src.graph.nodes import _parse_product_blocks
        content = "*1. A*\n- Preço: R$ 10\n[BTN:https://a.com]\n\nQual peça você precisa? 🔧"
        blocks = _parse_product_blocks(content)
        assert len(blocks) == 2
        assert blocks[0][1] == "https://a.com"
        assert blocks[1] == ("Qual peça você precisa? 🔧", None)

    def test_no_products_no_btn_returns_full_text(self):
        from src.graph.nodes import _parse_product_blocks
        text = "Endereço: Rua P R A, 313"
        blocks = _parse_product_blocks(text)
        assert blocks == [(text, None)]


class TestSendResponseNode:
    @patch("src.graph.send.send_link_button", return_value=True)
    @patch("src.graph.send.send_message", return_value=True)
    def test_plain_text_calls_send_message(self, mock_send, mock_btn):
        from src.graph.nodes import send_response_node

        state = _make_state(
            messages=[HumanMessage(content="oi"), AIMessage(content="Olá!")],
            chat_phone="5511999999999",
        )
        send_response_node(state)
        mock_send.assert_called_once_with("5511999999999", "Olá!")
        mock_btn.assert_not_called()

    @patch("src.graph.send.send_link_button", return_value=True)
    @patch("src.graph.send.send_message", return_value=True)
    def test_product_with_link_sends_single_message(self, mock_send, mock_btn):
        from src.graph.nodes import send_response_node

        content = "*1. Filtro*\n\n- Preço: R$ 89,90\n[BTN:https://ml.com/filtro]\n\nPosso ajudar?"
        state = _make_state(
            messages=[HumanMessage(content="filtro"), AIMessage(content=content)],
            chat_phone="5511999999999",
        )
        send_response_node(state)
        assert mock_btn.call_count == 1
        assert mock_send.call_count == 1   # apenas o fechamento
        # produto vai no message= do send_link_button
        _, kwargs = mock_btn.call_args
        assert "Filtro" in kwargs["message"]

    @patch("src.graph.send.send_link_button", return_value=True)
    @patch("src.graph.send.send_message", return_value=True)
    def test_two_products_two_link_cards_one_closing(self, mock_send, mock_btn):
        from src.graph.nodes import send_response_node

        content = "*1. A*\n\n- Preço: R$ 10\n[BTN:https://a.com]\n\n*2. B*\n\n- Preço: R$ 20\n[BTN:https://b.com]\n\nPosso ajudar?"
        state = _make_state(
            messages=[HumanMessage(content="biz"), AIMessage(content=content)],
            chat_phone="5511999999999",
        )
        send_response_node(state)
        assert mock_btn.call_count == 2    # 2 produtos como cards
        assert mock_send.call_count == 1   # só o fechamento como texto


def test_get_llm_classify_lazy_init():
    """_get_llm_classify inicializa ChatOpenAI apenas uma vez."""
    import src.graph.llm as llm_mod

    llm_mod._llm_classify = None  # reset

    with patch("src.graph.llm.ChatOpenAI") as mock_chat:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_chat.return_value = mock_llm

        result1 = llm_mod._get_llm_classify()
        result2 = llm_mod._get_llm_classify()  # cached

        assert result1 is result2
        assert mock_chat.call_count == 1

    llm_mod._llm_classify = None  # cleanup


def test_get_llm_respond_lazy_init():
    """_get_llm_respond inicializa ChatOpenAI apenas uma vez."""
    import src.graph.llm as llm_mod

    llm_mod._llm_respond = None  # reset

    with patch("src.graph.llm.ChatOpenAI") as mock_chat:
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm

        result1 = llm_mod._get_llm_respond()
        result2 = llm_mod._get_llm_respond()  # cached

        assert result1 is result2
        assert mock_chat.call_count == 1

    llm_mod._llm_respond = None  # cleanup
