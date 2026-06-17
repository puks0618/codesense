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
    try:
        from app.github.client import GitHubClient
        client = GitHubClient(140933129)
        token = await client._get_installation_token()
        return {"status": "ok", "token_prefix": token[:12] + "..."}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}
