"""Wallet sign-in (Sign-In With Solana style) and stateless session tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from solders.pubkey import Pubkey
from solders.signature import Signature


class AuthError(ValueError):
    pass


def new_nonce() -> str:
    return secrets.token_urlsafe(24)


def sign_in_message(wallet: str, nonce: str, issued_at: int) -> str:
    stamp = datetime.fromtimestamp(issued_at, tz=timezone.utc).isoformat()
    return (
        "Sigil wants you to sign in with your Solana account:\n"
        f"{wallet}\n\n"
        "This request does not send a transaction or cost a fee.\n\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {stamp}"
    )


def verify_signature(wallet: str, message: str, signature_b58: str) -> None:
    try:
        pubkey_bytes = bytes(Pubkey.from_string(wallet))
        signature_bytes = bytes(Signature.from_string(signature_b58))
    except Exception as exc:  # solders raises several parse errors
        raise AuthError("wallet or signature is not valid base58") from exc
    try:
        VerifyKey(pubkey_bytes).verify(message.encode("utf-8"), signature_bytes)
    except BadSignatureError as exc:
        raise AuthError("signature does not match this wallet and message") from exc


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_token(wallet: str, secret: str, ttl_seconds: int) -> tuple[str, int]:
    expires_at = int(time.time()) + ttl_seconds
    payload = _b64(json.dumps({"w": wallet, "exp": expires_at}).encode("utf-8"))
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}", expires_at


def read_token(token: str, secret: str) -> str | None:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        data = json.loads(_unb64(payload))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("exp", 0) < time.time():
        return None
    wallet = data.get("w")
    return wallet if isinstance(wallet, str) else None
