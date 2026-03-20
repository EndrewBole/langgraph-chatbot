from langchain_core.messages import AIMessage

from src.state import AgentState


def should_use_tools(state: AgentState) -> str:
    """Após classify: se tem tool_calls → tools, senão → human_handoff."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "human_handoff"


def check_human_status(state: AgentState) -> str:
    """Entry point: se em atendimento humano, pula o fluxo."""
    if state.get("em_atendimento_humano", False):
        return "skip"
    return "chatbot"
