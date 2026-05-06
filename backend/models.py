from datetime import datetime

from pydantic import BaseModel

import config


# ── Pixeltable row models ────────────────────────────────────────────────────

class ToolAgentRow(BaseModel):
    """Row model for the app.agent table."""
    prompt: str
    timestamp: datetime
    initial_system_prompt: str = config.INITIAL_SYSTEM_PROMPT
    final_system_prompt: str = config.FINAL_SYSTEM_PROMPT
    max_tokens: int = config.DEFAULT_MAX_TOKENS
    temperature: float = config.DEFAULT_TEMPERATURE


class ChatHistoryRow(BaseModel):
    """Row model for the app.chat_history table."""
    role: str
    content: str
    conversation_id: str
    timestamp: datetime


# ── Agent query request/response ─────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    conversation_id: str | None = None


class QueryMetadata(BaseModel):
    timestamp: str
    has_doc_context: bool
    has_image_context: bool
    has_tool_output: bool


class QueryResponse(BaseModel):
    answer: str
    metadata: QueryMetadata
