import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import config
from routers import data, search, agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        import setup_pixeltable
        setup_pixeltable.setup()
        logger.info("Pixeltable schema initialized")
    except Exception:
        logger.warning(
            "Pixeltable schema not initialized. "
            "Run 'python setup_pixeltable.py' first. "
            "The server will start but API calls will fail."
        )
    yield


app = FastAPI(
    title="Pixeltable Starter Kit",
    description="Full-stack multimodal AI starter app powered by Pixeltable",
    version="1.0.0",
    lifespan=lifespan,
)

# No cookies / Authorization headers are used, so allow_credentials stays False.
# This keeps CORS_ORIGINS="*" fully spec-compliant (browsers reject `*` + credentials).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(search.router)
app.include_router(agent.router)

# Pixeltable-native declarative routes (v0.6+).
# Exposes the same tables/queries as the facade routers above, but via
# Pixeltable's FastAPIRouter for scripts, admin, and direct API access.
try:
    from pxt_serve import build_pxt_router
    app.include_router(build_pxt_router())
    logger.info("Pixeltable FastAPIRouter mounted at /api/pxt")
except Exception:
    logger.warning(
        "Could not mount Pixeltable FastAPIRouter. "
        "Ensure 'python setup_pixeltable.py' has been run."
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend static build (production)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if not STATIC_DIR.is_dir():
        return JSONResponse(
            {"detail": "Frontend not built. Run: cd frontend && npm run build"},
            status_code=404,
        )
    file_path = STATIC_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["data/*", "*.log"],
    )
