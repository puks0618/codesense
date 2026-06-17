import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.auth.router import router as auth_router
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
app.include_router(auth_router)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "codesense"}
