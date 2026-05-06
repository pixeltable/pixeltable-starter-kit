"""Data pipeline endpoints — 100% Pixeltable FastAPIRouter.

Every endpoint is declarative: ``add_insert_route``, ``add_delete_route``,
or ``add_query_route``.  No hand-written ``@router`` endpoints.
"""
import pixeltable as pxt
from pixeltable.serving import FastAPIRouter

import config
import setup_pixeltable

router = FastAPIRouter(prefix="/api/data", tags=["data"])

docs_table = pxt.get_table(f"{config.APP_NAMESPACE}.documents")
images_table = pxt.get_table(f"{config.APP_NAMESPACE}.images")
videos_table = pxt.get_table(f"{config.APP_NAMESPACE}.videos")

# ── Insert (upload) ──────────────────────────────────────────────────────────
# Documents and videos use background=True: the endpoint accepts the file and
# returns a job handle immediately; the client polls /jobs/{id} until processing
# (chunking, embedding, transcription) completes.  Images are fast (thumbnail +
# CLIP) so they stay synchronous.
router.add_insert_route(docs_table, path="/upload/document", uploadfile_inputs=["document"], inputs=["timestamp"], outputs=["uuid"], background=True)
router.add_insert_route(images_table, path="/upload/image", uploadfile_inputs=["image"], inputs=["timestamp"], outputs=["uuid", "thumbnail"])
router.add_insert_route(videos_table, path="/upload/video", uploadfile_inputs=["video"], inputs=["timestamp"], outputs=["uuid"], background=True)

# ── Delete (by primary key uuid) ─────────────────────────────────────────────
router.add_delete_route(docs_table, path="/delete/document")
router.add_delete_route(images_table, path="/delete/image")
router.add_delete_route(videos_table, path="/delete/video")

# ── Detail queries (chunks, frames, transcription) ───────────────────────────
router.add_query_route(path="/chunks", query=setup_pixeltable.get_document_chunks, method="post")
router.add_query_route(path="/frames", query=setup_pixeltable.get_video_frames, method="post")
router.add_query_route(path="/transcription", query=setup_pixeltable.get_video_sentences, method="post")

# ── List queries (documents, images, videos) ─────────────────────────────────
router.add_query_route(path="/list/documents", query=setup_pixeltable.list_documents, method="get")
router.add_query_route(path="/list/images", query=setup_pixeltable.list_images, method="get")
router.add_query_route(path="/list/videos", query=setup_pixeltable.list_videos, method="get")
