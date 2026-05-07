"""UDFs for the Pixeltable Starter Kit agent pipeline."""
import os
from typing import Any

import pixeltable as pxt


@pxt.udf
def web_search(keywords: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo (no API key required)."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news(keywords=keywords, region="wt-wt", safesearch="off", timelimit="m", max_results=max_results))
            if not results:
                return "No results found."
            return "\n".join(
                f"{i}. {r.get('title', 'N/A')}\n   Source: {r.get('source', 'N/A')}\n   URL: {r.get('url', 'N/A')}\n   {r.get('body', 'N/A')}\n"
                for i, r in enumerate(results, 1)
            )
    except Exception as e:
        return f"Search failed: {e}."


@pxt.udf
def assemble_context(
    question: str,
    tool_outputs: list[dict[str, Any]] | None,
    doc_context: list[Any] | None,
    chat_memory_context: list[dict[str, Any]] | None = None,
) -> str:
    """Combine all context sources into a single text block for the LLM."""
    doc_str = "N/A"
    if doc_context:
        items = []
        for item in doc_context:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            source = os.path.basename(str(item.get("source_doc", "Unknown") if isinstance(item, dict) else "Unknown"))
            if text:
                items.append(f"- [Source: {source}] {text}")
        if items:
            doc_str = "\n".join(items)

    chat_str = "N/A"
    if chat_memory_context:
        lines = [f"- [{m.get('role', '?')}] {m.get('content', '')[:150]}" for m in chat_memory_context]
        if lines:
            chat_str = "\n".join(lines)

    return (
        f"ORIGINAL QUESTION:\n{question}\n\nAVAILABLE CONTEXT:\n\n"
        f"[TOOL RESULTS]\n{tool_outputs or 'N/A'}\n\n"
        f"[DOCUMENT CONTEXT]\n{doc_str}\n\n"
        f"[CHAT HISTORY CONTEXT]\n{chat_str}"
    )


def _extract_b64_images(items: list[dict[str, Any]] | None, key: str) -> list[dict[str, Any]]:
    """Extract base64-encoded image blocks from context items."""
    result = []
    for item in items or []:
        if not isinstance(item, dict) or key not in item:
            continue
        data = item[key]
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        if isinstance(data, str):
            result.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}})
    return result


@pxt.udf
def assemble_final_messages(
    history_context: list[dict[str, Any]] | None,
    multimodal_context_text: str,
    image_context: list[dict[str, Any]] | None = None,
    video_frame_context: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build the final message list for the LLM, incorporating all context."""
    msgs: list[dict[str, Any]] = []
    if history_context:
        for item in reversed(history_context):
            if item.get("role") and item.get("content"):
                msgs.append({"role": item["role"], "content": item["content"]})

    final_user_content: list[dict[str, Any]] = [
        *_extract_b64_images(image_context, "encoded_image"),
        *_extract_b64_images(video_frame_context, "encoded_frame"),
        {"type": "text", "text": multimodal_context_text},
    ]
    msgs.append({"role": "user", "content": final_user_content})
    return msgs
