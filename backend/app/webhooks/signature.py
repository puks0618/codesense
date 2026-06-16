import hashlib
import hmac


def verify_github_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    if not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        key=secret.encode(),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature_header)
