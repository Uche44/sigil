"""Core business logic: batch preparation, confirmation and shopper verification."""

from __future__ import annotations

import base64
import json
import secrets
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timezone
from typing import Any

from solders.pubkey import Pubkey

from . import hints
from .config import Settings
from .db import now
from .merkle import MerkleTree, details_hash, leaf_hash, verify_proof
from .packs import Pack, pack_by_code, validate_details
from .rpc import (
    BATCH_ACTIVE,
    BATCH_RECALLED,
    STATUS_SUSPENDED,
    STATUS_VERIFIED,
    BatchState,
    IssuerState,
    RpcReader,
    derive_batch_pda,
    derive_issuer_pda,
)
from .serials import decode_serial, encode_serial, generate_serial

VERDICT_UNKNOWN = "UNKNOWN"
VERDICT_ISSUER_SUSPENDED = "ISSUER_SUSPENDED"
VERDICT_RECALLED = "RECALLED"
VERDICT_EXPIRED = "EXPIRED"
VERDICT_UNUSUAL = "UNUSUAL_ACTIVITY"
VERDICT_REGISTERED = "REGISTERED"

VERDICT_COPY = {
    VERDICT_UNKNOWN: "This code is not registered. Do not trust this product.",
    VERDICT_ISSUER_SUSPENDED: "The producer's verification was withdrawn. Do not trust this product.",
    VERDICT_RECALLED: "This batch was recalled by the producer. Do not use this product.",
    VERDICT_EXPIRED: "This product is past its expiry date.",
    VERDICT_UNUSUAL: "This code has been scanned in several places recently. This can be normal. Check your pack carefully.",
    VERDICT_REGISTERED: "This code is registered. Check that the details match the pack in your hand.",
}

VERDICT_LABELS = {
    VERDICT_UNKNOWN: "Not registered",
    VERDICT_ISSUER_SUSPENDED: "Producer suspended",
    VERDICT_RECALLED: "Recalled",
    VERDICT_EXPIRED: "Expired",
    VERDICT_UNUSUAL: "Unusual activity",
    VERDICT_REGISTERED: "Registered",
}

VERDICT_TONE = {
    VERDICT_UNKNOWN: "red",
    VERDICT_ISSUER_SUSPENDED: "red",
    VERDICT_RECALLED: "red",
    VERDICT_EXPIRED: "red",
    VERDICT_UNUSUAL: "amber",
    VERDICT_REGISTERED: "green",
}


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str] | list[str]) -> None:
        self.errors = errors
        super().__init__(str(errors))


@dataclass
class Verdict:
    verdict: str
    reason: str
    details: dict[str, Any]
    proof: dict[str, Any] | None


def _iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def _day_start(value: str) -> int:
    parsed = date.fromisoformat(value)
    return int(datetime.combine(parsed, dtime.min, tzinfo=timezone.utc).timestamp())


def _day_end(value: str) -> int:
    parsed = date.fromisoformat(value)
    return int(datetime.combine(parsed, dtime.max, tzinfo=timezone.utc).timestamp())


def _row(conn: sqlite3.Connection, sql: str, params: tuple) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def get_issuer(conn: sqlite3.Connection, wallet: str) -> dict[str, Any] | None:
    return _row(conn, "SELECT * FROM issuers WHERE authority = ?", (wallet,))


def get_batch(conn: sqlite3.Connection, batch_id: int) -> dict[str, Any] | None:
    return _row(conn, "SELECT * FROM batches WHERE id = ?", (batch_id,))


def new_public_code(conn: sqlite3.Connection) -> str:
    while True:
        code = base64.b32encode(secrets.token_bytes(8)).decode("ascii").rstrip("=").lower()
        if not conn.execute("SELECT 1 FROM batches WHERE public_code = ?", (code,)).fetchone():
            return code


def _load_tree(conn: sqlite3.Connection, batch: dict[str, Any]) -> MerkleTree:
    rows = conn.execute(
        "SELECT serial FROM serials WHERE batch_id = ? ORDER BY leaf_index",
        (batch["id"],),
    ).fetchall()
    batch_pda_bytes = bytes(Pubkey.from_string(batch["batch_pda"]))
    raw_serials = [decode_serial(row["serial"]) for row in rows]
    return MerkleTree.from_serials(batch_pda_bytes, raw_serials)


class TreeCache:
    """Immutable trees, built once per batch and kept in memory."""

    def __init__(self, max_batches: int = 8) -> None:
        self.max_batches = max_batches
        self._trees: OrderedDict[int, tuple[str, MerkleTree]] = OrderedDict()

    def get(self, conn: sqlite3.Connection, batch: dict[str, Any]) -> MerkleTree:
        key = batch["id"]
        cached = self._trees.get(key)
        if cached and cached[0] == batch["merkle_root"]:
            self._trees.move_to_end(key)
            return cached[1]
        tree = _load_tree(conn, batch)
        self._trees[key] = (batch["merkle_root"], tree)
        self._trees.move_to_end(key)
        while len(self._trees) > self.max_batches:
            self._trees.popitem(last=False)
        return tree

    def forget(self, batch_id: int) -> None:
        self._trees.pop(batch_id, None)


def prepare_batch(
    conn: sqlite3.Connection,
    settings: Settings,
    pack: Pack,
    issuer: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    errors: dict[str, str] = {}

    try:
        details = validate_details(pack, payload.get("details") or {})
    except ValueError as exc:
        from .packs import DetailsError

        if isinstance(exc, DetailsError):
            errors.update(exc.errors)
        else:
            errors["details"] = str(exc)
        details = {}

    units = payload.get("units")
    if not isinstance(units, int) or isinstance(units, bool):
        errors["units"] = "must be a whole number"
    elif not 1 <= units <= min(settings.max_units, 100_000):
        errors["units"] = f"must be between 1 and {min(settings.max_units, 100_000)}"

    manufactured_date = None
    if not payload.get("manufactured_at"):
        errors["manufactured_at"] = "is required"
    else:
        try:
            manufactured_date = date.fromisoformat(str(payload["manufactured_at"]))
        except ValueError:
            errors["manufactured_at"] = "must be a date in YYYY-MM-DD form"

    expiry_date = None
    if payload.get("expires_at"):
        try:
            expiry_date = date.fromisoformat(str(payload["expires_at"]))
        except ValueError:
            errors["expires_at"] = "must be a date in YYYY-MM-DD form"
    if pack.expiry_required and expiry_date is None and "expires_at" not in errors:
        errors["expires_at"] = f"{pack.name} batches need an expiry date"

    if expiry_date:
        if _day_end(expiry_date.isoformat()) <= now():
            errors["expires_at"] = "must be in the future"
        elif manufactured_date and expiry_date <= manufactured_date:
            errors["expires_at"] = "must be after the manufacture date"

    if errors:
        raise ValidationError(errors)

    assert manufactured_date is not None  # narrowed by validation above

    authority = issuer["authority"]
    issuer_pda = derive_issuer_pda(settings.program_id, authority)

    nonce = secrets.randbits(63)
    while conn.execute(
        "SELECT 1 FROM batches WHERE issuer_pda = ? AND nonce = ?",
        (issuer_pda, nonce),
    ).fetchone():
        nonce = secrets.randbits(64)

    batch_pda = derive_batch_pda(settings.program_id, issuer_pda, nonce)

    serials: list[bytes] = []
    seen: set[str] = set()
    while len(serials) < units:
        raw = generate_serial()
        text = encode_serial(raw)
        if text not in seen:
            seen.add(text)
            serials.append(raw)

    tree = MerkleTree.from_serials(bytes(Pubkey.from_string(batch_pda)), serials)
    details_commitment = details_hash(details).hex()
    manufactured_at = _day_start(manufactured_date.isoformat())
    expires_at = _day_end(expiry_date.isoformat()) if expiry_date else 0

    public_code = new_public_code(conn)
    details_json = json.dumps(
        details, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO batches (
                public_code, issuer_id, issuer_pda, batch_pda, nonce, industry,
                details_json, details_hash, merkle_root, units, manufactured_at,
                expires_at, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (
                public_code,
                issuer["id"],
                issuer_pda,
                batch_pda,
                nonce,
                pack.industry_code,
                details_json,
                details_commitment,
                tree.root_hex,
                units,
                manufactured_at,
                expires_at,
                now(),
            ),
        )
        batch_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO serials (batch_id, serial, leaf_index) VALUES (?, ?, ?)",
            [
                (batch_id, encode_serial(raw), index)
                for index, raw in enumerate(serials)
            ],
        )

    return {
        "batch_id": batch_id,
        "public_code": public_code,
        "industry_id": pack.id,
        "industry_code": pack.industry_code,
        "nonce": nonce,
        "merkle_root": tree.root_hex,
        "details_hash": details_commitment,
        "units": units,
        "manufactured_at": manufactured_at,
        "expires_at": expires_at,
        "issuer_pda": issuer_pda,
        "batch_pda": batch_pda,
        "authority": authority,
        "tx_accounts": {
            "issuer": issuer_pda,
            "authority": authority,
            "batch": batch_pda,
        },
    }


def compare_batch_state(batch: dict[str, Any], state: BatchState) -> list[str]:
    problems: list[str] = []
    if state.issuer != batch["issuer_pda"]:
        problems.append("issuer does not match")
    if state.nonce != batch["nonce"]:
        problems.append("nonce does not match")
    if state.industry != batch["industry"]:
        problems.append("industry does not match")
    if state.merkle_root.hex() != batch["merkle_root"]:
        problems.append("Merkle root does not match")
    if state.details_hash.hex() != batch["details_hash"]:
        problems.append("details hash does not match")
    if state.units != batch["units"]:
        problems.append("units do not match")
    if state.manufactured_at != batch["manufactured_at"]:
        problems.append("manufacture date does not match")
    if state.expires_at != batch["expires_at"]:
        problems.append("expiry does not match")
    return problems


async def confirm_batch(
    conn: sqlite3.Connection,
    rpc: RpcReader,
    issuer: dict[str, Any],
    batch: dict[str, Any],
    tx_signature: str,
) -> dict[str, Any]:
    if batch["issuer_id"] != issuer["id"]:
        raise ValidationError(["this batch belongs to another issuer"])
    if batch["status"] != "draft":
        raise ValidationError([f"batch is already {batch['status']}"])
    if not batch.get("batch_pda"):
        raise ValidationError(["batch has no on-chain address"])

    rpc.forget(batch["batch_pda"])
    state = await rpc.batch(batch["batch_pda"])
    if state is None:
        raise ValidationError(["batch account was not found on chain yet"])
    problems = compare_batch_state(batch, state)
    if problems:
        raise ValidationError(problems)

    with conn:
        conn.execute(
            """
            UPDATE batches SET status = 'active', tx_signature = ?, confirmed_at = ?
            WHERE id = ?
            """,
            (tx_signature, now(), batch["id"]),
        )
    return get_batch(conn, batch["id"]) or batch


def mark_recalled(
    conn: sqlite3.Connection, batch: dict[str, Any], reason: int | None
) -> dict[str, Any]:
    with conn:
        conn.execute(
            """
            UPDATE batches SET status = 'recalled', recalled_at = ?, recall_reason = ?
            WHERE id = ?
            """,
            (now(), reason, batch["id"]),
        )
    return get_batch(conn, batch["id"]) or batch


def issuer_label(status: int) -> str:
    if status == STATUS_VERIFIED:
        return "Verified producer"
    if status == STATUS_SUSPENDED:
        return "Suspended producer"
    return "Unverified producer"


def resolve_verdict(
    conn: sqlite3.Connection,
    settings: Settings,
    trees: TreeCache,
    batch: dict[str, Any],
    serial: str,
    state: BatchState,
    issuer_state: IssuerState,
    region: str | None,
) -> Verdict:
    try:
        serial_bytes = decode_serial(serial)
    except ValueError:
        return Verdict(VERDICT_UNKNOWN, "invalid_serial", {}, None)

    row = conn.execute(
        "SELECT leaf_index FROM serials WHERE batch_id = ? AND serial = ?",
        (batch["id"], serial),
    ).fetchone()
    if row is None:
        return Verdict(VERDICT_UNKNOWN, "serial_not_registered", {}, None)

    details = json.loads(batch["details_json"])
    if details_hash(details).hex() != state.details_hash.hex():
        return Verdict(VERDICT_UNKNOWN, "details_mismatch", {}, None)

    tree = trees.get(conn, batch)
    if tree.root != state.merkle_root:
        return Verdict(VERDICT_UNKNOWN, "root_mismatch", {}, None)

    leaf = leaf_hash(bytes(Pubkey.from_string(batch["batch_pda"])), serial_bytes)
    proof = tree.proof(row["leaf_index"])
    if not verify_proof(leaf, proof, state.merkle_root):
        return Verdict(VERDICT_UNKNOWN, "proof_failed", {}, None)

    proof_json = {
        "leaf": leaf.hex(),
        "root": state.merkle_root.hex(),
        "leaf_index": row["leaf_index"],
        "steps": [step.to_json() for step in proof],
    }

    if issuer_state.status == STATUS_SUSPENDED:
        return Verdict(VERDICT_ISSUER_SUSPENDED, "issuer_suspended", details, proof_json)
    if state.status == BATCH_RECALLED:
        return Verdict(VERDICT_RECALLED, "batch_recalled", details, proof_json)
    if state.expires_at != 0 and now() > state.expires_at:
        return Verdict(VERDICT_EXPIRED, "expired", details, proof_json)
    if hints.serial_is_unusual(conn, settings, batch["id"], serial, region, now()):
        return Verdict(VERDICT_UNUSUAL, "unusual_activity", details, proof_json)
    if state.status != BATCH_ACTIVE:
        return Verdict(VERDICT_UNKNOWN, "unknown_batch_status", details, proof_json)
    return Verdict(VERDICT_REGISTERED, "registered", details, proof_json)


async def verify_scan(
    conn: sqlite3.Connection,
    rpc: RpcReader,
    settings: Settings,
    trees: TreeCache,
    packs: dict[str, Pack],
    *,
    public_code: str,
    serial: str,
    region: str | None,
    country: str | None,
    device: str,
    include_proof: bool,
) -> dict[str, Any]:
    batch = _row(conn, "SELECT * FROM batches WHERE public_code = ?", (public_code,))
    issuer_state: IssuerState | None = None
    state: BatchState | None = None
    verdict = Verdict(VERDICT_UNKNOWN, "batch_not_found", {}, None)

    if batch is not None and batch.get("batch_pda") and batch["status"] != "draft":
        state = await rpc.batch(batch["batch_pda"])
        if state is None:
            verdict = Verdict(VERDICT_UNKNOWN, "chain_batch_missing", {}, None)
        elif state.issuer != batch["issuer_pda"]:
            verdict = Verdict(VERDICT_UNKNOWN, "issuer_mismatch", {}, None)
        else:
            issuer_state = await rpc.issuer(state.issuer)
            if issuer_state is None:
                verdict = Verdict(VERDICT_UNKNOWN, "chain_issuer_missing", {}, None)
            else:
                verdict = resolve_verdict(
                    conn, settings, trees, batch, serial, state, issuer_state, region
                )
    elif batch is not None:
        verdict = Verdict(VERDICT_UNKNOWN, "batch_not_confirmed", {}, None)

    issuer_row = (
        _row(conn, "SELECT * FROM issuers WHERE id = ?", (batch["issuer_id"],))
        if batch
        else None
    )
    issuer_name = None
    if issuer_row:
        try:
            issuer_name = json.loads(issuer_row["profile_json"]).get("name")
        except ValueError:
            issuer_name = None

    pack = pack_by_code(packs, batch["industry"]) if batch else None
    payload = build_verdict_payload(
        verdict,
        batch=batch,
        issuer_state=issuer_state,
        issuer_name=issuer_name,
        state=state,
        pack=pack,
        include_proof=include_proof,
    )

    log_scan(conn, batch, serial, verdict.verdict, region, country, device)
    return payload


def build_verdict_payload(
    verdict: Verdict,
    *,
    batch: dict[str, Any] | None,
    issuer_state: IssuerState | None,
    issuer_name: str | None,
    state: BatchState | None,
    pack: Pack | None,
    include_proof: bool,
) -> dict[str, Any]:
    details = verdict.details
    product_name = (
        details.get("product_name") or details.get("item_type") or "this product"
    )
    batch_number = details.get("batch_number") or (batch["public_code"] if batch else "unknown")
    expires_at = _iso(state.expires_at) if state else (_iso(batch["expires_at"]) if batch else None)

    registered_line = None
    if verdict.verdict != VERDICT_UNKNOWN:
        expiry_text = expires_at or "no expiry date"
        registered_line = (
            f"This code is registered to {product_name}, batch {batch_number}, "
            f"expiry {expiry_text}. Check that this matches the pack in your hand."
        )

    return {
        "verdict": verdict.verdict,
        "label": VERDICT_LABELS[verdict.verdict],
        "tone": VERDICT_TONE[verdict.verdict],
        "message": VERDICT_COPY[verdict.verdict],
        "reason": verdict.reason,
        "registered_line": registered_line,
        "product": details,
        "issuer": (
            {
                "name": issuer_name,
                "label": issuer_label(issuer_state.status) if issuer_state else "Unverified producer",
                "verified": bool(issuer_state and issuer_state.status == STATUS_VERIFIED),
                "status": issuer_state.status if issuer_state else None,
            }
            if issuer_state or batch
            else None
        ),
        "batch": (
            {
                "public_code": batch["public_code"],
                "batch_number": batch_number,
                "industry_code": batch["industry"],
                "units": state.units if state else batch["units"],
                "expires_at": expires_at,
                "manufactured_at": (
                    _iso(state.manufactured_at) if state else _iso(batch["manufactured_at"])
                ),
                "status": (
                    "recalled" if state and state.status == BATCH_RECALLED else batch["status"]
                ),
            }
            if batch
            else None
        ),
        "checklist": list(pack.checklist) if pack else [],
        "field_labels": (
            {field.key: field.label for field in pack.fields} if pack else {}
        ),
        "proof": verdict.proof if include_proof else None,
        "verify_path": f"/v/{batch['public_code']}/<serial>" if batch else None,
    }


def log_scan(
    conn: sqlite3.Connection,
    batch: dict[str, Any] | None,
    serial: str,
    verdict: str,
    region: str | None,
    country: str | None,
    device: str,
) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO scan_events
                (batch_id, serial, scanned_at, region, country, device_hash, verdict)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch["id"] if batch else None,
                serial,
                now(),
                region,
                country,
                device,
                verdict,
            ),
        )


def batch_activity(
    conn: sqlite3.Connection, settings: Settings, batch_id: int
) -> dict[str, Any]:
    totals = conn.execute(
        "SELECT COUNT(*) AS scans, COUNT(DISTINCT serial) AS serials FROM scan_events WHERE batch_id = ?",
        (batch_id,),
    ).fetchone()
    by_verdict = conn.execute(
        "SELECT verdict, COUNT(*) AS count FROM scan_events WHERE batch_id = ? GROUP BY verdict",
        (batch_id,),
    ).fetchall()
    flagged = conn.execute(
        """
        SELECT serial, COUNT(DISTINCT region) AS regions, COUNT(*) AS scans
        FROM scan_events WHERE batch_id = ? AND serial IS NOT NULL
        GROUP BY serial HAVING regions > 1 ORDER BY scans DESC LIMIT 20
        """,
        (batch_id,),
    ).fetchall()
    return {
        "scans": totals["scans"],
        "scanned_serials": totals["serials"],
        "by_verdict": {row["verdict"]: row["count"] for row in by_verdict},
        "flagged_serials": [dict(row) for row in flagged],
        "batch_alert": hints.batch_alert(conn, settings, batch_id),
    }


def prune_scans(conn: sqlite3.Connection, retention_days: int) -> None:
    cutoff = now() - retention_days * 24 * 60 * 60
    with conn:
        conn.execute("DELETE FROM scan_events WHERE scanned_at < ?", (cutoff,))
