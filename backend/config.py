import os

from dotenv import load_dotenv

load_dotenv(override=True)

APP_NAMESPACE = "app"

# LLM & Model IDs
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large-instruct")
CLIP_MODEL_ID = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")
WHISPER_MODEL_ID = os.getenv("WHISPER_MODEL", "whisper-1")
CLAUDE_MODEL_ID = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

# System prompts for the agent pipeline
INITIAL_SYSTEM_PROMPT = (
    "Identify the best tool(s) to answer the user's query based on "
    "the available data sources (documents, images, video transcripts)."
)
FINAL_SYSTEM_PROMPT = (
    "Based on the provided context and the user's query, provide a clear "
    "and helpful answer. Cite specific sources when possible."
)

# LLM parameters
DEFAULT_MAX_TOKENS: int = 1024
DEFAULT_TEMPERATURE: float = 0.7

# CORS
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
