import asyncio
import json
import logging
import re
from typing import Optional

import anthropic

from app.config import settings
from app.github.models import DiffResult
from app.llm.prompts import CONTEXT_SECTION_TEMPLATE, REVIEW_USER_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".cpp": "c++",
    ".c": "c",
    ".cs": "c#",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "shell",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
}

SKIP_PATTERNS = [
    r"\.lock$",
    r"\.min\.js$",
    r"\.generated\.",
    r"/migrations/",
    r"/__snapshots__/",
    r"\.d\.ts$",
    r"_pb2\.py$",
]

SEVERITY_ORDER = {"critical": 0, "warning": 1, "suggestion": 2, "info": 3}


def _detect_language(file_path: str) -> str:
    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        if file_path.endswith(ext):
            return lang
    return "unknown"


def _should_skip(file_path: str) -> bool:
    return any(re.search(p, file_path) for p in SKIP_PATTERNS)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _extract_addition_lines(diff: str) -> set[int]:
    """Return set of new-file line numbers that are additions (+)."""
    addition_lines = set()
    new_line = 0
    for line in diff.split("\n"):
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                new_line = int(m.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            new_line += 1
            addition_lines.add(new_line)
        elif not line.startswith("-"):
            new_line += 1
    return addition_lines


class LLMReviewer:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def review_file(
        self,
        file_path: str,
        diff: str,
        pr_title: str,
        pr_body: str,
        context_chunks: Optional[list] = None,
    ) -> dict:
        if _should_skip(file_path):
            logger.debug(f"Skipping {file_path} (skip pattern match)")
            return {"comments": [], "file_summary": "File skipped.", "has_critical_issues": False}

        language = _detect_language(file_path)

        max_chars = 8000 * 4
        truncated = False
        if len(diff) > max_chars:
            diff = diff[:max_chars]
            truncated = True

        context_section = ""
        if context_chunks:
            chunks_text = "\n\n".join(
                f"// {c['file_path']} — {c['chunk_name']}\n{c['chunk_text']}"
                for c in context_chunks
            )
            context_section = CONTEXT_SECTION_TEMPLATE.format(retrieved_chunks=chunks_text)

        prompt = REVIEW_USER_PROMPT.format(
            file_path=file_path,
            language=language,
            pr_title=pr_title,
            pr_body=pr_body or "(no description)",
            diff=diff + ("\n\n[DIFF TRUNCATED — file too large]" if truncated else ""),
            context_section=context_section,
        )

        try:
            message = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)

            result = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON for {file_path}: {e}")
            return {"comments": [], "file_summary": "Parse error.", "has_critical_issues": False}
        except Exception as e:
            logger.error(f"LLM call failed for {file_path}: {e}", exc_info=True)
            return {"comments": [], "file_summary": "Review failed.", "has_critical_issues": False}

        addition_lines = _extract_addition_lines(diff)
        valid_comments = [
            c for c in result.get("comments", [])
            if c.get("line") in addition_lines
        ]
        result["comments"] = valid_comments[:10]
        return result

    def review_pr(self, diff_result: DiffResult, pr_title: str, pr_body: str) -> list:
        all_comments = []
        for f in diff_result.files:
            result = self.review_file(f.filename, f.patch, pr_title, pr_body)
            for comment in result.get("comments", []):
                comment["file_path"] = f.filename
                all_comments.append(comment)

        all_comments.sort(key=lambda c: SEVERITY_ORDER.get(c.get("severity", "info"), 99))
        return all_comments[:25]

    def generate_summary(self, all_comments: list, diff_result: DiffResult) -> tuple[str, str]:
        severity_counts = {"critical": 0, "warning": 0, "suggestion": 0, "info": 0}
        for c in all_comments:
            sev = c.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        verdict = "APPROVE"
        if severity_counts["critical"] > 0:
            verdict = "REQUEST_CHANGES"
        elif severity_counts["warning"] > 3:
            verdict = "REQUEST_CHANGES"
        elif all_comments:
            verdict = "COMMENT"

        files_reviewed = len(diff_result.files)
        total_comments = len(all_comments)

        verdict_emoji = {"APPROVE": "✅", "REQUEST_CHANGES": "❌", "COMMENT": "💬"}[verdict]

        lines = [
            f"## {verdict_emoji} CodeSense Review",
            "",
            f"**Files reviewed:** {files_reviewed} | "
            f"**+{diff_result.total_additions}** / **-{diff_result.total_deletions}** lines",
            "",
            "### Issue Summary",
            f"| Severity | Count |",
            f"|----------|-------|",
            f"| 🔴 Critical | {severity_counts['critical']} |",
            f"| 🟠 Warning  | {severity_counts['warning']} |",
            f"| 🔵 Suggestion | {severity_counts['suggestion']} |",
            f"| ℹ️ Info | {severity_counts['info']} |",
            "",
        ]

        if total_comments == 0:
            lines.append("No issues found. The code looks good! ✨")
        elif verdict == "REQUEST_CHANGES":
            lines.append(
                f"Found **{total_comments} issue(s)** that should be addressed before merging. "
                "See inline comments for details."
            )
        else:
            lines.append(
                f"Found **{total_comments} suggestion(s)**. These are non-blocking improvements."
            )

        return "\n".join(lines), verdict

    def respond_to_thread(
        self,
        original_code: str,
        original_comment: str,
        thread_history: list,
        developer_message: str,
    ) -> str:
        # Build message list — must start with user role (Anthropic API requirement)
        messages = []
        for turn in thread_history:
            role = "user" if turn["role"] == "developer" else "assistant"
            messages.append({"role": role, "content": turn["content"]})
        messages.append({"role": "user", "content": developer_message})

        system = (
            "You are CodeSense, an expert code reviewer. You are in a conversation with a developer "
            "about a specific code issue you flagged. Be helpful, specific, and concise. "
            "If asked for a fix, provide a concrete corrected code block. "
            f"Your original review comment: {original_comment}\n\n"
            f"The code in question:\n\n```\n{original_code}\n```"
        )

        try:
            message = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                system=system,
                messages=messages,
            )
            return message.content[0].text.strip()
        except Exception as e:
            logger.error(f"Thread response failed: {e}", exc_info=True)
            return "Sorry, I encountered an error while generating a response. Please try again."
