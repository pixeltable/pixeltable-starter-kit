"""Cross-modal similarity search — 100% Pixeltable FastAPIRouter.

Each embedding index gets its own ``add_query_route``.  The frontend calls
the active types in parallel and merges/sorts results client-side.
"""
from pixeltable.serving import FastAPIRouter

import setup_pixeltable

router = FastAPIRouter(prefix="/api/search", tags=["search"])

router.add_query_route(path="/documents", query=setup_pixeltable.search_documents_api, method="post")
router.add_query_route(path="/images", query=setup_pixeltable.search_images_api, method="post")
router.add_query_route(path="/video-frames", query=setup_pixeltable.search_video_frames_api, method="post")
router.add_query_route(path="/transcripts", query=setup_pixeltable.search_transcripts_api, method="post")
