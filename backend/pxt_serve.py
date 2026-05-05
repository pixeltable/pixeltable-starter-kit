"""Pixeltable FastAPIRouter integration (v0.6+).

Exposes Pixeltable tables and @pxt.query functions as declarative HTTP
endpoints under ``/api/pxt``. Runs alongside the existing facade routers
(``/api/data``, ``/api/search``, ``/api/agent``) which stay unchanged.

The ``@insert_route`` decorator is used for the agent query endpoint: it
lets Pixeltable handle the insert + computed-column readback, while our
post-processing reshapes the response into ``QueryResponse``.

See docs/MIGRATION_PXTFASTAPIROUTER.md for architecture context.
"""

import logging
from datetime import datetime

import pixeltable as pxt
from pixeltable.serving import FastAPIRouter

import config
import setup_pixeltable
from models import QueryMetadata, QueryResponse

logger = logging.getLogger(__name__)


def build_pxt_router() -> FastAPIRouter:
    """Build and return the Pixeltable-native FastAPI router.

    Calls ``setup_pixeltable.setup()`` to ensure the schema exists and the
    module-level ``@pxt.query`` references are populated before registering
    routes.
    """
    setup_pixeltable.setup()

    router = FastAPIRouter(prefix="/api/pxt", tags=["pixeltable"])

    # ── Tables ────────────────────────────────────────────────────────────

    docs_table = pxt.get_table(f"{config.APP_NAMESPACE}.documents")
    images_table = pxt.get_table(f"{config.APP_NAMESPACE}.images")
    videos_table = pxt.get_table(f"{config.APP_NAMESPACE}.videos")
    agent_table = pxt.get_table(f"{config.APP_NAMESPACE}.agent")
    chat_table = pxt.get_table(f"{config.APP_NAMESPACE}.chat_history")

    # ── Data: insert routes (file uploads) ────────────────────────────────

    router.add_insert_route(
        docs_table,
        path="/tables/documents/insert",
        uploadfile_inputs=["document"],
        inputs=["timestamp"],
        outputs=["uuid"],
    )

    router.add_insert_route(
        images_table,
        path="/tables/images/insert",
        uploadfile_inputs=["image"],
        inputs=["timestamp"],
        outputs=["uuid", "thumbnail"],
    )

    router.add_insert_route(
        videos_table,
        path="/tables/videos/insert",
        uploadfile_inputs=["video"],
        inputs=["timestamp"],
        outputs=["uuid"],
    )

    # ── Data: delete routes (by primary key uuid) ─────────────────────────

    router.add_delete_route(docs_table, path="/tables/documents/delete")
    router.add_delete_route(images_table, path="/tables/images/delete")
    router.add_delete_route(videos_table, path="/tables/videos/delete")

    # ── Data: query routes (similarity search) ────────────────────────────

    router.add_query_route(
        path="/queries/documents",
        query=setup_pixeltable.search_documents,
        method="post",
    )

    router.add_query_route(
        path="/queries/images",
        query=setup_pixeltable.search_images,
        method="post",
    )

    router.add_query_route(
        path="/queries/video-frames",
        query=setup_pixeltable.search_video_frames,
        method="post",
    )

    router.add_query_route(
        path="/queries/video-transcripts",
        query=setup_pixeltable.search_video_transcripts,
        method="post",
    )

    router.add_query_route(
        path="/queries/chat-history",
        query=setup_pixeltable.search_chat_history,
        method="post",
    )

    # ── Chat history: delete by conversation_id ───────────────────────────

    router.add_delete_route(
        chat_table,
        path="/tables/chat-history/delete",
        match_columns=["conversation_id"],
    )

    # ── Agent: insert with post-processing ────────────────────────────────
    # The @insert_route decorator lets Pixeltable handle the insert and
    # column readback (the 8-step pipeline), then our function reshapes
    # the response.

    @router.insert_route(
        agent_table,
        path="/agent/query",
        inputs=["prompt", "timestamp", "initial_system_prompt",
                "final_system_prompt", "max_tokens", "temperature"],
        outputs=["answer", "doc_context", "image_context", "tool_output"],
    )
    def agent_query(
        *,
        answer: dict | None = None,
        doc_context: list | None = None,
        image_context: list | None = None,
        tool_output: dict | None = None,
    ) -> QueryResponse:
        answer_text = str(answer) if answer else "Error: No answer generated."
        return QueryResponse(
            answer=answer_text,
            metadata=QueryMetadata(
                timestamp=datetime.now().isoformat(),
                has_doc_context=bool(doc_context),
                has_image_context=bool(image_context),
                has_tool_output=bool(tool_output),
            ),
        )

    return router
