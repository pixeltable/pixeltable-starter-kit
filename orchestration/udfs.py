"""UDFs for the batch pipeline."""

import pixeltable as pxt
from PIL import Image


@pxt.udf
def word_count(text: str) -> int:
    return len(text.split())


@pxt.udf
def char_count(text: str) -> int:
    return len(text)


@pxt.udf
def preview(text: str) -> str:
    return text[:200]


@pxt.udf
def thumbnail(img: Image.Image) -> Image.Image:
    """Generate a 128x128 thumbnail. When used with ``destination``,
    the thumbnail lands directly in the target bucket."""
    out = img.copy()
    out.thumbnail((128, 128))
    return out
