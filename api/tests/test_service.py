"""End-to-end service tests with a fake chain reader.

These cover the parts that must never regress: the verdict precedence,
the Merkle proof check and the rule that a signed batch's fields are fixed.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from sigil.config import Settings
from sigil.db import connect, init_db, now
from sigil.merkle import ProofStep, leaf_hash, verify_proof
from sigil.packs import DEFAULT_PACKS_DIR, load_packs
from sigil.rpc import BatchState, IssuerState, derive_batch_pda, derive_issuer_pda
from sigil.service import (
    VERDICT_EXPIRED,
    VERDICT_ISSUER_SUSPENDED,
    VERDICT_RECALLED,
    VERDICT_REGISTERED,
    VERDICT_UNKNOWN,
    VERDICT_UNUSUAL,
    TreeCache,
    ValidationError,
    confirm_batch,
    prepare_batch,
    verify_scan,
)
from sigil.serials import decode_serial


class FakeRpc:
    def __init__(self) -> None:
        self.issuers: dict[str, IssuerState] = {}
        self.batches: dict[str, BatchState] = {}

    async def issuer(self, address: str) -> IssuerState | None:
        return self.issuers.get(address)

    async def batch(self, address: str) -> BatchState | None:
        return self.batches.get(address)

    def forget(self, address: str) -> None:
        pass


@pytest.fixture()
def ctx(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "test.db", packs_dir=DEFAULT_PACKS_DIR)
    init_db(settings.db_path)
    conn = connect(settings.db_path)
    packs = load_packs(settings.packs_dir)
    wallet = str(Keypair().pubkey())
    issuer_pda = derive_issuer_pda(settings.program_id, wallet)
    with conn:
        conn.execute(
            "INSERT INTO issuers (authority, name_hash, profile_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (wallet, "00" * 32, json.dumps({"name": "Acme"}), now(), now()),
        )
    issuer = dict(conn.execute("SELECT * FROM issuers").fetchone())
    rpc = FakeRpc()
    rpc.issuers[issuer_pda] = IssuerState(
        address=issuer_pda,
        authority=wallet,
        name_hash=bytes(32),
        status=1,
        created_at=now(),
        verified_at=now(),
    )
    yield {
        "settings": settings,
        "conn": conn,
        "packs": packs,
        "wallet": wallet,
        "issuer": issuer,
        "issuer_pda": issuer_pda,
        "rpc": rpc,
        "trees": TreeCache(),
    }
    conn.close()


def medicine_payload(**overrides):
    payload = {
        "industry": "medicine",
        "details": {
            "product_name": "Paracetamol 500mg",
            "manufacturer": "Acme Pharma",
            "regulator_registration_number": "NAFDAC-1234",
            "batch_number": "B-2026-001",
            "manufacture_date": "2026-01-10",
            "expiry_date": "2030-01-10",
            "photo": "/uploads/paracetamol.jpg",
        },
        "units": 4,
        "manufactured_at": "2026-01-10",
        "expires_at": "2030-01-10",
    }
    payload.update(overrides)
    return payload


def prepare(ctx, **overrides):
    return prepare_batch(
        ctx["conn"],
        ctx["settings"],
        ctx["packs"]["medicine"],
        ctx["issuer"],
        medicine_payload(**overrides),
    )


def chain_state(prepared, **overrides):
    state = BatchState(
        address=prepared["batch_pda"],
        issuer=prepared["issuer_pda"],
        nonce=prepared["nonce"],
        industry=prepared["industry_code"],
        merkle_root=bytes.fromhex(prepared["merkle_root"]),
        details_hash=bytes.fromhex(prepared["details_hash"]),
        units=prepared["units"],
        manufactured_at=prepared["manufactured_at"],
        expires_at=prepared["expires_at"],
        status=0,
        recalled_at=0,
        recall_reason=0,
        created_at=now(),
    )
    return replace(state, **overrides) if overrides else state


async def scan(ctx, prepared, serial="AAAAAAAAAAAAAAAA", **kwargs):
    defaults = dict(
        public_code=prepared["public_code"],
        serial=serial,
        region="NG-LA",
        country="NG",
        device="device-1",
        include_proof=True,
    )
    defaults.update(kwargs)
    return await verify_scan(
        ctx["conn"],
        ctx["rpc"],
        ctx["settings"],
        ctx["trees"],
        ctx["packs"],
        **defaults,
    )


@pytest.mark.asyncio
async def test_prepare_confirm_and_verify(ctx):
    prepared = prepare(ctx)
    assert prepared["merkle_root"] == prepared["merkle_root"].lower()
    assert prepared["units"] == 4
    assert prepared["industry_code"] == 1

    state = chain_state(prepared)
    ctx["rpc"].batches[prepared["batch_pda"]] = state

    batch = ctx["conn"].execute(
        "SELECT * FROM batches WHERE id = ?", (prepared["batch_id"],)
    ).fetchone()
    confirmed = await confirm_batch(
        ctx["conn"], ctx["rpc"], ctx["issuer"], dict(batch), "sig-1"
    )
    assert confirmed["status"] == "active"

    serial = ctx["conn"].execute(
        "SELECT serial FROM serials WHERE batch_id = ? AND leaf_index = 2",
        (prepared["batch_id"],),
    ).fetchone()["serial"]

    result = await scan(ctx, prepared, serial=serial)
    assert result["verdict"] == VERDICT_REGISTERED
    assert result["product"]["product_name"] == "Paracetamol 500mg"
    assert result["batch"]["batch_number"] == "B-2026-001"
    assert result["issuer"]["label"] == "Verified producer"
    assert "Check that this matches the pack in your hand" in result["registered_line"]

    proof = result["proof"]
    assert proof["root"] == prepared["merkle_root"]
    steps = [ProofStep.from_json(step) for step in proof["steps"]]
    leaf = leaf_hash(
        bytes(Pubkey.from_string(prepared["batch_pda"])), decode_serial(serial)
    )
    assert verify_proof(leaf, steps, bytes.fromhex(prepared["merkle_root"]))


@pytest.mark.asyncio
async def test_unknown_batch_and_unknown_serial(ctx):
    prepared = prepare(ctx)
    ctx["rpc"].batches[prepared["batch_pda"]] = chain_state(prepared)
    await confirm_batch(
        ctx["conn"],
        ctx["rpc"],
        ctx["issuer"],
        dict(ctx["conn"].execute("SELECT * FROM batches").fetchone()),
        "sig",
    )

    result = await scan(ctx, prepared, public_code="doesnotexist")
    assert result["verdict"] == VERDICT_UNKNOWN
    assert result["reason"] == "batch_not_found"

    result = await scan(ctx, prepared, serial="BBBBBBBBBBBBBBBB")
    assert result["verdict"] == VERDICT_UNKNOWN
    assert result["reason"] == "serial_not_registered"


@pytest.mark.asyncio
async def test_verdict_precedence(ctx):
    prepared = prepare(ctx)
    state = chain_state(prepared)
    ctx["rpc"].batches[prepared["batch_pda"]] = state
    serial = ctx["conn"].execute("SELECT serial FROM serials LIMIT 1").fetchone()["serial"]

    await confirm_batch(
        ctx["conn"],
        ctx["rpc"],
        ctx["issuer"],
        dict(ctx["conn"].execute("SELECT * FROM batches").fetchone()),
        "sig",
    )

    ctx["rpc"].issuers[prepared["issuer_pda"]] = replace(
        ctx["rpc"].issuers[prepared["issuer_pda"]], status=2
    )
    ctx["rpc"].batches[prepared["batch_pda"]] = replace(
        state, status=1, expires_at=now() - 10
    )
    result = await scan(ctx, prepared, serial=serial)
    assert result["verdict"] == VERDICT_ISSUER_SUSPENDED

    ctx["rpc"].issuers[prepared["issuer_pda"]] = replace(
        ctx["rpc"].issuers[prepared["issuer_pda"]], status=1
    )
    result = await scan(ctx, prepared, serial=serial)
    assert result["verdict"] == VERDICT_RECALLED

    ctx["rpc"].batches[prepared["batch_pda"]] = replace(state, status=0, expires_at=now() - 10)
    result = await scan(ctx, prepared, serial=serial)
    assert result["verdict"] == VERDICT_EXPIRED

    ctx["rpc"].batches[prepared["batch_pda"]] = replace(
        state, status=0, expires_at=prepared["expires_at"]
    )
    result = await scan(ctx, prepared, serial=serial)
    assert result["verdict"] == VERDICT_REGISTERED


@pytest.mark.asyncio
async def test_unusual_activity_is_a_hint_not_a_claim(ctx):
    prepared = prepare(ctx)
    ctx["rpc"].batches[prepared["batch_pda"]] = chain_state(prepared)
    await confirm_batch(
        ctx["conn"],
        ctx["rpc"],
        ctx["issuer"],
        dict(ctx["conn"].execute("SELECT * FROM batches").fetchone()),
        "sig",
    )
    serial = ctx["conn"].execute("SELECT serial FROM serials LIMIT 1").fetchone()["serial"]

    first = await scan(ctx, prepared, serial=serial, region="NG-LA")
    assert first["verdict"] == VERDICT_REGISTERED

    second = await scan(ctx, prepared, serial=serial, region="GH-AC")
    assert second["verdict"] == VERDICT_UNUSUAL
    assert second["tone"] == "amber"
    assert "fake" not in second["message"].lower()
    assert "can be normal" in second["message"].lower()


@pytest.mark.asyncio
async def test_details_tampering_returns_unknown(ctx):
    prepared = prepare(ctx)
    ctx["rpc"].batches[prepared["batch_pda"]] = chain_state(prepared)
    await confirm_batch(
        ctx["conn"],
        ctx["rpc"],
        ctx["issuer"],
        dict(ctx["conn"].execute("SELECT * FROM batches").fetchone()),
        "sig",
    )
    serial = ctx["conn"].execute("SELECT serial FROM serials LIMIT 1").fetchone()["serial"]

    with ctx["conn"]:
        ctx["conn"].execute(
            "UPDATE batches SET details_json = ? WHERE id = ?",
            (json.dumps({"product_name": "Something else"}), prepared["batch_id"]),
        )
    result = await scan(ctx, prepared, serial=serial)
    assert result["verdict"] == VERDICT_UNKNOWN
    assert result["reason"] == "details_mismatch"


@pytest.mark.asyncio
async def test_serial_list_tampering_returns_unknown(ctx):
    prepared = prepare(ctx)
    ctx["rpc"].batches[prepared["batch_pda"]] = chain_state(prepared)
    await confirm_batch(
        ctx["conn"],
        ctx["rpc"],
        ctx["issuer"],
        dict(ctx["conn"].execute("SELECT * FROM batches").fetchone()),
        "sig",
    )
    serial = ctx["conn"].execute("SELECT serial FROM serials LIMIT 1").fetchone()["serial"]
    assert (await scan(ctx, prepared, serial=serial))["verdict"] == VERDICT_REGISTERED

    other = ctx["conn"].execute(
        "SELECT serial FROM serials WHERE batch_id = ? AND serial != ? LIMIT 1",
        (prepared["batch_id"], serial),
    ).fetchone()["serial"]
    with ctx["conn"]:
        ctx["conn"].execute(
            "UPDATE serials SET serial = ? WHERE batch_id = ? AND serial = ?",
            ("CCCCCCCCCCCCCCCC", prepared["batch_id"], other),
        )
    ctx["trees"].forget(prepared["batch_id"])

    result = await scan(ctx, prepared, serial=serial)
    assert result["verdict"] == VERDICT_UNKNOWN
    assert result["reason"] == "root_mismatch"


@pytest.mark.asyncio
async def test_confirm_rejects_a_different_on_chain_batch(ctx):
    prepared = prepare(ctx)
    ctx["rpc"].batches[prepared["batch_pda"]] = chain_state(
        prepared, merkle_root=bytes(32)
    )
    batch = dict(ctx["conn"].execute("SELECT * FROM batches").fetchone())
    with pytest.raises(ValidationError) as exc:
        await confirm_batch(ctx["conn"], ctx["rpc"], ctx["issuer"], batch, "sig")
    assert "Merkle root does not match" in exc.value.errors


def test_prepare_rejects_missing_expiry_and_bad_units(ctx):
    with pytest.raises(ValidationError) as exc:
        prepare(ctx, expires_at=None)
    assert "expires_at" in exc.value.errors

    with pytest.raises(ValidationError) as exc:
        prepare(ctx, units=0)
    assert "units" in exc.value.errors

    with pytest.raises(ValidationError) as exc:
        prepare(ctx, expires_at="2020-01-01")
    assert "expires_at" in exc.value.errors

    details = medicine_payload()["details"] | {"not_a_field": "x"}
    with pytest.raises(ValidationError) as exc:
        prepare(ctx, details=details)
    assert "not_a_field" in exc.value.errors


@pytest.mark.asyncio
async def test_every_serial_can_be_verified(ctx):
    prepared = prepare(ctx, units=7)
    ctx["rpc"].batches[prepared["batch_pda"]] = chain_state(prepared)
    await confirm_batch(
        ctx["conn"],
        ctx["rpc"],
        ctx["issuer"],
        dict(ctx["conn"].execute("SELECT * FROM batches").fetchone()),
        "sig",
    )
    serials = [
        row["serial"]
        for row in ctx["conn"].execute(
            "SELECT serial FROM serials WHERE batch_id = ? ORDER BY leaf_index",
            (prepared["batch_id"],),
        ).fetchall()
    ]
    assert len(set(serials)) == 7
    for serial in serials:
        result = await scan(ctx, prepared, serial=serial, region=None)
        assert result["verdict"] == VERDICT_REGISTERED

    logs = ctx["conn"].execute("SELECT COUNT(*) AS n FROM scan_events").fetchone()["n"]
    assert logs == 7
    remaining = ctx["conn"].execute(
        "SELECT COUNT(*) AS n FROM serials WHERE batch_id = ?",
        (prepared["batch_id"],),
    ).fetchone()["n"]
    assert remaining == 7


def test_second_industry_needs_no_code_change(ctx):
    prepared = prepare_batch(
        ctx["conn"],
        ctx["settings"],
        ctx["packs"]["cosmetics"],
        ctx["issuer"],
        {
            "industry": "cosmetics",
            "details": {
                "brand": "Glow",
                "product_name": "Lip balm",
                "batch_number": "C-2026-01",
                "photo": "/uploads/lip.jpg",
            },
            "units": 2,
            "manufactured_at": "2026-06-01",
            "expires_at": None,
        },
    )
    assert prepared["industry_code"] == 2
    assert prepared["expires_at"] == 0
    rows = ctx["conn"].execute(
        "SELECT serial FROM serials WHERE batch_id = ?", (prepared["batch_id"],)
    ).fetchall()
    assert len(rows) == 2
