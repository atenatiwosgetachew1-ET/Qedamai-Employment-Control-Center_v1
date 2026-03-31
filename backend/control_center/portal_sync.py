import json
import os
import time
from base64 import b64encode
from urllib import error, request

from cryptography.hazmat.primitives import serialization


def _sync_base_url(base_url: str = "") -> str:
    preferred = (base_url or "").strip()
    if preferred:
        return preferred.rstrip("/")
    return (os.getenv("CUSTOMER_PORTAL_SYNC_BASE_URL") or "").rstrip("/")


def sync_is_configured(base_url: str = "") -> bool:
    return bool(_sync_base_url(base_url))


def _signed_headers(body: bytes, *, key_id: str, private_key_pem: str) -> dict[str, str]:
    timestamp = str(int(time.time()))
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    signature = private_key.sign(timestamp.encode("utf-8") + b"." + body)
    return {
        "Content-Type": "application/json",
        "X-Portal-Sync-Key": key_id,
        "X-Portal-Sync-Timestamp": timestamp,
        "X-Portal-Sync-Algorithm": "ed25519",
        "X-Portal-Sync-Signature": b64encode(signature).decode("ascii"),
    }


def post_sync(path: str, payload: dict, *, key_id: str, private_key_pem: str, base_url: str = "") -> tuple[bool, str]:
    target_base_url = _sync_base_url(base_url)
    if not target_base_url:
        return False, "Customer portal sync base URL is not configured."

    body = json.dumps(payload).encode("utf-8")
    target = f"{target_base_url}{path}"
    req = request.Request(target, data=body, method="POST")
    for key, value in _signed_headers(body, key_id=key_id, private_key_pem=private_key_pem).items():
        req.add_header(key, value)

    try:
        with request.urlopen(req, timeout=15) as response:
            response.read()
        return True, ""
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        if "<!DOCTYPE" in response_body or "<html" in response_body.lower():
            return False, f"HTTP {exc.code}: endpoint not found or returned HTML at {target}"
        return False, f"HTTP {exc.code}: {response_body}"
    except Exception as exc:
        return False, str(exc)
