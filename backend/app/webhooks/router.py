import json
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.config import settings
from app.github.client import GitHubClient
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
    elif x_github_event == "issue_comment" and action == "created":
        background_tasks.add_task(handle_issue_comment, payload)
    elif x_github_event == "pull_request_review_comment" and action == "created":
        background_tasks.add_task(handle_review_comment, payload)
    else:
        logger.info(f"Ignoring unhandled event: {x_github_event}/{action}")

    return {"status": "ok"}


async def handle_pull_request(payload: dict):
    try:
        repo_full_name = payload["repository"]["full_name"]
        pr_number = payload["pull_request"]["number"]
        installation_id = payload["installation"]["id"]

        logger.info(f"Handling PR #{pr_number} on {repo_full_name}")

        client = GitHubClient(installation_id)
        diff_result = await client.get_pr_diff(repo_full_name, pr_number)

        logger.info(f"PR #{pr_number}: {len(diff_result.files)} reviewable files, "
                    f"+{diff_result.total_additions}/-{diff_result.total_deletions} lines")

        await client.post_comment(
            repo_full_name,
            pr_number,
            "**CodeSense** is analyzing this PR. Review will appear shortly.",
        )

        logger.info(f"Posted stub comment on PR #{pr_number}")

    except Exception as e:
        logger.error(f"Error in handle_pull_request: {e}", exc_info=True)


async def handle_issue_comment(payload: dict):
    logger.info("issue_comment handler — not yet implemented (Phase 5)")


async def handle_review_comment(payload: dict):
    logger.info("pull_request_review_comment handler — not yet implemented (Phase 5)")
