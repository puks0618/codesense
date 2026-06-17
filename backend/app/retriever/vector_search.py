import asyncio
import logging
import re

from app.db.client import db_client
from app.indexer.embedder import EmbeddingGenerator

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.75


class CodeRetriever:
    def __init__(self):
        self._embedder = EmbeddingGenerator()

    async def find_related_chunks(
        self,
        query_text: str,
        repo_full_name: str,
        exclude_file_path: str,
        language: str = None,
        top_k: int = 5,
    ) -> list[dict]:
        if not query_text.strip():
            return []

        try:
            query_embedding = await asyncio.to_thread(self._embedder.embed_single, query_text)
        except Exception as e:
            logger.error(f"Failed to embed query for retrieval: {e}")
            return []

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "code_chunks_vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": 100,
                    "limit": top_k,
                    "filter": {
                        "repo_full_name": {"$eq": repo_full_name}
                    },
                }
            },
            {
                "$match": {
                    "file_path": {"$ne": exclude_file_path}
                }
            },
            {
                "$project": {
                    "chunk_text": 1,
                    "file_path": 1,
                    "chunk_name": 1,
                    "chunk_type": 1,
                    "language": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        try:
            col = db_client.get_collection("code_chunks")
            cursor = col.aggregate(pipeline)
            results = await cursor.to_list(length=top_k)
            return [r for r in results if r.get("score", 0) >= SIMILARITY_THRESHOLD]
        except Exception as e:
            logger.error(f"Vector search failed for {repo_full_name}: {e}", exc_info=True)
            return []

    async def find_callers_and_callees(
        self, function_name: str, repo_full_name: str
    ) -> list[dict]:
        if not function_name or function_name == "anonymous":
            return []

        try:
            pattern = rf"\b{re.escape(function_name)}\b"
            col = db_client.get_collection("code_chunks")
            cursor = col.find(
                {
                    "repo_full_name": repo_full_name,
                    "chunk_text": {"$regex": pattern},
                    "chunk_name": {"$ne": function_name},
                },
                {
                    "chunk_text": 1,
                    "file_path": 1,
                    "chunk_name": 1,
                    "chunk_type": 1,
                    "language": 1,
                },
            ).limit(5)
            return await cursor.to_list(length=5)
        except Exception as e:
            logger.error(
                f"Caller/callee search failed for {function_name}: {e}", exc_info=True
            )
            return []
