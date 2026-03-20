from typing import Annotated, NotRequired

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    session_id: str
    chat_phone: str
    tentativas_categoria_e: int
    requer_humano: bool
    em_atendimento_humano: bool
    awaiting_reply: bool
    follow_up_sent: bool
    last_activity: NotRequired[float]
    session_start: NotRequired[int]
    channel: NotRequired[str]
    chatwoot_conversation_id: NotRequired[int]
