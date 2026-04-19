"""Tool-calling agent: query endpoint + conversation management."""
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
import pixeltable as pxt

import config
from models import (
    ToolAgentRow,
    ChatHistoryRow,
    ConversationSummary,
    ChatMessageItem,
    ConversationDetail,
    DeleteResponse,
    QueryRequest,
    QueryMetadata,
    QueryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/query", response_model=QueryResponse)
def query(body: QueryRequest):
    if not body.query:
        raise HTTPException(status_code=400, detail="Query text is required")

    try:
        agent_table = pxt.get_table(f"{config.APP_NAMESPACE}.agent")

        current_timestamp = datetime.now()
        row = ToolAgentRow(
            prompt=body.query,
            timestamp=current_timestamp,
        )
        agent_table.insert([row])

        result = (
            agent_table.where(agent_table.timestamp == current_timestamp)
            .select(
                agent_table.answer,
                agent_table.doc_context,
                agent_table.image_context,
                agent_table.tool_output,
            )
            .collect()
        )

        if not result:
            raise HTTPException(status_code=500, detail="No results after processing")

        data = result[0]

        conversation_id = body.conversation_id or "default"
        try:
            chat_table = pxt.get_table(f"{config.APP_NAMESPACE}.chat_history")
            chat_table.insert([ChatHistoryRow(
                role="user",
                content=body.query,
                conversation_id=conversation_id,
                timestamp=current_timestamp,
            )])
            answer = data.get("answer", "Error: No answer generated.")
            if answer and not answer.startswith("Error:"):
                chat_table.insert([ChatHistoryRow(
                    role="assistant",
                    content=answer,
                    conversation_id=conversation_id,
                    timestamp=datetime.now(),
                )])
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")

        return QueryResponse(
            answer=data.get("answer", "Error: No answer generated."),
            metadata=QueryMetadata(
                timestamp=current_timestamp.isoformat(),
                has_doc_context=bool(data.get("doc_context")),
                has_image_context=bool(data.get("image_context")),
                has_tool_output=bool(data.get("tool_output")),
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Conversations ─────────────────────────────────────────────────────────────

@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations():
    try:
        table = pxt.get_table(f"{config.APP_NAMESPACE}.chat_history")
        rows = list(
            table.select(
                role=table.role,
                content=table.content,
                conversation_id=table.conversation_id,
                timestamp=table.timestamp,
            )
            .order_by(table.timestamp, asc=True)
            .collect()
        )

        convos: dict[str, dict] = {}
        for row in rows:
            cid = row.get("conversation_id") or "default"
            if cid not in convos:
                ts = row["timestamp"]
                ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)
                convos[cid] = {
                    "conversation_id": cid,
                    "title": "",
                    "created_at": ts_str,
                    "updated_at": ts_str,
                    "message_count": 0,
                }
            entry = convos[cid]
            entry["message_count"] += 1
            ts = row["timestamp"]
            entry["updated_at"] = ts.isoformat() if isinstance(ts, datetime) else str(ts)
            if not entry["title"] and row["role"] == "user":
                entry["title"] = row["content"][:100]

        return sorted(convos.values(), key=lambda c: c["updated_at"], reverse=True)
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str):
    try:
        table = pxt.get_table(f"{config.APP_NAMESPACE}.chat_history")
        rows = list(
            table.where(table.conversation_id == conversation_id)
            .select(role=table.role, content=table.content, timestamp=table.timestamp)
            .order_by(table.timestamp, asc=True)
            .collect()
        )
        messages = []
        for row in rows:
            ts = row["timestamp"]
            messages.append({
                "role": row["role"],
                "content": row["content"],
                "timestamp": ts.isoformat() if isinstance(ts, datetime) else str(ts),
            })
        return {"conversation_id": conversation_id, "messages": messages}
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}", response_model=DeleteResponse)
def delete_conversation(conversation_id: str):
    try:
        table = pxt.get_table(f"{config.APP_NAMESPACE}.chat_history")
        status = table.delete(where=(table.conversation_id == conversation_id))
        return {"message": "Deleted", "num_deleted": status.num_rows}
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
