from pydantic import BaseModel


class ChangedFile(BaseModel):
    filename: str
    status: str
    patch: str = ""
    additions: int = 0
    deletions: int = 0


class DiffResult(BaseModel):
    files: list[ChangedFile]
    total_additions: int
    total_deletions: int


class PREvent(BaseModel):
    pr_number: int
    repo_full_name: str
    installation_id: int
    head_sha: str
    base_sha: str
    pr_title: str
    pr_body: str
    author_login: str
