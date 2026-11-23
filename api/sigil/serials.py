"""Unit serials.

A serial is 10 random bytes (80 bits) from the operating system CSPRNG,
shown to humans as 16 uppercase base32 characters (RFC 4648, no padding).
Serials are public. The randomness only stops someone guessing a registered one.
"""

from __future__ import annotations

import base64
import re
import secrets

SERIAL_BYTES = 10
SERIAL_CHARS = 16
_SERIAL_RE = re.compile(r"^[A-Z2-7]{16}$")


class SerialError(ValueError):
    pass


def generate_serial() -> bytes:
    return secrets.token_bytes(SERIAL_BYTES)


def encode_serial(raw: bytes) -> str:
    if len(raw) != SERIAL_BYTES:
        raise SerialError(f"serial must be {SERIAL_BYTES} bytes, got {len(raw)}")
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def decode_serial(text: str) -> bytes:
    if not isinstance(text, str) or not _SERIAL_RE.match(text):
        raise SerialError("serial must be 16 characters from A-Z and 2-7")
    return base64.b32decode(text)


def is_valid_serial(text: str) -> bool:
    try:
        decode_serial(text)
    except SerialError:
        return False
    return True
