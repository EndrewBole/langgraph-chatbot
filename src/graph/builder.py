from langgraph.graph import END, START, StateGraph

from src.graph.edges import check_human_status, should_use_tools
from src.graph.nodes import (
    classify_node,
    respond_node,
    human_handoff_node,
    send_response_node,
    tool_node,
)
from src.config import settings
from src.memory.checkpointer import get_checkpointer
from src.state import AgentState

builder = StateGraph(AgentState)

# Nós
builder.add_node("chatbot", classify_node)
builder.add_node("tools", tool_node)
builder.add_node("respond", respond_node)
builder.add_node("human_handoff", human_handoff_node)
builder.add_node("send_response", send_response_node)

# Fluxo
#
# START → (humano ativo?) → skip/END
#       → chatbot (LLM classifica)
#           → tool_calls? → tools → respond (LLM responde com resultados) → human_handoff
#           → sem tools  → human_handoff
#       → human_handoff (#HUMANO# check)
#       → send_response → END

builder.add_conditional_edges(
    START,
    check_human_status,
    {"chatbot": "chatbot", "skip": END},
)
builder.add_conditional_edges(
    "chatbot",
    should_use_tools,
    {"tools": "tools", "human_handoff": "human_handoff"},
)
builder.add_edge("tools", "respond")
builder.add_edge("respond", "human_handoff")
builder.add_edge("human_handoff", "send_response")
builder.add_edge("send_response", END)

checkpointer = get_checkpointer(use_postgres=bool(settings.DATABASE_URL))
graph = builder.compile(checkpointer=checkpointer)
