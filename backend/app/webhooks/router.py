import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.config import settings
from app.db.client import db_client
from app.github.client import GitHubClient
from app.github.models import PREvent
from app.reviewer.pipeline import ReviewPipeline
from app.webhooks.signature import verify_github_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks")


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    payload_bytes = await request.body()

    if not verify_github_signature(payload_bytes, x_hub_signature_256, settings.github_webhook_secret):
        logger.warning("Rejected webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(payload_bytes)
    action = payload.get("action", "")

    logger.info(f"GitHub event: {x_github_event} / action: {action}")

    if x_github_event == "pull_request" and action in ("opened", "synchronize"):
        background_tasks.add_task(handle_pull_request, payload)
    elif x_github_event == "pull_request" and action == "closed" and payload.get("pull_request", {}).get("merged"):
        background_tasks.add_task(handle_pr_merged, payload)
    elif x_github_event in ("installation", "installation_repositories") and action in ("created", "added"):
        background_tasks.add_task(handle_installation, payload)
    elif x_github_event == "issue_comment" and action == "created":
        background_tasks.add_task(handle_issue_comment, payload)
    elif x_github_event == "pull_request_review_comment" and action == "created":
        background_tasks.add_task(handle_review_comment, payload)
    elif x_github_event == "pull_request_review_comment" and action == "deleted":
        background_tasks.add_task(handle_review_comment_deleted, payload)
    elif x_github_event == "pull_request_review_comment_reaction" and action == "created":
        background_tasks.add_task(handle_reaction, payload)
    else:
        logger.info(f"Ignoring unhandled event: {x_github_event}/{action}")

    return {"status": "ok"}


async def handle_pull_request(payload: dict):
    repo_full_name = payload["repository"]["full_name"]
    pr_number = payload["pull_request"]["number"]
    installation_id = payload["installation"]["id"]
    commit_sha = payload["pull_request"]["head"]["sha"]
    pr_title = payload["pull_request"]["title"]
    pr_body = payload["pull_request"].get("body") or ""

    logger.info(f"Reviewing PR #{pr_number} on {repo_full_name} @ {commit_sha[:8]}")

    review_doc = {
        "repo_full_name": repo_full_name,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "commit_sha": commit_sha,
        "status": "pending",
        "comments": [],
        "summary": "",
        "overall_score": 0,
        "review_duration_ms": 0,
        "created_at": datetime.now(timezone.utc),
    }
    review_id = None

    try:
        reviews_col = db_client.get_collection("reviews")
        insert_result = await reviews_col.insert_one(review_doc)
        review_id = insert_result.inserted_id
    except Exception:
        logger.warning("MongoDB unavailable — proceeding without persistence")

    client = GitHubClient(installation_id)

    try:
        start_ms = _now_ms()

        diff_result = await client.get_pr_diff(repo_full_name, pr_number)
        logger.info(f"PR #{pr_number}: {len(diff_result.files)} reviewable files, "
                    f"+{diff_result.total_additions}/-{diff_result.total_deletions} lines")

        if not diff_result.files:
            await client.post_comment(repo_full_name, pr_number,
                                      "**CodeSense**: No reviewable files found in this PR.")
            return

        # Cap at 20 files (largest by additions first) if over 100
        files = diff_result.files
        if len(files) > 100:
            files = sorted(files, key=lambda f: f.additions, reverse=True)[:20]
            await client.post_comment(
                repo_full_name, pr_number,
                "**CodeSense**: This PR has over 100 changed files. "
                "Reviewing the 20 largest files by additions only."
            )
            from app.github.models import DiffResult
            diff_result = DiffResult(
                files=files,
                total_additions=sum(f.additions for f in files),
                total_deletions=sum(f.deletions for f in files),
            )

        pr_event = PREvent(
            pr_number=pr_number,
            repo_full_name=repo_full_name,
            installation_id=installation_id,
            head_sha=commit_sha,
            base_sha=payload["pull_request"]["base"]["sha"],
            pr_title=pr_title,
            pr_body=pr_body,
            author_login=payload["pull_request"]["user"]["login"],
        )

        pipeline = ReviewPipeline()
        result = await pipeline.run(pr_event, diff_result)
        all_comments = result["comments"]
        summary = result["summary"]
        verdict = result["verdict"]

        duration_ms = _now_ms() - start_ms
        logger.info(f"PR #{pr_number}: {len(all_comments)} comments, verdict={verdict}, "
                    f"duration={duration_ms}ms")

        # Format comments for GitHub PR review
        github_comments = []
        for c in all_comments:
            severity_prefix = {
                "critical": "🔴 **Critical**",
                "warning": "🟠 **Warning**",
                "suggestion": "🔵 **Suggestion**",
                "info": "ℹ️ **Info**",
            }.get(c.get("severity", "info"), "ℹ️ **Info**")

            body = (
                f"{severity_prefix} [{c.get('category', 'style').upper()}]: "
                f"**{c.get('title', '')}**\n\n{c.get('body', '')}"
            )
            github_comments.append({
                "path": c["file_path"],
                "line": c["line"],
                "body": body,
            })

        await client.post_review(
            repo_full_name, pr_number, commit_sha,
            github_comments, summary, verdict
        )
        logger.info(f"Posted review on PR #{pr_number}")

        # Persist completed review
        if review_id is not None:
            try:
                await reviews_col.update_one(
                    {"_id": review_id},
                    {"$set": {
                        "status": "completed",
                        "comments": all_comments,
                        "summary": summary,
                        "review_duration_ms": duration_ms,
                    }}
                )
            except Exception:
                logger.warning("Failed to update review status in MongoDB")

    except Exception as e:
        logger.error(f"Review failed for PR #{pr_number}: {e}", exc_info=True)
        try:
            await client.post_comment(
                repo_full_name, pr_number,
                f"**CodeSense**: Review failed with an unexpected error. "
                f"The team has been notified.\n\n`{type(e).__name__}: {e}`"
            )
        except Exception:
            pass

        if review_id is not None:
            try:
                await reviews_col.update_one(
                    {"_id": review_id},
                    {"$set": {"status": "failed"}}
                )
            except Exception:
                pass


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)


async def handle_installation(payload: dict):
    try:
        from app.indexer.parser import RepositoryIndexer
        installation_id = payload["installation"]["id"]
        repos = payload.get("repositories") or payload.get("repositories_added", [])
        client = GitHubClient(installation_id)
        indexer = RepositoryIndexer()
        for repo in repos:
            repo_full_name = repo["full_name"]
            logger.info(f"Indexing newly installed repo: {repo_full_name}")
            try:
                summary = await indexer.index_repository(repo_full_name, client)
                logger.info(f"Indexing complete for {repo_full_name}: {summary}")
            except Exception as e:
                logger.error(f"Indexing failed for {repo_full_name}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"handle_installation failed: {e}", exc_info=True)


async def handle_pr_merged(payload: dict):
    try:
        from app.indexer.parser import RepositoryIndexer
        repo_full_name = payload["repository"]["full_name"]
        pr_number = payload["pull_request"]["number"]
        installation_id = payload["installation"]["id"]
        logger.info(f"PR #{pr_number} merged on {repo_full_name} — updating index")
        client = GitHubClient(installation_id)
        diff_result = await client.get_pr_diff(repo_full_name, pr_number)
        indexer = RepositoryIndexer()
        await indexer.index_pr_changes(repo_full_name, diff_result.files, client)
        logger.info(f"Index updated for {repo_full_name} after PR #{pr_number} merge")
    except Exception as e:
        logger.error(f"handle_pr_merged failed: {e}", exc_info=True)


async def handle_review_comment(payload: dict):
    try:
        comment = payload["comment"]
        comment_id: int = comment["id"]
        comment_body: str = comment["body"]
        comment_login: str = comment["user"]["login"]
        in_reply_to_id: Optional[int] = comment.get("in_reply_to_id")
        file_path: str = comment.get("path", "")
        diff_hunk: str = comment.get("diff_hunk", "")
        pr_number: int = payload["pull_request"]["number"]
        repo_full_name: str = payload["repository"]["full_name"]
        installation_id: int = payload["installation"]["id"]

        bot_login = f"{settings.github_app_slug}[bot]"

        # When our own bot posts a review comment, GitHub sends us a webhook for it.
        # Store it in threads so developers can reply to it.
        if comment_login == bot_login:
            if in_reply_to_id is None:
                # Top-level CodeSense comment — seed the thread
                try:
                    threads_col = db_client.get_collection("threads")
                    await threads_col.update_one(
                        {"github_comment_id": comment_id},
                        {"$setOnInsert": {
                            "github_comment_id": comment_id,
                            "repo_full_name": repo_full_name,
                            "pr_number": pr_number,
                            "file_path": file_path,
                            "original_code_context": diff_hunk,
                            "original_comment": comment_body,
                            "turns": [],
                            "created_at": datetime.now(timezone.utc),
                        }},
                        upsert=True,
                    )
                    logger.info(f"Stored thread seed for comment {comment_id} on {repo_full_name}#{pr_number}")
                except Exception as e:
                    logger.error(f"Failed to store thread seed: {e}", exc_info=True)
            return  # Never respond to our own comments

        # Developer comment — only handle replies to our comments
        if in_reply_to_id is None:
            # Top-level human comment on a PR CodeSense reviewed — ingest as team style
            await _ingest_team_style_comment(
                repo_full_name, pr_number, comment_id, diff_hunk, comment_body, comment_login
            )
            return

        try:
            threads_col = db_client.get_collection("threads")
            thread = await threads_col.find_one({"github_comment_id": in_reply_to_id})
        except Exception as e:
            logger.error(f"Thread lookup failed: {e}", exc_info=True)
            return

        if thread is None:
            logger.debug(f"Comment {in_reply_to_id} is not a CodeSense thread — ignoring")
            return

        # Developer is replying to one of our comments — respond
        from app.llm.reviewer import LLMReviewer
        reviewer = LLMReviewer()
        try:
            response_text = await asyncio.to_thread(
                reviewer.respond_to_thread,
                thread["original_code_context"],
                thread["original_comment"],
                thread.get("turns", []),
                comment_body,
            )
        except Exception as e:
            logger.error(f"respond_to_thread failed: {e}", exc_info=True)
            return

        # Post the reply to GitHub
        client = GitHubClient(installation_id)
        try:
            reply = await client.post_review_comment_reply(
                repo_full_name, pr_number, comment_id, response_text
            )
            reply_comment_id = reply.get("id")
        except Exception as e:
            logger.error(f"Failed to post reply comment: {e}", exc_info=True)
            return

        # Update thread turns
        now = datetime.now(timezone.utc)
        new_turns = [
            {"role": "developer", "content": comment_body, "github_comment_id": comment_id, "created_at": now},
            {"role": "codesense", "content": response_text, "github_comment_id": reply_comment_id, "created_at": now},
        ]
        try:
            await threads_col.update_one(
                {"github_comment_id": in_reply_to_id},
                {"$push": {"turns": {"$each": new_turns}}},
            )
        except Exception as e:
            logger.error(f"Failed to update thread turns: {e}", exc_info=True)

        logger.info(f"Responded to thread {in_reply_to_id} on {repo_full_name}#{pr_number}")

    except Exception as e:
        logger.error(f"handle_review_comment failed: {e}", exc_info=True)


async def handle_issue_comment(payload: dict):
    try:
        comment = payload["comment"]
        comment_login: str = comment["user"]["login"]
        bot_login = f"{settings.github_app_slug}[bot]"

        if comment_login == bot_login:
            return  # Prevent infinite loops

        # Issue comments are general PR comments — no thread lookup (no in_reply_to_id)
        logger.info(
            f"issue_comment by {comment_login} on "
            f"{payload['repository']['full_name']} — no thread action"
        )
    except Exception as e:
        logger.error(f"handle_issue_comment failed: {e}", exc_info=True)


async def _ingest_team_style_comment(
    repo_full_name: str,
    pr_number: int,
    comment_id: int,
    diff_hunk: str,
    comment_body: str,
    reviewer_login: str,
) -> None:
    """Store a human review comment as a team style example if CodeSense reviewed this PR."""
    try:
        reviews_col = db_client.get_collection("reviews")
        review = await reviews_col.find_one(
            {"repo_full_name": repo_full_name, "pr_number": pr_number}
        )
        if review is None:
            logger.debug(
                f"Skipping team style ingestion for {repo_full_name}#{pr_number} — no CodeSense review"
            )
            return

        # Use the last 10 lines of the diff hunk as the code context
        hunk_lines = diff_hunk.strip().split("\n")
        code_context = "\n".join(hunk_lines[-10:])

        from app.indexer.embedder import EmbeddingGenerator
        embedder = EmbeddingGenerator()
        try:
            embedding = await asyncio.to_thread(embedder.embed_single, code_context)
        except Exception as e:
            logger.error(f"Failed to embed team style comment: {e}")
            return

        team_style_col = db_client.get_collection("team_style")
        await team_style_col.update_one(
            {"github_comment_id": comment_id},
            {"$setOnInsert": {
                "github_comment_id": comment_id,
                "repo_full_name": repo_full_name,
                "pr_number": pr_number,
                "code_context": code_context,
                "comment_body": comment_body,
                "reviewer_login": reviewer_login,
                "embedding": embedding,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        logger.info(
            f"Ingested team style comment {comment_id} from {reviewer_login} on {repo_full_name}#{pr_number}"
        )
    except Exception as e:
        logger.error(f"Team style ingestion failed: {e}", exc_info=True)


async def handle_review_comment_deleted(payload: dict):
    """Track deleted CodeSense comments as implicit negative feedback."""
    try:
        comment = payload["comment"]
        comment_id: int = comment["id"]
        repo_full_name: str = payload["repository"]["full_name"]

        threads_col = db_client.get_collection("threads")
        thread = await threads_col.find_one({"github_comment_id": comment_id})
        if thread is None:
            return  # Not a CodeSense comment — nothing to track

        reactor_login: str = payload.get("sender", {}).get("login", "")
        feedback_col = db_client.get_collection("comment_feedback")
        await feedback_col.update_one(
            {"github_comment_id": comment_id, "reaction": "deleted"},
            {"$setOnInsert": {
                "github_comment_id": comment_id,
                "repo_full_name": repo_full_name,
                "reaction": "deleted",
                "reactor_login": reactor_login,
                "category": None,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        logger.info(f"Recorded deletion of CodeSense comment {comment_id} on {repo_full_name}")
        await _check_negative_signal_threshold(repo_full_name, feedback_col)
    except Exception as e:
        logger.error(f"handle_review_comment_deleted failed: {e}", exc_info=True)


async def handle_reaction(payload: dict):
    """Track 👎 reactions on CodeSense comments for quality feedback.

    Requires the GitHub App to have 'Reactions' Read permission and the
    pull_request_review_comment_reaction webhook event subscribed.
    """
    try:
        if payload.get("action") != "created":
            return

        reaction_content: str = payload.get("reaction", {}).get("content", "")
        if reaction_content != "-1":
            return  # Only track thumbs-down

        comment = payload.get("pull_request_review_comment") or payload.get("comment", {})
        comment_id: int = comment.get("id")
        if not comment_id:
            return

        repo_full_name: str = payload["repository"]["full_name"]
        reactor_login: str = payload.get("reaction", {}).get("user", {}).get("login", "")

        threads_col = db_client.get_collection("threads")
        thread = await threads_col.find_one({"github_comment_id": comment_id})
        if thread is None:
            return  # Not a CodeSense comment

        # Best-effort: look up the comment's category from stored reviews
        category: Optional[str] = None
        try:
            reviews_col = db_client.get_collection("reviews")
            pr_number: int = thread.get("pr_number")
            review = await reviews_col.find_one(
                {"repo_full_name": repo_full_name, "pr_number": pr_number}
            )
            if review:
                for c in review.get("comments", []):
                    if c.get("github_comment_id") == comment_id:
                        category = c.get("category")
                        break
        except Exception:
            pass

        feedback_col = db_client.get_collection("comment_feedback")
        await feedback_col.update_one(
            {"github_comment_id": comment_id, "reaction": "-1", "reactor_login": reactor_login},
            {"$setOnInsert": {
                "github_comment_id": comment_id,
                "repo_full_name": repo_full_name,
                "reaction": "-1",
                "reactor_login": reactor_login,
                "category": category,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        logger.info(f"Recorded 👎 on CodeSense comment {comment_id} from {reactor_login}")
        await _check_negative_signal_threshold(repo_full_name, feedback_col, category=category)
    except Exception as e:
        logger.error(f"handle_reaction failed: {e}", exc_info=True)


async def _check_negative_signal_threshold(
    repo_full_name: str, feedback_col, category: Optional[str] = None
) -> None:
    """Log a warning when 5+ thumbs-down accumulate for a repo (optionally per category)."""
    try:
        query: dict = {"repo_full_name": repo_full_name, "reaction": "-1"}
        if category:
            query["category"] = category
        count = await feedback_col.count_documents(query)
        if count >= 5:
            cat_msg = f" for category '{category}'" if category else ""
            logger.warning(
                f"Quality signal: {count} negative reactions on {repo_full_name}{cat_msg}. "
                "Consider adjusting review sensitivity for this category."
            )
    except Exception as e:
        logger.error(f"Negative signal threshold check failed: {e}", exc_info=True)
