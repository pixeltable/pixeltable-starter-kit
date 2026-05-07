"""Data pipeline endpoints — upload, list, delete, detail queries."""
import uuid as _uuid

import pixeltable as pxt
from pixeltable.serving import FastAPIRouter
import config

router = FastAPIRouter(prefix="/api/data", tags=["data"])

docs = pxt.get_table(f"{config.APP_NAMESPACE}.documents")
images = pxt.get_table(f"{config.APP_NAMESPACE}.images")
videos = pxt.get_table(f"{config.APP_NAMESPACE}.videos")
chunks = pxt.get_table(f"{config.APP_NAMESPACE}.chunks")
video_frames = pxt.get_table(f"{config.APP_NAMESPACE}.video_frames")
video_sentences = pxt.get_table(f"{config.APP_NAMESPACE}.video_sentences")

# Uploads (documents/videos use background=True for async processing)
router.add_insert_route(docs, path="/upload/document", uploadfile_inputs=["document"], inputs=["timestamp"], outputs=["uuid"], background=True)
router.add_insert_route(images, path="/upload/image", uploadfile_inputs=["image"], inputs=["timestamp"], outputs=["uuid", "thumbnail"])
router.add_insert_route(videos, path="/upload/video", uploadfile_inputs=["video"], inputs=["timestamp"], outputs=["uuid"], background=True)

router.add_delete_route(docs, path="/delete/document")
router.add_delete_route(images, path="/delete/image")
router.add_delete_route(videos, path="/delete/video")


@pxt.query
def get_chunks(file_uuid: _uuid.UUID):
    return chunks.where(chunks.uuid == file_uuid).select(text=chunks.text, title=chunks.title, heading=chunks.heading, page=chunks.page)


@pxt.query
def get_frames(file_uuid: _uuid.UUID, limit: int = 12):
    return video_frames.where(video_frames.uuid == file_uuid).select(frame=video_frames.frame_thumbnail, position=video_frames.pos).limit(limit)


@pxt.query
def get_transcription(file_uuid: _uuid.UUID):
    return video_sentences.where(video_sentences.uuid == file_uuid).select(text=video_sentences.text)


router.add_query_route(path="/chunks", query=get_chunks, method="post")
router.add_query_route(path="/frames", query=get_frames, method="post")
router.add_query_route(path="/transcription", query=get_transcription, method="post")


@pxt.query
def list_documents():
    return docs.select(uuid=docs.uuid, name=docs.document, timestamp=docs.timestamp).order_by(docs.timestamp, asc=False)


@pxt.query
def list_images():
    return images.select(uuid=images.uuid, name=images.image, thumbnail=images.thumbnail, timestamp=images.timestamp).order_by(images.timestamp, asc=False)


@pxt.query
def list_videos():
    return videos.select(uuid=videos.uuid, name=videos.video, timestamp=videos.timestamp).order_by(videos.timestamp, asc=False)


router.add_query_route(path="/list/documents", query=list_documents, method="get")
router.add_query_route(path="/list/images", query=list_images, method="get")
router.add_query_route(path="/list/videos", query=list_videos, method="get")
