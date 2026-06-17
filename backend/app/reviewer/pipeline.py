import asyncio
import logging
import re

from app.github.models import DiffResult, PREvent
from app.llm.reviewer import SEVERITY_ORDER, LLMReviewer
from app.retriever.vector_search import CodeRetriever

logger = logging.getLogger(__name__)

_FUNC_NAME_PATTERNS = [
    r"def\s+(\w+)\s*\(",
    r"async\s+def\s+(\w+)\s*\(",
    r"function\s+(\w+)\s*\(",
    r"func\s+(\w+)\s*\(",
    r"(\w+)\s*[:=]\s*(?:async\s+)?function\s*\(",
]

MAX_CONTEXT_CHUNKS = 8
MAX_FUNC_NAMES_PER_FILE = 3


def _extract_added_code(patch: str) -> str:
    lines = []
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return "\n".join(lines)


def _extract_new_function_names(patch: str) -> list[str]:
    added = _extract_added_code(patch)
    names = []
    for p in _FUNC_NAME_PATTERNS:
        names.extend(re.findall(p, added))
    return list(set(names))


class ReviewPipeline:
    def __init__(self):
        self._reviewer = LLMReviewer()
        self._retriever = CodeRetriever()

    async def run(self, pr_event: PREvent, diff_result: DiffResult) -> dict:
        all_comments = []

        for f in diff_result.files:
            context_chunks = await self._get_context(
                f.filename, f.patch, pr_event.repo_full_name
            )
            result = await asyncio.to_thread(
                self._reviewer.review_file,
                f.filename,
                f.patch,
                pr_event.pr_title,
                pr_event.pr_body,
                context_chunks or None,
            )
            for comment in result.get("comments", []):
                comment["file_path"] = f.filename
                all_comments.append(comment)

        all_comments.sort(
            key=lambda c: SEVERITY_ORDER.get(c.get("severity", "info"), 99)
        )
        all_comments = all_comments[:25]

        summary, verdict = self._reviewer.generate_summary(all_comments, diff_result)
        return {"comments": all_comments, "summary": summary, "verdict": verdict}

    async def _get_context(
        self, file_path: str, patch: str, repo: str
    ) -> list[dict]:
        added_code = _extract_added_code(patch)
        if not added_code.strip():
            return []

        context_chunks = []
        seen_names: set[str] = set()

        try:
            related = await self._retriever.find_related_chunks(
                query_text=added_code,
                repo_full_name=repo,
                exclude_file_path=file_path,
                top_k=5,
            )
            for chunk in related:
                context_chunks.append(chunk)
                seen_names.add(chunk.get("chunk_name", ""))
        except Exception as e:
            logger.warning(f"Vector retrieval failed for {file_path}: {e}")

        try:
            func_names = _extract_new_function_names(patch)
            for name in func_names[:MAX_FUNC_NAMES_PER_FILE]:
                callers = await self._retriever.find_callers_and_callees(name, repo)
                for chunk in callers:
                    if chunk.get("chunk_name") not in seen_names:
                        context_chunks.append(chunk)
                        seen_names.add(chunk.get("chunk_name", ""))
        except Exception as e:
            logger.warning(f"Caller/callee search failed for {file_path}: {e}")

        return context_chunks[:MAX_CONTEXT_CHUNKS]
