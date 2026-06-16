import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseClient:
    def __init__(self):
        self._client: Optional[AsyncIOMotorClient] = None
        self._db = None

    async def connect(self):
        try:
            self._client = AsyncIOMotorClient(settings.mongodb_uri)
            await self._client.admin.command("ping")
            self._db = self._client["codesense"]
            await self._create_indexes()
            logger.info("Connected to MongoDB Atlas")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def _create_indexes(self):
        await self._db["code_chunks"].create_index(
            [("repo_full_name", 1), ("file_path", 1), ("chunk_name", 1)],
            unique=True,
        )
        await self._db["code_chunks"].create_index("file_hash")
        await self._db["reviews"].create_index([("repo_full_name", 1), ("pr_number", 1)])
        await self._db["team_style"].create_index("repo_full_name")
        await self._db["comment_feedback"].create_index("github_comment_id")
        logger.info("MongoDB indexes ensured")

    async def close(self):
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")

    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db[name]


db_client = DatabaseClient()
