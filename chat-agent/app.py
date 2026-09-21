"""pxt schema update app.py agent && pxt service update app.py agent

Export ANTHROPIC_API_KEY before the first pxt command; the service inherits the daemon's environment.
Exported it later? The CLI refuses with STALE_CONFIG: run pxt daemon restart, then pxt service update app.py agent.
"""

# ruff: noqa: F821

from datetime import datetime
from typing import Any

import pixeltable as pxt
import pixeltable.functions as pxtf
import pydantic
from fastapi import HTTPException
from pixeltable.functions.anthropic import messages
from pixeltable.functions.huggingface import sentence_transformer
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()
embed_fn = sentence_transformer.using(model_id="all-MiniLM-L6-v2")
_DEFAULT_SYSTEM = "You are a helpful assistant with a knowledge base and conversation memory. Be concise and accurate."


@pxt.udf
def assemble_context(
    prompt: str,
    memory_context: list[dict[str, Any]] | None,
    knowledge_context: list[Any] | None,
) -> str:
    parts = [f"QUESTION:\n{prompt}"]
    if knowledge_context:
        items = [item.get("text", str(item)) if isinstance(item, dict) else str(item) for item in knowledge_context]
        parts.append("KNOWLEDGE:\n" + "\n".join(f"- {t}" for t in items if t))
    if memory_context:
        lines = [f"- [{m.get('role', '?')}] {m.get('content', '')[:200]}" for m in memory_context]
        parts.append("MEMORY:\n" + "\n".join(lines))
    return "\n\n".join(parts)


class Knowledge(TableModel, name="knowledge"):
    body: pxt.String
    title: pxt.String
    source: pxt.String
    uuid = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    timestamp: pxt.Timestamp | None


class Sentences(
    TableModel,
    name="sentences",
    base=Knowledge,
    iterator=pxtf.string.string_splitter(Knowledge.body, separators="sentence"),
):
    __indexes__ = [pxt.EmbeddingIndex(text, embedding=embed_fn, name="knowledge_embed")]


class Conversations(TableModel, name="conversations"):
    role: pxt.String
    content: pxt.String
    conversation_id: pxt.String
    user_id: pxt.String
    uuid = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    timestamp: pxt.Timestamp | None
    __indexes__ = [pxt.EmbeddingIndex(content, embedding=embed_fn, name="conversations_embed")]


@pxt.query
def search_knowledge(query_text: str, limit: int = 10) -> pxt.Query:
    sim = Sentences.text.similarity(string=query_text)
    return Sentences.where(sim > 0.3).order_by(sim, asc=False).select(Sentences.text, score=sim).limit(limit)


@pxt.query
def recall_memory(query_text: str, limit: int = 10) -> pxt.Query:
    sim = Conversations.content.similarity(string=query_text)
    return (
        Conversations.where(sim > 0.5)
        .order_by(sim, asc=False)
        .select(
            role=Conversations.role,
            content=Conversations.content,
            conversation_id=Conversations.conversation_id,
            score=sim,
        )
        .limit(limit)
    )


@pxt.query
def get_history(conversation_id: str, limit: int = 10) -> pxt.Query:
    return (
        Conversations.where(Conversations.conversation_id == conversation_id)
        .order_by(Conversations.timestamp, asc=False)
        .select(role=Conversations.role, content=Conversations.content, timestamp=Conversations.timestamp)
        .limit(limit)
    )


class Agent(TableModel, name="agent"):
    prompt: pxt.String
    conversation_id: pxt.String
    system_prompt: pxt.String
    max_tokens: pxt.Int
    uuid = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    timestamp: pxt.Timestamp | None
    memory_context = recall_memory(prompt)
    knowledge_context = search_knowledge(prompt)
    context = assemble_context(prompt, memory_context, knowledge_context)
    final_response = messages(
        model="claude-sonnet-5",
        messages=[{"role": "user", "content": context}],
        max_tokens=max_tokens,
        model_kwargs={"system": system_prompt},
    )
    answer = final_response.content[0].text.astype(pxt.String)


api = FastAPIRouter(name="agent", prefix="/api")
api.add_insert_route(
    Knowledge, path="/knowledge", inputs=[Knowledge.body, Knowledge.title, Knowledge.source], outputs=[Knowledge.uuid]
)
api.add_insert_route(
    Conversations,
    path="/conversations",
    inputs=[Conversations.role, Conversations.content, Conversations.conversation_id, Conversations.user_id],
    outputs=[Conversations.uuid],
)
api.add_query_route(path="/knowledge/search", query=search_knowledge, method="get")
api.add_query_route(path="/memory/search", query=recall_memory, method="get")
api.add_query_route(path="/history", query=get_history, method="get")
api.add_delete_route(Knowledge, path="/delete/knowledge")
api.add_delete_route(Conversations, path="/delete/conversation")


# Models are bound to their tables by `pxt service` (at the TARGET being served, local or pxt://).
# From plain Python, call TableModel.bind_all("agent") after `import app`.
def _append_turns(question: str, answer: str, conversation_id: str, ts: datetime) -> None:
    Conversations.insert(
        [
            {
                "role": "user",
                "content": question,
                "conversation_id": conversation_id,
                "user_id": "default",
                "timestamp": ts,
            },
            {
                "role": "assistant",
                "content": answer,
                "conversation_id": conversation_id,
                "user_id": "system",
                "timestamp": datetime.now(),
            },
        ]
    )


def ask(
    question: str,
    conversation_id: str = "default",
    *,
    system_prompt: str | None = None,
    max_tokens: int = 1024,
) -> str:
    if not Agent.is_bound:
        raise RuntimeError(
            "Models are not bound to tables. Run `pxt schema update app.py agent`, "
            "then `TableModel.bind_all('agent')` before calling ask() from plain Python."
        )
    ts = datetime.now()
    status = Agent.insert(
        [
            {
                "prompt": question,
                "conversation_id": conversation_id,
                "system_prompt": system_prompt or _DEFAULT_SYSTEM,
                "max_tokens": max_tokens,
                "timestamp": ts,
            }
        ],
        return_rows=True,
    )
    if not status.rows:
        return "Error: no response generated."
    answer = status.rows[0].get("answer") or "Error: no answer in response."
    _append_turns(question, answer, conversation_id, ts)
    return answer


class AskRequest(pydantic.BaseModel):
    prompt: str
    conversation_id: str = "default"
    system_prompt: str | None = None
    max_tokens: int = 1024


class AskResponse(pydantic.BaseModel):
    answer: str


# Hand-written rather than declared: /ask orchestrates an insert plus two follow-up writes.
# FastAPIRouter subclasses fastapi.APIRouter so this is served normally, but it is not part of
# service_spec(), so `pxt service diff` and `pxt service list` will not mention it.
@api.post("/ask")
def ask_http(body: AskRequest) -> AskResponse:
    try:
        return AskResponse(
            answer=ask(
                body.prompt,
                body.conversation_id,
                system_prompt=body.system_prompt,
                max_tokens=body.max_tokens,
            )
        )
    except pxt.Error as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.to_dict()) from exc
