"""Canonical JSON encoding used for on-chain details commitments.

Rules:
- object keys sorted
- no insignificant whitespace
- UTF-8, non-ASCII characters kept as-is
- floats are rejected: use ints or strings so every language hashes the same bytes
"""

from __future__ import annotations

import json
from typing import Any


class CanonicalJSONError(ValueError):
    pass


def _check(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise CanonicalJSONError(
            f"{path}: floats are not allowed in canonical JSON; send numbers as strings"
        )
    if isinstance(value, list):
        for i, item in enumerate(value):
            _check(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalJSONError(f"{path}: object keys must be strings")
            _check(item, f"{path}.{key}")
        return
    raise CanonicalJSONError(f"{path}: unsupported type {type(value).__name__}")


def canonical_json(value: Any) -> str:
    _check(value, "$")
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")
