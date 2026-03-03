"""UDFs for the batch pipeline."""

import pixeltable as pxt


@pxt.udf
def word_count(text: str) -> int:
    return len(text.split())


@pxt.udf
def char_count(text: str) -> int:
    return len(text)


@pxt.udf
def preview(text: str) -> str:
    return text[:200]
