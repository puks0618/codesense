import asyncio
import json
import logging
from datetime import datetime, timezone

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


async def handle_issue_comment(payload: dict):
    logger.info("issue_comment handler — not yet implemented (Phase 5)")


async def handle_review_comment(payload: dict):
    logger.info("pull_request_review_comment handler — not yet implemented (Phase 5)")
