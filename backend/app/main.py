import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.client import db_client
from app.webhooks.router import router as webhooks_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CodeSense starting up")
    await db_client.connect()
    yield
    await db_client.close()
    logger.info("CodeSense shutting down")


app = FastAPI(title="CodeSense", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "codesense"}


@app.get("/debug/github-auth")
async def debug_github_auth():
    """Temporary debug endpoint — remove after diagnosis."""
    import traceback
    from app.config import settings
    key = settings.github_private_key
    return {
        "key_length": len(key),
        "has_begin": "-----BEGIN RSA PRIVATE KEY-----" in key,
        "has_end": "-----END RSA PRIVATE KEY-----" in key,
        "newline_count": key.count("\n"),
        "literal_backslash_n_count": key.count("\\n"),
        "first_60": repr(key[:60]),
        "last_60": repr(key[-60:]),
    }
