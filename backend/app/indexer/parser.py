import asyncio
import base64
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
}

# Maps each language to: which AST node types to extract, and what chunk_type to assign them
NODE_TYPES = {
    "python": {
        "function_definition": "function",
        "async_function_definition": "function",
        "class_definition": "class",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "tsx": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
    },
    "java": {
        "method_declaration": "method",
        "class_declaration": "class",
    },
}

SKIP_DIRS = frozenset({"node_modules", "vendor", ".git", "dist", "build", "__pycache__"})
MAX_FILE_BYTES = 100 * 1024
MAX_CHUNK_CHARS = 6000


class CodeParser:
    def __init__(self):
        self._parsers: dict = {}

    def get_language(self, file_path: str) -> Optional[str]:
        for ext, lang in EXTENSION_TO_LANGUAGE.items():
            if file_path.endswith(ext):
                return lang
        return None

    def _load_parser(self, language: str):
        from tree_sitter import Language, Parser
        try:
            if language == "python":
                import tree_sitter_python as m
                lang = Language(m.language())
            elif language == "javascript":
                import tree_sitter_javascript as m
                lang = Language(m.language())
            elif language == "typescript":
                import tree_sitter_typescript as m
                lang = Language(m.language_typescript())
            elif language == "tsx":
                import tree_sitter_typescript as m
                lang = Language(m.language_tsx())
            elif language == "go":
                import tree_sitter_go as m
                lang = Language(m.language())
            elif language == "java":
                import tree_sitter_java as m
                lang = Language(m.language())
            else:
                return None
            return Parser(lang)
        except Exception as e:
            logger.warning(f"Failed to load tree-sitter parser for {language}: {e}")
            return None

    def _get_parser(self, language: str):
        if language not in self._parsers:
            self._parsers[language] = self._load_parser(language)
        return self._parsers[language]

    def parse_file(self, file_path: str, source_code: str) -> list:
        language = self.get_language(file_path)
        if language is None:
            return self._module_chunk(file_path, source_code)

        parser = self._get_parser(language)
        if parser is None:
            return self._module_chunk(file_path, source_code)

        try:
            source_bytes = source_code.encode("utf-8")
            tree = parser.parse(source_bytes)
            chunks = self._extract_chunks(tree.root_node, source_bytes, language)
            return chunks if chunks else self._module_chunk(file_path, source_code)
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return self._module_chunk(file_path, source_code)

    def _module_chunk(self, file_path: str, source_code: str) -> list:
        return [{
            "chunk_type": "module",
            "chunk_name": file_path.rsplit("/", 1)[-1],
            "chunk_text": source_code[:MAX_CHUNK_CHARS],
            "start_line": 1,
            "end_line": source_code.count("\n") + 1,
        }]

    def _get_node_name(self, node, source_bytes: bytes) -> str:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                    break
        if name_node is None:
            return "anonymous"
        return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

    def _extract_chunks(self, root_node, source_bytes: bytes, language: str) -> list:
        targets = NODE_TYPES.get(language, {})
        if not targets:
            return []

        chunks = []

        def walk(node):
            if node.type in targets:
                chunk_type = targets[node.type]
                name = self._get_node_name(node, source_bytes)
                text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1

                # Oversized class: extract methods as individual chunks instead
                if chunk_type == "class" and len(text) > MAX_CHUNK_CHARS:
                    for child in node.children:
                        if child.type in targets:
                            child_name = self._get_node_name(child, source_bytes)
                            child_text = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                            chunks.append({
                                "chunk_type": targets[child.type],
                                "chunk_name": f"{name}.{child_name}",
                                "chunk_text": child_text[:MAX_CHUNK_CHARS],
                                "start_line": child.start_point[0] + 1,
                                "end_line": child.end_point[0] + 1,
                            })
                    return  # Skip adding the full oversized class

                chunks.append({
                    "chunk_type": chunk_type,
                    "chunk_name": name,
                    "chunk_text": text[:MAX_CHUNK_CHARS],
                    "start_line": start_line,
                    "end_line": end_line,
                })
                return  # Don't recurse further into matched nodes

            for child in node.children:
                walk(child)

        walk(root_node)
        return chunks


class RepositoryIndexer:
    def __init__(self):
        self._parser = CodeParser()

    async def index_repository(self, repo_full_name: str, github_client) -> dict:
        from app.db.client import db_client
        from app.indexer.embedder import EmbeddingGenerator

        embedder = EmbeddingGenerator()
        chunks_col = db_client.get_collection("code_chunks")
        start_ms = int(time.time() * 1000)
        files_indexed = 0
        chunks_created = 0
        files_skipped = 0

        logger.info(f"Starting full index for {repo_full_name}")

        try:
            resp = await github_client._request("GET", f"https://api.github.com/repos/{repo_full_name}")
            resp.raise_for_status()
            default_branch = resp.json()["default_branch"]

            resp2 = await github_client._request(
                "GET",
                f"https://api.github.com/repos/{repo_full_name}/git/trees/{default_branch}",
                params={"recursive": "1"},
            )
            resp2.raise_for_status()
            tree = resp2.json().get("tree", [])
            logger.info(f"{repo_full_name}: {len(tree)} tree entries, branch={default_branch}")

            for item in tree:
                if item["type"] != "blob":
                    continue

                path = item["path"]

                # Skip excluded directories
                path_parts = path.split("/")
                if any(part in SKIP_DIRS for part in path_parts[:-1]):
                    continue

                # Language filter
                language = self._parser.get_language(path)
                if language is None:
                    continue

                # Size filter
                if item.get("size", 0) > MAX_FILE_BYTES:
                    logger.debug(f"Skipping large file: {path}")
                    files_skipped += 1
                    continue

                # Fetch content
                try:
                    resp3 = await github_client._request(
                        "GET",
                        f"https://api.github.com/repos/{repo_full_name}/contents/{path}",
                        params={"ref": default_branch},
                    )
                    resp3.raise_for_status()
                    encoded = resp3.json().get("content", "").replace("\n", "")
                    source_code = base64.b64decode(encoded).decode("utf-8", errors="replace")
                except Exception as e:
                    logger.warning(f"Failed to fetch {path}: {e}")
                    files_skipped += 1
                    continue

                # Cache check: skip if file hash already indexed
                file_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
                try:
                    if await chunks_col.find_one({"repo_full_name": repo_full_name, "file_path": path, "file_hash": file_hash}):
                        files_skipped += 1
                        continue
                except Exception:
                    pass

                # Parse (CPU-bound)
                raw_chunks = await asyncio.to_thread(self._parser.parse_file, path, source_code)
                for chunk in raw_chunks:
                    chunk["file_hash"] = file_hash

                # Embed (IO-bound)
                try:
                    chunks_with_embeddings = await asyncio.to_thread(embedder.embed_chunks, raw_chunks, path)
                except Exception as e:
                    logger.error(f"Embedding failed for {path}: {e}")
                    files_skipped += 1
                    continue

                # Upsert to MongoDB
                now = datetime.now(timezone.utc)
                try:
                    for chunk in chunks_with_embeddings:
                        await chunks_col.update_one(
                            {"repo_full_name": repo_full_name, "file_path": path, "chunk_name": chunk["chunk_name"]},
                            {"$set": {
                                **chunk,
                                "repo_full_name": repo_full_name,
                                "file_path": path,
                                "language": language,
                                "indexed_at": now,
                            }},
                            upsert=True,
                        )
                except Exception as e:
                    logger.error(f"MongoDB upsert failed for {path}: {e}")
                    continue

                files_indexed += 1
                chunks_created += len(chunks_with_embeddings)
                logger.info(f"Indexed {path}: {len(chunks_with_embeddings)} chunks")

        except Exception as e:
            logger.error(f"index_repository failed for {repo_full_name}: {e}", exc_info=True)

        duration_ms = int(time.time() * 1000) - start_ms
        summary = {
            "files_indexed": files_indexed,
            "chunks_created": chunks_created,
            "files_skipped": files_skipped,
            "duration_ms": duration_ms,
        }
        logger.info(f"Indexing complete for {repo_full_name}: {summary}")
        return summary

    async def index_pr_changes(self, repo_full_name: str, changed_files: list, github_client) -> None:
        from app.db.client import db_client
        from app.indexer.embedder import EmbeddingGenerator

        embedder = EmbeddingGenerator()
        chunks_col = db_client.get_collection("code_chunks")

        # Fetch default branch once
        try:
            resp = await github_client._request("GET", f"https://api.github.com/repos/{repo_full_name}")
            resp.raise_for_status()
            default_branch = resp.json()["default_branch"]
        except Exception as e:
            logger.error(f"Could not get default branch for {repo_full_name}: {e}")
            return

        for f in changed_files:
            path = f.filename if hasattr(f, "filename") else f.get("filename", "")
            status = f.status if hasattr(f, "status") else f.get("status", "")

            # Remove chunks for deleted files
            if status == "removed":
                try:
                    result = await chunks_col.delete_many({"repo_full_name": repo_full_name, "file_path": path})
                    logger.info(f"Removed {result.deleted_count} chunks for deleted file {path}")
                except Exception as e:
                    logger.error(f"Failed to delete chunks for {path}: {e}")
                continue

            language = self._parser.get_language(path)
            if language is None:
                continue

            try:
                resp2 = await github_client._request(
                    "GET",
                    f"https://api.github.com/repos/{repo_full_name}/contents/{path}",
                    params={"ref": default_branch},
                )
                resp2.raise_for_status()
                encoded = resp2.json().get("content", "").replace("\n", "")
                source_code = base64.b64decode(encoded).decode("utf-8", errors="replace")
            except Exception as e:
                logger.warning(f"Failed to fetch merged file {path}: {e}")
                continue

            file_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
            raw_chunks = await asyncio.to_thread(self._parser.parse_file, path, source_code)
            for chunk in raw_chunks:
                chunk["file_hash"] = file_hash

            try:
                chunks_with_embeddings = await asyncio.to_thread(embedder.embed_chunks, raw_chunks, path)
            except Exception as e:
                logger.error(f"Embedding failed for merged file {path}: {e}")
                continue

            now = datetime.now(timezone.utc)
            try:
                await chunks_col.delete_many({"repo_full_name": repo_full_name, "file_path": path})
                for chunk in chunks_with_embeddings:
                    await chunks_col.update_one(
                        {"repo_full_name": repo_full_name, "file_path": path, "chunk_name": chunk["chunk_name"]},
                        {"$set": {
                            **chunk,
                            "repo_full_name": repo_full_name,
                            "file_path": path,
                            "language": language,
                            "indexed_at": now,
                        }},
                        upsert=True,
                    )
                logger.info(f"Re-indexed merged file {path}: {len(chunks_with_embeddings)} chunks")
            except Exception as e:
                logger.error(f"MongoDB upsert failed for merged file {path}: {e}")
