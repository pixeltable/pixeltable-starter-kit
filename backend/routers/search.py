"""Cross-modal similarity search across all media types."""
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pixeltable as pxt

import config
from models import SearchResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    types: list[str] = ["document", "image", "video_frame", "transcript"]
    limit: int = 20
    threshold: float = 0.3


@router.post("/search", response_model=SearchResponse)
def search(body: SearchRequest):
    results: list[dict] = []

    if "document" in body.types:
        try:
            chunks = pxt.get_table(f"{config.APP_NAMESPACE}.chunks")
            sim = chunks.text.similarity(string=body.query)
            rows = list(
                chunks.where(sim > body.threshold)
                .order_by(sim, asc=False)
                .select(
                    text=chunks.text,
                    uuid=chunks.uuid,
                    sim=sim,
                    title=chunks.title,
                    source=chunks.document,
                )
                .limit(body.limit)
                .collect()
            )
            for r in rows:
                results.append({
                    "type": "document",
                    "uuid": str(r.get("uuid", "")),
                    "similarity": round(r.get("sim", 0), 3),
                    "text": r.get("text", ""),
                    "metadata": {
                        "title": r.get("title"),
                        "source": os.path.basename(str(r.get("source", ""))),
                    },
                })
        except Exception as e:
            logger.warning(f"Document search failed: {e}")

    if "image" in body.types:
        try:
            imgs = pxt.get_table(f"{config.APP_NAMESPACE}.images")
            sim = imgs.image.similarity(string=body.query)
            rows = list(
                imgs.where(sim > 0.2)
                .order_by(sim, asc=False)
                .select(
                    uuid=imgs.uuid,
                    sim=sim,
                    thumbnail=imgs.thumbnail,
                    name=imgs.image,
                )
                .limit(body.limit)
                .collect()
            )
            for r in rows:
                results.append({
                    "type": "image",
                    "uuid": str(r.get("uuid", "")),
                    "similarity": round(r.get("sim", 0), 3),
                    "thumbnail": r.get("thumbnail"),
                    "metadata": {
                        "source": os.path.basename(
                            getattr(r.get("name"), "filename", "") or ""
                        ),
                    },
                })
        except Exception as e:
            logger.warning(f"Image search failed: {e}")

    if "video_frame" in body.types:
        try:
            frames = pxt.get_table(f"{config.APP_NAMESPACE}.video_frames")
            sim = frames.frame.similarity(string=body.query)
            rows = list(
                frames.where(sim > 0.2)
                .order_by(sim, asc=False)
                .select(
                    uuid=frames.uuid,
                    sim=sim,
                    thumbnail=frames.frame_thumbnail,
                    source=frames.video,
                )
                .limit(body.limit)
                .collect()
            )
            for r in rows:
                results.append({
                    "type": "video_frame",
                    "uuid": str(r.get("uuid", "")),
                    "similarity": round(r.get("sim", 0), 3),
                    "thumbnail": r.get("thumbnail"),
                    "metadata": {
                        "source": os.path.basename(str(r.get("source", ""))),
                    },
                })
        except Exception as e:
            logger.warning(f"Video frame search failed: {e}")

    if "transcript" in body.types:
        try:
            sents = pxt.get_table(f"{config.APP_NAMESPACE}.video_sentences")
            sim = sents.text.similarity(string=body.query)
            rows = list(
                sents.where(sim > body.threshold)
                .order_by(sim, asc=False)
                .select(
                    text=sents.text,
                    uuid=sents.uuid,
                    sim=sim,
                    source=sents.video,
                )
                .limit(body.limit * 3)  # fetch extra to allow dedup
                .collect()
            )
            seen_texts: set[str] = set()
            for r in rows:
                text = r.get("text", "")
                if text in seen_texts:
                    continue
                seen_texts.add(text)
                results.append({
                    "type": "transcript",
                    "uuid": str(r.get("uuid", "")),
                    "similarity": round(r.get("sim", 0), 3),
                    "text": text,
                    "metadata": {
                        "source": os.path.basename(str(r.get("source", ""))),
                    },
                })
        except Exception as e:
            logger.warning(f"Transcript search failed: {e}")

    results.sort(key=lambda x: x.get("similarity", 0), reverse=True)

    return {
        "query": body.query,
        "results": results[: body.limit],
    }
