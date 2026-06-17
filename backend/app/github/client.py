import asyncio
import logging
import time
from typing import Optional

import httpx
import jwt

from app.config import settings
from app.github.models import ChangedFile, DiffResult

logger = logging.getLogger(__name__)

SKIP_FILENAMES = {"package-lock.json", "yarn.lock", "Pipfile.lock", "poetry.lock", "pnpm-lock.yaml"}
SKIP_EXTENSIONS = (".min.js", ".map", ".lock")


class GitHubClient:
    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self._token: Optional[str] = None
        self._token_expires_at: float = 0

    def _generate_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 540,  # 9 minutes (max is 10)
            "iss": str(settings.github_app_id),  # PyJWT requires string
        }
        return jwt.encode(payload, settings.github_private_key, algorithm="RS256")

    async def _get_installation_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token

        app_jwt = self._generate_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{self.installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=30,
            )
            resp.raise_for_status()

        data = resp.json()
        self._token = data["token"]
        self._token_expires_at = time.time() + 3500
        logger.info(f"Obtained installation token for installation {self.installation_id}")
        return self._token

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        token = await self._get_installation_token()
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        })

        for attempt in range(3):
            async with httpx.AsyncClient() as client:
                resp = await client.request(method, url, headers=headers, timeout=30, **kwargs)

            if resp.status_code in (403, 429):
                retry_after = int(resp.headers.get("retry-after", 60))
                logger.warning(f"Rate limited on {url}. Retrying after {retry_after}s (attempt {attempt + 1})")
                if attempt < 2:
                    await asyncio.sleep(retry_after)
                    continue

            return resp

        return resp

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> DiffResult:
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"
        resp = await self._request("GET", url, params={"per_page": 100})
        resp.raise_for_status()

        files = []
        for f in resp.json():
            filename: str = f["filename"]

            if filename.split("/")[-1] in SKIP_FILENAMES:
                logger.debug(f"Skipping lock file: {filename}")
                continue
            if any(filename.endswith(ext) for ext in SKIP_EXTENSIONS):
                logger.debug(f"Skipping minified/map file: {filename}")
                continue
            if f.get("status") == "removed":
                continue
            if not f.get("patch"):
                continue

            files.append(ChangedFile(
                filename=filename,
                status=f["status"],
                patch=f.get("patch", ""),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
            ))

        return DiffResult(
            files=files,
            total_additions=sum(f.additions for f in files),
            total_deletions=sum(f.deletions for f in files),
        )

    async def post_review(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_sha: str,
        comments: list,
        summary: str,
        verdict: str,
    ) -> dict:
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
        resp = await self._request("POST", url, json={
            "commit_id": commit_sha,
            "body": summary,
            "event": verdict,
            "comments": comments,
        })
        resp.raise_for_status()
        logger.info(f"Posted review on {repo_full_name}#{pr_number} verdict={verdict}")
        return resp.json()

    async def post_comment(self, repo_full_name: str, pr_number: int, body: str) -> dict:
        url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
        resp = await self._request("POST", url, json={"body": body})
        resp.raise_for_status()
        logger.info(f"Posted comment on {repo_full_name}#{pr_number}")
        return resp.json()

    async def get_pr_comments(self, repo_full_name: str, pr_number: int) -> list:
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/comments"
        resp = await self._request("GET", url)
        resp.raise_for_status()
        return resp.json()

    async def post_review_comment_reply(
        self, repo_full_name: str, pr_number: int, comment_id: int, body: str
    ) -> dict:
        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/comments/{comment_id}/replies"
        resp = await self._request("POST", url, json={"body": body})
        resp.raise_for_status()
        logger.info(f"Posted reply to comment {comment_id} on {repo_full_name}#{pr_number}")
        return resp.json()
