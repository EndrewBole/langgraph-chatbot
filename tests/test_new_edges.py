from langchain_core.messages import AIMessage, HumanMessage


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


def test_should_use_tools_with_tool_calls():
    from src.graph.edges import should_use_tools

    msg = AIMessage(content="", tool_calls=[{"name": "buscar", "args": {"query": "filtro"}, "id": "1"}])
    state = _make_state(messages=[msg])
    assert should_use_tools(state) == "tools"


def test_should_use_tools_without_tool_calls():
    from src.graph.edges import should_use_tools

    msg = AIMessage(content="Olá!")
    state = _make_state(messages=[msg])
    assert should_use_tools(state) == "human_handoff"


def test_check_human_status_active():
    from src.graph.edges import check_human_status

    state = _make_state(em_atendimento_humano=True)
    assert check_human_status(state) == "skip"


def test_check_human_status_inactive():
    from src.graph.edges import check_human_status

    state = _make_state(em_atendimento_humano=False)
    assert check_human_status(state) == "chatbot"
