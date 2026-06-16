import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.webhooks.signature import verify_github_signature

SECRET = "test-webhook-secret"


def make_signature(payload: bytes, secret: str = SECRET) -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ---------------------------------------------------------------------------
# Signature verification tests
# ---------------------------------------------------------------------------

def test_signature_valid():
    payload = b'{"action": "opened"}'
    sig = make_signature(payload)
    assert verify_github_signature(payload, sig, SECRET) is True


def test_signature_wrong_secret():
    payload = b'{"action": "opened"}'
    sig = make_signature(payload, secret="wrong-secret")
    assert verify_github_signature(payload, sig, SECRET) is False


def test_signature_missing_header():
    payload = b'{"action": "opened"}'
    assert verify_github_signature(payload, None, SECRET) is False


def test_signature_malformed_header():
    payload = b'{"action": "opened"}'
    assert verify_github_signature(payload, "md5=abc123", SECRET) is False


# ---------------------------------------------------------------------------
# Webhook endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _headers(payload: bytes, event: str = "ping") -> dict:
    return {
        "X-Hub-Signature-256": make_signature(payload),
        "X-GitHub-Event": event,
        "Content-Type": "application/json",
    }


def test_webhook_invalid_signature(client):
    payload = json.dumps({"action": "opened"}).encode()
    resp = client.post(
        "/webhooks/github",
        content=payload,
        headers={
            "X-Hub-Signature-256": "sha256=invalidsig",
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


def test_webhook_unknown_event_returns_200(client):
    payload = json.dumps({"zen": "hello"}).encode()
    resp = client.post("/webhooks/github", content=payload, headers=_headers(payload, "ping"))
    assert resp.status_code == 200


def test_webhook_pull_request_opened_triggers_handler(client):
    payload = json.dumps({
        "action": "opened",
        "pull_request": {
            "number": 1,
            "head": {"sha": "abc123"},
            "base": {"sha": "def456"},
            "title": "Test PR",
            "body": "",
            "user": {"login": "testuser"},
        },
        "repository": {"full_name": "owner/repo"},
        "installation": {"id": 99},
    }).encode()

    with patch("app.webhooks.router.handle_pull_request", new_callable=AsyncMock) as mock_handler:
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers=_headers(payload, "pull_request"),
        )
        assert resp.status_code == 200
