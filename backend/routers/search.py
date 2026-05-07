"""Cross-modal similarity search endpoints."""
import pixeltable as pxt
from pixeltable.serving import FastAPIRouter
import config

router = FastAPIRouter(prefix="/api/search", tags=["search"])

chunks = pxt.get_table(f"{config.APP_NAMESPACE}.chunks")
images = pxt.get_table(f"{config.APP_NAMESPACE}.images")
video_frames = pxt.get_table(f"{config.APP_NAMESPACE}.video_frames")
video_sentences = pxt.get_table(f"{config.APP_NAMESPACE}.video_sentences")


@pxt.query
def search_documents(query_text: str):
    sim = chunks.text.similarity(string=query_text)
    return chunks.where(sim > 0.3).order_by(sim, asc=False).select(
        text=chunks.text, uuid=chunks.uuid, sim=sim, title=chunks.title, source=chunks.document).limit(20)


@pxt.query
def search_images(query_text: str):
    sim = images.image.similarity(string=query_text)
    return images.where(sim > 0.2).order_by(sim, asc=False).select(
        uuid=images.uuid, sim=sim, thumbnail=images.thumbnail, source=images.image).limit(20)


@pxt.query
def search_video_frames(query_text: str):
    sim = video_frames.frame.similarity(string=query_text)
    return video_frames.where(sim > 0.2).order_by(sim, asc=False).select(
        uuid=video_frames.uuid, sim=sim, thumbnail=video_frames.frame_thumbnail, source=video_frames.video).limit(20)


@pxt.query
def search_transcripts(query_text: str):
    sim = video_sentences.text.similarity(string=query_text)
    return video_sentences.where(sim > 0.3).order_by(sim, asc=False).select(
        text=video_sentences.text, uuid=video_sentences.uuid, sim=sim, source=video_sentences.video).limit(60)


router.add_query_route(path="/documents", query=search_documents, method="post")
router.add_query_route(path="/images", query=search_images, method="post")
router.add_query_route(path="/video-frames", query=search_video_frames, method="post")
router.add_query_route(path="/transcripts", query=search_transcripts, method="post")
