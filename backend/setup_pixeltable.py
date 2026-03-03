"""Schema definition for the Pixeltable Starter Kit.

Run once to initialize the database schema:
    python setup_pixeltable.py

WARNING: This drops and recreates the 'app' namespace on every run.
"""
import config
import pixeltable as pxt

from pixeltable.functions import image as pxt_image
from pixeltable.functions import openai
from pixeltable.functions import string as pxt_str
from pixeltable.functions.anthropic import invoke_tools, messages
from pixeltable.functions.audio import audio_splitter
from pixeltable.functions.document import document_splitter
from pixeltable.functions.huggingface import sentence_transformer, clip
from pixeltable.functions.string import string_splitter
from pixeltable.functions.uuid import uuid7
from pixeltable.functions.video import extract_audio, frame_iterator

import functions

pxt.drop_dir(config.APP_NAMESPACE, force=True)
pxt.create_dir(config.APP_NAMESPACE, if_exists="ignore")

# ── 1. Document Pipeline ─────────────────────────────────────────────────────

documents = pxt.create_table(
    f"{config.APP_NAMESPACE}.documents",
    {
        "document": pxt.Document,
        "uuid": uuid7(),
        "timestamp": pxt.Timestamp,
    },
    primary_key=["uuid"],
    if_exists="ignore",
)

chunks = pxt.create_view(
    f"{config.APP_NAMESPACE}.chunks",
    documents,
    iterator=document_splitter(
        document=documents.document,
        separators="page, sentence",
        metadata="title, heading, page",
    ),
    if_exists="ignore",
)

sentence_embed = sentence_transformer.using(model_id=config.EMBEDDING_MODEL_ID)

chunks.add_embedding_index(
    "text",
    string_embed=sentence_embed,
    if_exists="ignore",
)

print("  Documents: table + chunks view + embedding index")


@pxt.query
def search_documents(query_text: str):
    sim = chunks.text.similarity(query_text)
    return (
        chunks.where((sim > 0.5) & (pxt_str.len(chunks.text) > 30))
        .order_by(sim, asc=False)
        .select(
            chunks.text,
            source_doc=chunks.document,
            sim=sim,
            title=chunks.title,
            heading=chunks.heading,
            page_number=chunks.page,
        )
        .limit(20)
    )


# ── 2. Image Pipeline ────────────────────────────────────────────────────────

images = pxt.create_table(
    f"{config.APP_NAMESPACE}.images",
    {
        "image": pxt.Image,
        "uuid": uuid7(),
        "timestamp": pxt.Timestamp,
    },
    primary_key=["uuid"],
    if_exists="ignore",
)

images.add_computed_column(
    thumbnail=pxt_image.b64_encode(pxt_image.thumbnail(images.image, size=(320, 320))),
    if_exists="ignore",
)

images.add_embedding_index(
    "image",
    embedding=clip.using(model_id=config.CLIP_MODEL_ID),
    if_exists="ignore",
)

print("  Images: table + thumbnail computed column + CLIP embedding index")


@pxt.query
def search_images(query_text: str):
    sim = images.image.similarity(query_text)
    return (
        images.where(sim > 0.25)
        .order_by(sim, asc=False)
        .select(
            encoded_image=pxt_image.b64_encode(
                pxt_image.thumbnail(images.image, size=(224, 224)), "png"
            ),
            sim=sim,
        )
        .limit(5)
    )


# ── 3. Video Pipeline ────────────────────────────────────────────────────────

videos = pxt.create_table(
    f"{config.APP_NAMESPACE}.videos",
    {
        "video": pxt.Video,
        "uuid": uuid7(),
        "timestamp": pxt.Timestamp,
    },
    primary_key=["uuid"],
    if_exists="ignore",
)

# 3a. Keyframe extraction + CLIP embedding
video_frames = pxt.create_view(
    f"{config.APP_NAMESPACE}.video_frames",
    videos,
    iterator=frame_iterator(video=videos.video, keyframes_only=True),
    if_exists="ignore",
)

video_frames.add_computed_column(
    frame_thumbnail=pxt_image.b64_encode(
        pxt_image.thumbnail(video_frames.frame, size=(320, 320))
    ),
    if_exists="ignore",
)

video_frames.add_embedding_index(
    column="frame",
    embedding=clip.using(model_id=config.CLIP_MODEL_ID),
    if_exists="ignore",
)

print("  Videos: keyframes view + CLIP embedding index")


@pxt.query
def search_video_frames(query_text: str):
    sim = video_frames.frame.similarity(query_text)
    return (
        video_frames.where(sim > 0.25)
        .order_by(sim, asc=False)
        .select(
            encoded_frame=pxt_image.b64_encode(video_frames.frame, "png"),
            source_video=video_frames.video,
            sim=sim,
        )
        .limit(5)
    )


# 3b. Audio extraction -> transcription -> sentence splitting -> embedding
videos.add_computed_column(
    audio=extract_audio(videos.video, format="mp3"),
    if_exists="ignore",
)

video_audio_chunks = pxt.create_view(
    f"{config.APP_NAMESPACE}.video_audio_chunks",
    videos,
    iterator=audio_splitter(audio=videos.audio, duration=30.0),
    if_exists="ignore",
)

video_audio_chunks.add_computed_column(
    transcription=openai.transcriptions(
        audio=video_audio_chunks.audio_segment, model=config.WHISPER_MODEL_ID
    ),
    if_exists="ignore",
)

video_sentences = pxt.create_view(
    f"{config.APP_NAMESPACE}.video_sentences",
    video_audio_chunks.where(video_audio_chunks.transcription != None),
    iterator=string_splitter(
        text=video_audio_chunks.transcription.text, separators="sentence"
    ),
    if_exists="ignore",
)

video_sentences.add_embedding_index(
    column="text", string_embed=sentence_embed, if_exists="ignore"
)

print("  Videos: audio extraction -> Whisper transcription -> sentence embedding")


@pxt.query
def search_video_transcripts(query_text: str):
    """Search video transcripts by semantic similarity."""
    sim = video_sentences.text.similarity(query_text)
    return (
        video_sentences.where(sim > 0.7)
        .order_by(sim, asc=False)
        .select(
            video_sentences.text,
            source_video=video_sentences.video,
            sim=sim,
        )
        .limit(20)
    )


# ── 4. Chat History ──────────────────────────────────────────────────────────

chat_history = pxt.create_table(
    f"{config.APP_NAMESPACE}.chat_history",
    {
        "role": pxt.String,
        "content": pxt.String,
        "conversation_id": pxt.String,
        "timestamp": pxt.Timestamp,
    },
    if_exists="ignore",
)

chat_history.add_embedding_index(
    column="content", string_embed=sentence_embed, if_exists="ignore"
)

print("  Chat history: table + embedding index")


@pxt.query
def get_recent_chat_history(limit: int = 4):
    return (
        chat_history
        .order_by(chat_history.timestamp, asc=False)
        .select(role=chat_history.role, content=chat_history.content)
        .limit(limit)
    )


@pxt.query
def search_chat_history(query_text: str):
    sim = chat_history.content.similarity(query_text)
    return (
        chat_history.where(sim > 0.8)
        .order_by(sim, asc=False)
        .select(role=chat_history.role, content=chat_history.content, sim=sim)
        .limit(10)
    )


# ── 5. Agent Pipeline (tool-calling workflow) ────────────────────────────────

tools = pxt.tools(
    functions.web_search,
    search_video_transcripts,
)

agent = pxt.create_table(
    f"{config.APP_NAMESPACE}.agent",
    {
        "prompt": pxt.String,
        "timestamp": pxt.Timestamp,
        "initial_system_prompt": pxt.String,
        "final_system_prompt": pxt.String,
        "max_tokens": pxt.Int,
        "temperature": pxt.Float,
    },
    if_exists="ignore",
)

# Step 1: Initial LLM call with tools
agent.add_computed_column(
    initial_response=messages(
        model=config.CLAUDE_MODEL_ID,
        messages=[{"role": "user", "content": agent.prompt}],
        tools=tools,
        tool_choice=tools.choice(required=True),
        max_tokens=agent.max_tokens,
        model_kwargs={
            "system": agent.initial_system_prompt,
            "temperature": agent.temperature,
        },
    ),
    if_exists="ignore",
)

# Step 2: Tool execution
agent.add_computed_column(
    tool_output=invoke_tools(tools, agent.initial_response),
    if_exists="ignore",
)

# Step 3: Context retrieval (RAG)
agent.add_computed_column(
    doc_context=search_documents(agent.prompt),
    if_exists="ignore",
)
agent.add_computed_column(
    image_context=search_images(agent.prompt),
    if_exists="ignore",
)
agent.add_computed_column(
    video_frame_context=search_video_frames(agent.prompt),
    if_exists="ignore",
)
agent.add_computed_column(
    chat_memory_context=search_chat_history(agent.prompt),
    if_exists="ignore",
)

# Step 4: Recent chat history
agent.add_computed_column(
    history_context=get_recent_chat_history(),
    if_exists="ignore",
)

# Step 5: Assemble context
agent.add_computed_column(
    multimodal_context=functions.assemble_context(
        agent.prompt,
        agent.tool_output,
        agent.doc_context,
        agent.chat_memory_context,
    ),
    if_exists="ignore",
)

# Step 6: Assemble final messages
agent.add_computed_column(
    final_messages=functions.assemble_final_messages(
        agent.history_context,
        agent.multimodal_context,
        image_context=agent.image_context,
        video_frame_context=agent.video_frame_context,
    ),
    if_exists="ignore",
)

# Step 7: Final LLM call
agent.add_computed_column(
    final_response=messages(
        model=config.CLAUDE_MODEL_ID,
        messages=agent.final_messages,
        max_tokens=agent.max_tokens,
        model_kwargs={
            "system": agent.final_system_prompt,
            "temperature": agent.temperature,
        },
    ),
    if_exists="ignore",
)

# Step 8: Extract answer text
agent.add_computed_column(
    answer=agent.final_response.content[0].text,
    if_exists="ignore",
)

print("  Agent: 8-step tool-calling pipeline")
print("\nSchema setup complete.")
