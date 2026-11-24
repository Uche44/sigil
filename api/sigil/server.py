"""FastAPI app: producer, admin and shopper endpoints.

Shoppers never sign or send transactions. Every on-chain write is made by a
producer or admin wallet in the browser, then confirmed here by reading the chain.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import secrets
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from solders.pubkey import Pubkey

from . import auth, service
from .canonical import canonical_json_bytes
from .config import Settings
from .db import connect, init_db, now
from .hints import coarse_region, device_hash
from .labels import labels_pdf, qr_png, verify_url
from .packs import Pack, load_packs, pack_by_code
from .rpc import ChainError, RpcReader, derive_issuer_pda, derive_registry_pda
from .serials import is_valid_serial
from .service import (
    TreeCache,
    ValidationError,
    batch_activity,
    confirm_batch,
    get_batch,
    get_issuer,
    mark_recalled,
    prepare_batch,
    prune_scans,
    verify_scan,
)

SETTINGS = Settings.from_env()
PROGRAM_ID = SETTINGS.program_id


class RateLimiter:
    def __init__(self, limit: int = 120, window: int = 60) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, at: float | None = None) -> bool:
        import time

        moment = at if at is not None else time.monotonic()
        if len(self._hits) > 10_000:
            self._hits = {
                device: [hit for hit in hits if moment - hit < self.window]
                for device, hits in self._hits.items()
                if any(moment - hit < self.window for hit in hits)
            }
        hits = [hit for hit in self._hits.get(key, []) if moment - hit < self.window]
        if len(hits) >= self.limit:
            self._hits[key] = hits
            return False
        hits.append(moment)
        self._hits[key] = hits
        return True


@dataclass
class AppState:
    settings: Settings
    conn: sqlite3.Connection
    rpc: RpcReader
    trees: TreeCache
    packs: dict[str, Pack]
    limiter: RateLimiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    SETTINGS.uploads_dir.mkdir(parents=True, exist_ok=True)
    init_db(SETTINGS.db_path)
    conn = connect(SETTINGS.db_path)
    prune_scans(conn, SETTINGS.scan_retention_days)
    app.state.sigil = AppState(
        settings=SETTINGS,
        conn=conn,
        rpc=RpcReader(
            SETTINGS.rpc_url, SETTINGS.program_id, SETTINGS.chain_cache_seconds
        ),
        trees=TreeCache(),
        packs=load_packs(SETTINGS.packs_dir),
        limiter=RateLimiter(),
    )
    yield
    app.state.sigil.conn.close()


app = FastAPI(title="Sigil API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(SETTINGS.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Sigil-Region"],
)

SETTINGS.uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/uploads", StaticFiles(directory=str(SETTINGS.uploads_dir)), name="uploads"
)


@app.exception_handler(ValidationError)
async def validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"errors": exc.errors})


@app.exception_handler(ChainError)
async def chain_handler(_: Request, exc: ChainError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"error": "chain unavailable"})


def state(request: Request) -> AppState:
    return request.app.state.sigil


def wallet_from_header(
    request: Request, authorization: str | None = Header(default=None)
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="sign in required")
    token = authorization.split(" ", 1)[1].strip()
    wallet = auth.read_token(token, state(request).settings.token_secret)
    if wallet is None:
        raise HTTPException(status_code=401, detail="session expired, sign in again")
    return wallet


def require_admin(request: Request, wallet: str = Depends(wallet_from_header)) -> str:
    admins = state(request).settings.admin_pubkeys
    if not admins:
        raise HTTPException(status_code=403, detail="no admin wallets configured")
    if wallet not in admins:
        raise HTTPException(status_code=403, detail="not an admin wallet")
    return wallet


def require_issuer(request: Request, wallet: str = Depends(wallet_from_header)) -> dict[str, Any]:
    issuer = get_issuer(state(request).conn, wallet)
    if issuer is None:
        raise HTTPException(status_code=404, detail="submit your company profile first")
    return issuer


# ---------------------------------------------------------------- models


class NonceRequest(BaseModel):
    wallet: str = Field(min_length=32, max_length=44)


class VerifyRequest(BaseModel):
    wallet: str = Field(min_length=32, max_length=44)
    nonce: str = Field(min_length=8, max_length=200)
    signature: str = Field(min_length=64, max_length=128)


class IssuerProfile(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(default="", max_length=80)
    regulator_numbers: dict[str, str] = Field(default_factory=dict)
    documents: list[str] = Field(default_factory=list, max_length=20)
    contact_email: str = Field(default="", max_length=200)


class PrepareBatchRequest(BaseModel):
    industry: str
    details: dict[str, Any]
    units: int
    manufactured_at: str
    expires_at: str | None = None


class ConfirmBatchRequest(BaseModel):
    tx_signature: str = Field(min_length=32, max_length=128)


class RecallConfirmRequest(BaseModel):
    reason: int = Field(default=0, ge=0, le=255)


class ReportRequest(BaseModel):
    public_code: str
    serial: str
    note: str = Field(min_length=1, max_length=2000)
    photo_ref: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------- helpers


def _issuer_payload(request: Request, wallet: str, issuer: dict[str, Any] | None, chain_status: int | None) -> dict[str, Any]:
    profile = json.loads(issuer["profile_json"]) if issuer else None
    return {
        "wallet": wallet,
        "profile": profile,
        "name_hash": issuer["name_hash"] if issuer else None,
        "issuer_pda": derive_issuer_pda(state(request).settings.program_id, wallet),
        "status": chain_status,
        "status_label": service.issuer_label(chain_status) if chain_status is not None else None,
        "registered": chain_status is not None,
        "is_admin": wallet in state(request).settings.admin_pubkeys,
    }


def _batch_payload(request: Request, batch: dict[str, Any]) -> dict[str, Any]:
    st = state(request)
    pack = pack_by_code(st.packs, batch["industry"])
    settings = st.settings
    return {
        "id": batch["id"],
        "public_code": batch["public_code"],
        "status": batch["status"],
        "industry": pack.id if pack else None,
        "industry_name": pack.name if pack else None,
        "industry_code": batch["industry"],
        "details": json.loads(batch["details_json"]),
        "units": batch["units"],
        "manufactured_at": service._iso(batch["manufactured_at"]),
        "expires_at": service._iso(batch["expires_at"]),
        "created_at": batch["created_at"],
        "confirmed_at": batch["confirmed_at"],
        "merkle_root": batch["merkle_root"],
        "details_hash": batch["details_hash"],
        "batch_pda": batch["batch_pda"],
        "issuer_pda": batch["issuer_pda"],
        "tx_signature": batch["tx_signature"],
        "verify_base": f"{settings.web_base_url}/v/{batch['public_code']}",
        "labels_pdf": f"/api/v1/batches/{batch['id']}/labels",
        "labels_png": f"/api/v1/batches/{batch['id']}/labels/{{serial}}.png",
    }


async def _chain_status(request: Request, wallet: str) -> int | None:
    st = state(request)
    pda = derive_issuer_pda(st.settings.program_id, wallet)
    issuer = await st.rpc.issuer(pda)
    return issuer.status if issuer else None


# ---------------------------------------------------------------- config


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/config")
async def config() -> dict[str, Any]:
    return {
        "program_id": PROGRAM_ID,
        "rpc_url": SETTINGS.rpc_url,
        "registry_pda": derive_registry_pda(PROGRAM_ID),
        "web_base_url": SETTINGS.web_base_url,
    }


@app.get("/api/v1/industries")
async def industries(request: Request) -> dict[str, Any]:
    packs = state(request).packs
    return {
        "industries": [
            {
                "id": pack.id,
                "name": pack.name,
                "industry_code": pack.industry_code,
                "expiry_required": pack.expiry_required,
                "fields": [
                    {
                        "key": field.key,
                        "label": field.label,
                        "type": field.type,
                        "required": field.required,
                    }
                    for field in pack.fields
                ],
                "checklist": list(pack.checklist),
            }
            for pack in sorted(packs.values(), key=lambda p: p.industry_code)
        ]
    }


# ---------------------------------------------------------------- auth


@app.post("/api/v1/auth/nonce")
async def auth_nonce(body: NonceRequest, request: Request) -> dict[str, Any]:
    st = state(request)
    try:
        Pubkey.from_string(body.wallet)
    except Exception:
        raise HTTPException(status_code=422, detail="wallet is not a valid Solana address")
    nonce = auth.new_nonce()
    issued_at = now()
    message = auth.sign_in_message(body.wallet, nonce, issued_at)
    expires_at = issued_at + st.settings.nonce_ttl_seconds
    with st.conn:
        st.conn.execute("DELETE FROM nonces WHERE expires_at < ?", (issued_at,))
        st.conn.execute(
            "INSERT INTO nonces (wallet, nonce, message, expires_at) VALUES (?, ?, ?, ?)",
            (body.wallet, nonce, message, expires_at),
        )
    return {"nonce": nonce, "message": message, "expires_at": expires_at}


@app.post("/api/v1/auth/verify")
async def auth_verify(body: VerifyRequest, request: Request) -> dict[str, Any]:
    st = state(request)
    row = st.conn.execute(
        "SELECT * FROM nonces WHERE wallet = ? AND nonce = ?",
        (body.wallet, body.nonce),
    ).fetchone()
    if row is None or row["used"] or row["expires_at"] < now():
        raise HTTPException(status_code=401, detail="nonce is unknown, used or expired")

    try:
        auth.verify_signature(body.wallet, row["message"], body.signature)
    except auth.AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    with st.conn:
        st.conn.execute(
            "UPDATE nonces SET used = 1 WHERE wallet = ? AND nonce = ?",
            (body.wallet, body.nonce),
        )

    token, expires_at = auth.issue_token(
        body.wallet, st.settings.token_secret, st.settings.token_ttl_seconds
    )
    issuer = get_issuer(st.conn, body.wallet)
    chain_status = await _chain_status(request, body.wallet)
    return {
        "token": token,
        "expires_at": expires_at,
        "issuer": _issuer_payload(request, body.wallet, issuer, chain_status),
    }


# ---------------------------------------------------------------- issuers


@app.post("/api/v1/issuers")
async def submit_issuer(
    body: IssuerProfile,
    request: Request,
    wallet: str = Depends(wallet_from_header),
) -> dict[str, Any]:
    st = state(request)
    profile = body.model_dump()
    profile_json = canonical_json_bytes(profile).decode("utf-8")
    name_hash = hashlib.sha256(canonical_json_bytes(profile)).hexdigest()
    issuer_pda = derive_issuer_pda(st.settings.program_id, wallet)
    chain = await st.rpc.issuer(issuer_pda)

    existing = get_issuer(st.conn, wallet)
    if existing and chain is not None:
        return {
            "issuer": _issuer_payload(request, wallet, existing, chain.status),
            "instruction": None,
        }

    with st.conn:
        if existing:
            st.conn.execute(
                "UPDATE issuers SET name_hash = ?, profile_json = ?, updated_at = ? WHERE id = ?",
                (name_hash, profile_json, now(), existing["id"]),
            )
        else:
            st.conn.execute(
                "INSERT INTO issuers (authority, name_hash, profile_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (wallet, name_hash, profile_json, now(), now()),
            )

    issuer = get_issuer(st.conn, wallet)
    return {
        "issuer": _issuer_payload(request, wallet, issuer, chain.status if chain else None),
        "instruction": {
            "program_id": st.settings.program_id,
            "registry": derive_registry_pda(st.settings.program_id),
            "issuer": issuer_pda,
            "authority": wallet,
            "name_hash": list(bytes.fromhex(name_hash)),
        },
    }


@app.get("/api/v1/issuers/me")
async def my_issuer(
    request: Request, wallet: str = Depends(wallet_from_header)
) -> dict[str, Any]:
    issuer = get_issuer(state(request).conn, wallet)
    pda = derive_issuer_pda(state(request).settings.program_id, wallet)
    state(request).rpc.forget(pda)
    chain_status = await _chain_status(request, wallet)
    return _issuer_payload(request, wallet, issuer, chain_status)


# ---------------------------------------------------------------- uploads


@app.post("/api/v1/uploads/photo")
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    wallet: str = Depends(wallet_from_header),
) -> dict[str, str]:
    st = state(request)
    raw = await file.read(6 * 1024 * 1024 + 1)
    if len(raw) > 6 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="photo must be 6MB or smaller")
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=422, detail="that file is not a readable image")

    image.thumbnail((1600, 1600))
    name = f"{secrets.token_hex(16)}.jpg"
    image.save(st.settings.uploads_dir / name, format="JPEG", quality=85, optimize=True)
    relative = f"/uploads/{name}"
    return {
        "url": relative,
        "absolute_url": f"{st.settings.public_base_url}{relative}",
    }


# ---------------------------------------------------------------- batches


@app.get("/api/v1/batches")
async def list_batches(
    request: Request, issuer: dict[str, Any] = Depends(require_issuer)
) -> dict[str, Any]:
    rows = state(request).conn.execute(
        "SELECT * FROM batches WHERE issuer_id = ? ORDER BY id DESC",
        (issuer["id"],),
    ).fetchall()
    return {"batches": [_batch_payload(request, dict(row)) for row in rows]}


@app.post("/api/v1/batches/prepare")
async def prepare(
    body: PrepareBatchRequest,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> dict[str, Any]:
    st = state(request)
    pack = st.packs.get(body.industry)
    if pack is None:
        raise HTTPException(status_code=422, detail=f"unknown industry {body.industry!r}")

    chain_issuer_pda = derive_issuer_pda(st.settings.program_id, issuer["authority"])
    st.rpc.forget(chain_issuer_pda)
    chain_issuer = await st.rpc.issuer(chain_issuer_pda)
    if chain_issuer is None:
        raise HTTPException(status_code=403, detail="register your issuer on-chain first")
    if chain_issuer.status != 1:
        raise HTTPException(status_code=403, detail="your issuer is not verified yet")

    prepared = prepare_batch(
        st.conn, st.settings, pack, issuer, body.model_dump()
    )
    prepared["nonce"] = str(prepared["nonce"])
    prepared["program_id"] = st.settings.program_id
    prepared["registry_pda"] = derive_registry_pda(st.settings.program_id)
    prepared["industry"] = pack.id
    return prepared


@app.get("/api/v1/batches/{batch_id}")
async def batch_detail(
    batch_id: int,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> dict[str, Any]:
    batch = get_batch(state(request).conn, batch_id)
    if batch is None or batch["issuer_id"] != issuer["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    payload = _batch_payload(request, batch)
    payload["activity"] = batch_activity(state(request).conn, state(request).settings, batch_id)
    return payload


@app.post("/api/v1/batches/{batch_id}/confirm")
async def confirm(
    batch_id: int,
    body: ConfirmBatchRequest,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> dict[str, Any]:
    st = state(request)
    batch = get_batch(st.conn, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    confirmed = await confirm_batch(
        st.conn, st.rpc, issuer, batch, body.tx_signature
    )
    st.trees.forget(batch_id)
    return _batch_payload(request, confirmed)


@app.post("/api/v1/batches/{batch_id}/recall/prepare")
async def recall_prepare(
    batch_id: int,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> dict[str, Any]:
    st = state(request)
    batch = get_batch(st.conn, batch_id)
    if batch is None or batch["issuer_id"] != issuer["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    if batch["status"] != "active":
        raise HTTPException(status_code=409, detail="only active batches can be recalled")
    chain = await st.rpc.batch(batch["batch_pda"])
    if chain is None:
        raise HTTPException(status_code=409, detail="batch not found on chain")
    if chain.status != 0:
        raise HTTPException(status_code=409, detail="batch is already recalled")
    return {
        "program_id": st.settings.program_id,
        "issuer": batch["issuer_pda"],
        "authority": issuer["authority"],
        "batch": batch["batch_pda"],
        "instruction": "recall_batch",
    }


@app.post("/api/v1/batches/{batch_id}/recall/confirm")
async def recall_confirm(
    batch_id: int,
    body: RecallConfirmRequest,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> dict[str, Any]:
    st = state(request)
    batch = get_batch(st.conn, batch_id)
    if batch is None or batch["issuer_id"] != issuer["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    st.rpc.forget(batch["batch_pda"])
    chain = await st.rpc.batch(batch["batch_pda"])
    if chain is None:
        raise HTTPException(status_code=409, detail="batch not found on chain")
    if chain.status != 1:
        raise HTTPException(status_code=409, detail="the chain does not show this batch as recalled")
    updated = mark_recalled(st.conn, batch, body.reason)
    return _batch_payload(request, updated)


@app.get("/api/v1/batches/{batch_id}/serials")
async def batch_serials(
    batch_id: int,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    issuer: dict[str, Any] = Depends(require_issuer),
) -> dict[str, Any]:
    st = state(request)
    batch = get_batch(st.conn, batch_id)
    if batch is None or batch["issuer_id"] != issuer["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    rows = st.conn.execute(
        "SELECT serial FROM serials WHERE batch_id = ? ORDER BY leaf_index LIMIT ? OFFSET ?",
        (batch_id, limit, offset),
    ).fetchall()
    total = st.conn.execute(
        "SELECT COUNT(*) AS n FROM serials WHERE batch_id = ?", (batch_id,)
    ).fetchone()["n"]
    return {"serials": [row["serial"] for row in rows], "total": total}


@app.get("/api/v1/batches/{batch_id}/activity")
async def activity(
    batch_id: int,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> dict[str, Any]:
    st = state(request)
    batch = get_batch(st.conn, batch_id)
    if batch is None or batch["issuer_id"] != issuer["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    return batch_activity(st.conn, st.settings, batch_id)


def _label_context(request: Request, batch_id: int, issuer: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    st = state(request)
    batch = get_batch(st.conn, batch_id)
    if batch is None or batch["issuer_id"] != issuer["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    if batch["status"] == "draft":
        raise HTTPException(status_code=409, detail="confirm the batch before downloading labels")
    serials = [
        row["serial"]
        for row in st.conn.execute(
            "SELECT serial FROM serials WHERE batch_id = ? ORDER BY leaf_index",
            (batch_id,),
        ).fetchall()
    ]
    return batch, serials


@app.get("/api/v1/batches/{batch_id}/labels")
async def labels(
    batch_id: int,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> Response:
    st = state(request)
    batch, serials = _label_context(request, batch_id, issuer)
    details = json.loads(batch["details_json"])
    pdf = labels_pdf(
        base_url=st.settings.web_base_url,
        public_code=batch["public_code"],
        product_name=details.get("product_name") or details.get("item_type") or "Product",
        batch_number=details.get("batch_number") or batch["public_code"],
        serials=serials,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="sigil-{batch["public_code"]}.pdf"'
        },
    )


@app.get("/api/v1/batches/{batch_id}/labels/{serial}.png")
async def label_png(
    batch_id: int,
    serial: str,
    request: Request,
    issuer: dict[str, Any] = Depends(require_issuer),
) -> Response:
    st = state(request)
    batch, _ = _label_context(request, batch_id, issuer)
    exists = st.conn.execute(
        "SELECT 1 FROM serials WHERE batch_id = ? AND serial = ?", (batch_id, serial)
    ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="serial is not in this batch")
    png = qr_png(verify_url(st.settings.web_base_url, batch["public_code"], serial))
    return Response(content=png, media_type="image/png")


# ---------------------------------------------------------------- admin


@app.get("/api/v1/admin/registry")
async def admin_registry(
    request: Request, wallet: str = Depends(require_admin)
) -> dict[str, Any]:
    st = state(request)
    pda = derive_registry_pda(st.settings.program_id)
    st.rpc.forget(pda)
    registry = await st.rpc.registry(pda)
    return {
        "registry_pda": pda,
        "exists": registry is not None,
        "admin": registry.admin if registry else None,
        "issuer_count": registry.issuer_count if registry else 0,
        "wallet": wallet,
        "wallet_is_admin": bool(registry and registry.admin == wallet),
    }


@app.get("/api/v1/admin/issuers")
async def admin_issuers(
    request: Request,
    status: str = Query(default="pending"),
    wallet: str = Depends(require_admin),
) -> dict[str, Any]:
    st = state(request)
    rows = st.conn.execute("SELECT * FROM issuers ORDER BY id DESC").fetchall()
    wanted = {
        "pending": 0,
        "verified": 1,
        "suspended": 2,
        "all": None,
    }
    if status not in wanted:
        raise HTTPException(status_code=422, detail="status must be pending, verified, suspended or all")
    target = wanted[status]

    async def one(row: sqlite3.Row) -> dict[str, Any] | None:
        issuer = dict(row)
        pda = derive_issuer_pda(st.settings.program_id, issuer["authority"])
        st.rpc.forget(pda)
        chain = await st.rpc.issuer(pda)
        if chain is None:
            return None
        if target is not None and chain.status != target:
            return None
        return {
            "wallet": issuer["authority"],
            "issuer_pda": pda,
            "profile": json.loads(issuer["profile_json"]),
            "name_hash": issuer["name_hash"],
            "status": chain.status,
            "status_label": service.issuer_label(chain.status),
            "created_at": chain.created_at,
            "verified_at": chain.verified_at,
        }

    results = await asyncio.gather(*(one(row) for row in rows))
    return {"issuers": [item for item in results if item is not None]}


# ---------------------------------------------------------------- shopper verify

_prune_counter = 0


@app.get("/api/v1/verify/{batch_code}/{serial}")
async def verify(
    batch_code: str,
    serial: str,
    request: Request,
    proof: bool = Query(default=False),
) -> JSONResponse:
    st = state(request)
    serial = serial.upper()
    if not is_valid_serial(serial):
        raise HTTPException(status_code=422, detail="that is not a valid serial")
    if len(batch_code) > 32:
        raise HTTPException(status_code=422, detail="that is not a valid batch code")

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    device = device_hash(st.settings.device_secret, ip, request.headers.get("user-agent"))
    if not st.limiter.allow(device):
        raise HTTPException(status_code=429, detail="too many scans, wait a minute")

    region, country = coarse_region(dict(request.headers))
    payload = await verify_scan(
        st.conn,
        st.rpc,
        st.settings,
        st.trees,
        st.packs,
        public_code=batch_code.lower(),
        serial=serial,
        region=region,
        country=country,
        device=device,
        include_proof=proof,
    )

    global _prune_counter
    _prune_counter += 1
    if _prune_counter % 500 == 0:
        prune_scans(st.conn, st.settings.scan_retention_days)

    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"},
    )


@app.post("/api/v1/reports")
async def report(body: ReportRequest, request: Request) -> dict[str, Any]:
    st = state(request)
    batch = st.conn.execute(
        "SELECT id FROM batches WHERE public_code = ?", (body.public_code.lower(),)
    ).fetchone()
    with st.conn:
        cursor = st.conn.execute(
            "INSERT INTO reports (batch_id, serial, note, photo_ref, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                batch["id"] if batch else None,
                body.serial,
                body.note,
                body.photo_ref,
                now(),
            ),
        )
    return {"report_id": int(cursor.lastrowid)}
