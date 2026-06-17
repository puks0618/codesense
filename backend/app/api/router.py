import logging
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.db.client import db_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


async def _get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/repos")
async def list_repos(user: dict = Depends(_get_current_user)):
    reviews_col = db_client.get_collection("reviews")
    cursor = reviews_col.aggregate([
        {"$group": {
            "_id": "$repo_full_name",
            "review_count": {"$sum": 1},
            "last_reviewed_at": {"$max": "$created_at"},
        }},
        {"$sort": {"last_reviewed_at": -1}},
        {"$limit": 50},
    ])
    repos = await cursor.to_list(length=50)
    return [
        {
            "repo_full_name": r["_id"],
            "review_count": r["review_count"],
            "last_reviewed_at": r["last_reviewed_at"].isoformat() if r.get("last_reviewed_at") else None,
        }
        for r in repos
    ]


@router.get("/repos/{owner}/{repo}/reviews")
async def list_repo_reviews(owner: str, repo: str, user: dict = Depends(_get_current_user)):
    repo_full_name = f"{owner}/{repo}"
    reviews_col = db_client.get_collection("reviews")
    cursor = reviews_col.find(
        {"repo_full_name": repo_full_name},
        {"_id": 0, "pr_number": 1, "pr_title": 1, "status": 1, "verdict": 1,
         "summary": 1, "review_duration_ms": 1, "created_at": 1, "comments": 1},
    ).sort("created_at", -1).limit(50)
    reviews = await cursor.to_list(length=50)
    result = []
    for r in reviews:
        r["comment_count"] = len(r.pop("comments", []))
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
        result.append(r)
    return result


@router.get("/repos/{owner}/{repo}/reviews/{pr_number}")
async def get_review(owner: str, repo: str, pr_number: int, user: dict = Depends(_get_current_user)):
    repo_full_name = f"{owner}/{repo}"
    reviews_col = db_client.get_collection("reviews")
    review = await reviews_col.find_one(
        {"repo_full_name": repo_full_name, "pr_number": pr_number},
        {"_id": 0},
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.get("created_at"):
        review["created_at"] = review["created_at"].isoformat()
    return review


@router.get("/repos/{owner}/{repo}/metrics")
async def get_metrics(owner: str, repo: str, user: dict = Depends(_get_current_user)):
    repo_full_name = f"{owner}/{repo}"
    reviews_col = db_client.get_collection("reviews")

    agg_cursor = reviews_col.aggregate([
        {"$match": {"repo_full_name": repo_full_name, "status": "completed"}},
        {"$project": {
            "comment_count": {"$size": {"$ifNull": ["$comments", []]}},
            "review_duration_ms": 1,
        }},
        {"$group": {
            "_id": None,
            "total_reviews": {"$sum": 1},
            "avg_comments_per_pr": {"$avg": "$comment_count"},
            "avg_duration_ms": {"$avg": "$review_duration_ms"},
        }},
    ])
    totals_list = await agg_cursor.to_list(length=1)
    totals = totals_list[0] if totals_list else {}

    category_cursor = reviews_col.aggregate([
        {"$match": {"repo_full_name": repo_full_name, "status": "completed"}},
        {"$unwind": "$comments"},
        {"$group": {"_id": "$comments.category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ])
    categories = await category_cursor.to_list(length=20)

    file_cursor = reviews_col.aggregate([
        {"$match": {"repo_full_name": repo_full_name, "status": "completed"}},
        {"$unwind": "$comments"},
        {"$group": {"_id": "$comments.file_path", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ])
    files = await file_cursor.to_list(length=10)

    return {
        "total_reviews": totals.get("total_reviews", 0),
        "avg_comments_per_pr": round(totals.get("avg_comments_per_pr", 0) or 0, 1),
        "avg_review_duration_ms": round(totals.get("avg_duration_ms", 0) or 0),
        "issues_by_category": [{"category": r["_id"], "count": r["count"]} for r in categories],
        "top_flagged_files": [{"file_path": r["_id"], "count": r["count"]} for r in files],
    }
