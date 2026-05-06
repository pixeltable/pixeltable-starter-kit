"""Tool-calling agent: 1 hand-written endpoint + Pixeltable FastAPIRouter.

Only ``POST /query`` is hand-written — it has multi-table side effects
(agent table insert + 2x chat_history inserts).  Everything else is
declarative via ``add_query_route`` and ``add_delete_route``.
"""
import logging
from datetime import datetime

import pixeltable as pxt
from pixeltable.serving import FastAPIRouter
from fastapi import HTTPException

import config
import setup_pixeltable
from models import ToolAgentRow, ChatHistoryRow, QueryRequest, QueryMetadata, QueryResponse

logger = logging.getLogger(__name__)
router = FastAPIRouter(prefix="/api/agent", tags=["agent"])

chat_table = pxt.get_table(f"{config.APP_NAMESPACE}.chat_history")

# ── Declarative routes ───────────────────────────────────────────────────────
router.add_query_route(path="/conversation", query=setup_pixeltable.get_conversation_messages, method="post")
router.add_query_route(path="/messages", query=setup_pixeltable.list_all_messages, method="get")
router.add_delete_route(chat_table, path="/delete-conversation", match_columns=["conversation_id"])


# ── Hand-written: agent query (multi-table side effects) ─────────────────────

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
