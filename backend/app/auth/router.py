import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth")


def _create_session_jwt(github_login: str, github_token: str) -> str:
    payload = {
        "sub": github_login,
        "github_token": github_token,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


@router.get("/github")
async def github_login():
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        "&scope=read:user"
    )
    return RedirectResponse(url=url)


@router.get("/github/callback")
async def github_callback(code: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()

    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data.get("error_description", "GitHub OAuth failed"))

    github_token = data["access_token"]

    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=30,
        )
        user_resp.raise_for_status()

    user = user_resp.json()
    session_jwt = _create_session_jwt(user["login"], github_token)

    frontend_url = settings.frontend_url or "http://localhost:3000"
    return RedirectResponse(url=f"{frontend_url}/?token={session_jwt}")


@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"login": payload["sub"]}
