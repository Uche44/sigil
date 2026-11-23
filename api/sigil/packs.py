"""Industry packs: per-industry field lists and shopper copy, loaded from JSON.

Adding an industry must only need a new JSON file in /packs. No code change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import json

FIELD_TYPES = {"text", "date", "number", "photo"}
DEFAULT_PACKS_DIR = Path(__file__).resolve().parents[2] / "packs"
MAX_TEXT = 500
MAX_PHOTO_REF = 1000


class PackError(ValueError):
    pass


class DetailsError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: str
    required: bool


@dataclass(frozen=True)
class Pack:
    id: str
    name: str
    industry_code: int
    expiry_required: bool
    fields: tuple[Field, ...]
    checklist: tuple[str, ...]


def _parse_pack(raw: dict, source: Path) -> Pack:
    def fail(message: str) -> None:
        raise PackError(f"{source.name}: {message}")

    for key in ("id", "name", "industry_code", "expiry_required", "fields", "checklist"):
        if key not in raw:
            fail(f"missing {key}")
    if not isinstance(raw["industry_code"], int) or not 0 <= raw["industry_code"] <= 255:
        fail("industry_code must be a u8")
    if not isinstance(raw["expiry_required"], bool):
        fail("expiry_required must be a bool")
    if not raw["fields"]:
        fail("fields must not be empty")
    if not raw["checklist"]:
        fail("checklist must not be empty")

    fields: list[Field] = []
    seen: set[str] = set()
    for item in raw["fields"]:
        if item.get("type") not in FIELD_TYPES:
            fail(f"field {item.get('key')!r} has unknown type")
        if item.get("key") in seen:
            fail(f"duplicate field {item.get('key')!r}")
        seen.add(item["key"])
        fields.append(
            Field(
                key=item["key"],
                label=item["label"],
                type=item["type"],
                required=bool(item["required"]),
            )
        )
    return Pack(
        id=raw["id"],
        name=raw["name"],
        industry_code=raw["industry_code"],
        expiry_required=raw["expiry_required"],
        fields=tuple(fields),
        checklist=tuple(str(line) for line in raw["checklist"]),
    )


def load_packs(directory: Path | str | None = None) -> dict[str, Pack]:
    path = Path(directory or os.environ.get("SIGIL_PACKS_DIR") or DEFAULT_PACKS_DIR)
    if not path.is_dir():
        raise PackError(f"packs directory not found: {path}")
    packs: dict[str, Pack] = {}
    codes: dict[int, str] = {}
    for file in sorted(path.glob("*.json")):
        pack = _parse_pack(json.loads(file.read_text(encoding="utf-8")), file)
        if pack.id in packs:
            raise PackError(f"duplicate pack id {pack.id!r}")
        if pack.industry_code in codes:
            raise PackError(f"industry_code {pack.industry_code} used twice")
        packs[pack.id] = pack
        codes[pack.industry_code] = pack.id
    if not packs:
        raise PackError(f"no packs in {path}")
    return packs


def pack_by_code(packs: dict[str, Pack], code: int) -> Pack | None:
    for pack in packs.values():
        if pack.industry_code == code:
            return pack
    return None


def _normalise_value(field: Field, value: Any) -> Any:
    if field.type == "text":
        text = str(value).strip()
        if not text:
            raise ValueError("must not be empty")
        if len(text) > MAX_TEXT:
            raise ValueError(f"must be at most {MAX_TEXT} characters")
        return text
    if field.type == "date":
        try:
            parsed = date.fromisoformat(str(value))
        except ValueError as exc:
            raise ValueError("must be a date in YYYY-MM-DD form") from exc
        return parsed.isoformat()
    if field.type == "number":
        if isinstance(value, bool):
            raise ValueError("must be a number")
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("must be a number") from exc
        if not number.is_finite() or number <= 0:
            raise ValueError("must be a positive number")
        return format(number.normalize(), "f")
    if field.type == "photo":
        ref = str(value).strip()
        if not ref:
            raise ValueError("must not be empty")
        if len(ref) > MAX_PHOTO_REF:
            raise ValueError("reference is too long")
        return ref
    raise ValueError("unknown field type")


def validate_details(pack: Pack, details: dict) -> dict:
    if not isinstance(details, dict):
        raise DetailsError({"$": "details must be an object"})

    errors: dict[str, str] = {}
    known = {field.key for field in pack.fields}
    for key in details:
        if key not in known:
            errors[key] = "not a field in this industry pack"

    cleaned: dict[str, Any] = {}
    for field in pack.fields:
        value = details.get(field.key)
        absent = value is None or (isinstance(value, str) and not value.strip())
        if absent:
            if field.required:
                errors[field.key] = "is required"
            continue
        try:
            cleaned[field.key] = _normalise_value(field, value)
        except ValueError as exc:
            errors[field.key] = str(exc)

    if errors:
        raise DetailsError(errors)
    return cleaned
