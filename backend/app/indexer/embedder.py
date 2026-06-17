import hashlib
import logging

import openai

from app.config import settings

logger = logging.getLogger(__name__)

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100


class EmbeddingGenerator:
    def __init__(self):
        self._client = openai.OpenAI(api_key=settings.openai_api_key)

    def file_hash(self, source_code: str) -> str:
        return hashlib.sha256(source_code.encode("utf-8")).hexdigest()

    def embed_chunks(self, chunks: list, file_path: str) -> list:
        if not chunks:
            return chunks

        texts = [
            f"File: {file_path}\nFunction: {c['chunk_name']}\n\n{c['chunk_text']}"
            for c in chunks
        ]

        all_embeddings = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            try:
                response = self._client.embeddings.create(model=EMBED_MODEL, input=batch)
                all_embeddings.extend([d.embedding for d in response.data])
                logger.debug(f"Embedded batch {i // BATCH_SIZE + 1} ({len(batch)} chunks) for {file_path}")
            except Exception as e:
                logger.error(f"Embedding batch failed for {file_path}: {e}", exc_info=True)
                raise

        return [{**chunk, "embedding": embedding} for chunk, embedding in zip(chunks, all_embeddings)]

    def embed_single(self, text: str) -> list:
        response = self._client.embeddings.create(model=EMBED_MODEL, input=[text])
        return response.data[0].embedding
