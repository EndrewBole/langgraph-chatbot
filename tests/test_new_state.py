from langchain_core.messages import HumanMessage


def test_state_has_session_id():
    from src.state import AgentState

    state: AgentState = {
        "messages": [HumanMessage(content="oi")],
        "session_id": "5511999999999",
        "chat_phone": "5511999999999",
        "tentativas_categoria_e": 0,
        "requer_humano": False,
        "em_atendimento_humano": False,
    }
    assert state["session_id"] == "5511999999999"
    assert state["requer_humano"] is False


def test_state_requer_humano():
    from src.state import AgentState

    state: AgentState = {
        "messages": [HumanMessage(content="humano")],
        "session_id": "123",
        "chat_phone": "123",
        "tentativas_categoria_e": 3,
        "requer_humano": True,
        "em_atendimento_humano": True,
    }
    assert state["requer_humano"] is True
    assert state["em_atendimento_humano"] is True
