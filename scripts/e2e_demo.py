"""End-to-end devnet demo: register a producer, verify it, create a batch,
confirm it, then check a serial through the public verify endpoint.

Runs entirely from keypairs, so it works without a browser. The browser flow
does exactly the same instructions through the producer and admin pages.

Prerequisites:
  - program deployed, registry initialised (scripts/solana_admin.py init-registry)
  - API running with the same SIGIL_PROGRAM_ID and SIGIL_ADMIN_PUBKEYS

Usage:
  python scripts/e2e_demo.py --admin-keypair .deployer.json
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

import httpx
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey

sys.path.insert(0, str(Path(__file__).resolve().parent))

from solana_admin import (  # noqa: E402
    SYSTEM_PROGRAM,
    account,
    batch_pda,
    disc,
    issuer_pda,
    load_keypair,
    registry_pda,
    rpc,
    send,
)

MEDICINE_DETAILS = {
    "product_name": "Paracetamol 500mg",
    "manufacturer": "Acme Pharma",
    "regulator_registration_number": "NAFDAC-1234",
    "batch_number": "B-2026-001",
    "manufacture_date": "2026-11-01",
    "expiry_date": "2028-11-01",
    "photo": "https://example.com/paracetamol.jpg",
}

PROFILE = {
    "name": "Acme Pharma",
    "country": "Nigeria",
    "regulator_numbers": {"NAFDAC": "01-2345"},
    "documents": ["https://example.com/acme-licence.pdf"],
    "contact_email": "quality@acme.example",
}


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.client = httpx.Client(timeout=60)

    def request(self, method: str, path: str, token: str | None = None, **kwargs):
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self.client.request(method, f"{self.base}{path}", headers=headers, **kwargs)
        if response.status_code >= 400:
            raise SystemExit(f"{method} {path} -> {response.status_code}: {response.text}")
        return response.json()

    def get(self, path: str, token: str | None = None, **kwargs):
        return self.request("GET", path, token, **kwargs)

    def post(self, path: str, body=None, token: str | None = None, **kwargs):
        return self.request("POST", path, token, json=body, **kwargs)


def sign_in(api: Api, keypair: Keypair) -> tuple[str, dict]:
    wallet = str(keypair.pubkey())
    challenge = api.post("/api/v1/auth/nonce", {"wallet": wallet})
    message = challenge["message"]
    signature = str(keypair.sign_message(message.encode("utf-8")))
    result = api.post(
        "/api/v1/auth/verify",
        {"wallet": wallet, "nonce": challenge["nonce"], "signature": signature},
    )
    return result["token"], result["issuer"]


def ensure_funded(url: str, keypair: Keypair, lamports: int = 2_000_000_000) -> None:
    balance = rpc(url, "getBalance", [str(keypair.pubkey())])["value"]
    if balance >= 100_000_000:
        print(f"  balance {balance / 1e9:.2f} SOL")
        return
    print("  requesting a devnet airdrop…")
    signature = rpc(url, "requestAirdrop", [str(keypair.pubkey()), lamports])
    for _ in range(40):
        status = rpc(
            url,
            "getSignatureStatuses",
            [[signature], {"searchTransactionHistory": True}],
        )["value"][0]
        if status and status.get("confirmationStatus") in ("confirmed", "finalized"):
            print(f"  funded: {signature}")
            return
        time.sleep(1)
    raise SystemExit("airdrop did not confirm; try again later")


def register_issuer(url: str, program: Pubkey, keypair: Keypair, name_hash: bytes) -> None:
    issuer = issuer_pda(program, keypair.pubkey())
    if account(url, issuer) is not None:
        print("  issuer already on-chain")
        return
    instruction = Instruction(
        program,
        disc("register_issuer") + name_hash,
        [
            AccountMeta(registry_pda(program), False, True),
            AccountMeta(keypair.pubkey(), True, True),
            AccountMeta(issuer, False, True),
            AccountMeta(SYSTEM_PROGRAM, False, False),
        ],
    )
    print(f"  register_issuer {send(url, keypair, instruction)}")


def verify_issuer(url: str, program: Pubkey, admin: Keypair, wallet: Pubkey) -> None:
    issuer = issuer_pda(program, wallet)
    existing = account(url, issuer)
    if existing is not None and existing[72] == 1:
        print("  issuer already verified")
        return
    instruction = Instruction(
        program,
        disc("set_issuer_status") + struct.pack("<B", 1),
        [
            AccountMeta(registry_pda(program), False, False),
            AccountMeta(admin.pubkey(), True, False),
            AccountMeta(issuer_pda(program, wallet), False, True),
        ],
    )
    print(f"  set_issuer_status(Verified) {send(url, admin, instruction)}")

def create_batch(
    url: str,
    program: Pubkey,
    producer: Keypair,
    prepared: dict,
) -> tuple[Pubkey, str]:
    issuer = issuer_pda(program, producer.pubkey())
    nonce = int(prepared["nonce"])
    batch = batch_pda(program, issuer, nonce)
    data = (
        disc("create_batch")
        + struct.pack("<Q", nonce)
        + struct.pack("<B", prepared["industry_code"])
        + bytes.fromhex(prepared["merkle_root"])
        + bytes.fromhex(prepared["details_hash"])
        + struct.pack("<I", prepared["units"])
        + struct.pack("<q", prepared["manufactured_at"])
        + struct.pack("<q", prepared["expires_at"])
    )
    instruction = Instruction(
        program,
        data,
        [
            AccountMeta(issuer, False, False),
            AccountMeta(producer.pubkey(), True, True),
            AccountMeta(batch, False, True),
            AccountMeta(SYSTEM_PROGRAM, False, False),
        ],
    )
    return batch, send(url, producer, instruction)


def recall_batch(url: str, program: Pubkey, producer: Keypair, batch: Pubkey) -> None:
    instruction = Instruction(
        program,
        disc("recall_batch") + struct.pack("<B", 1),
        [
            AccountMeta(issuer_pda(program, producer.pubkey()), False, False),
            AccountMeta(producer.pubkey(), True, False),
            AccountMeta(batch, False, True),
        ],
    )
    print(f"  recall_batch {send(url, producer, instruction)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--rpc", default="https://api.devnet.solana.com")
    parser.add_argument("--program", default="A1JYKRSENgPY1Zqa9GjT41m4LuyqMv9dgqeNQ6bSh6HF")
    parser.add_argument("--admin-keypair", type=Path, default=Path(".deployer.json"))
    parser.add_argument("--producer-keypair", type=Path, default=Path(".producer.json"))
    parser.add_argument("--units", type=int, default=5)
    parser.add_argument("--recall", action="store_true", help="recall the batch after checking it")
    options = parser.parse_args()

    program = Pubkey.from_string(options.program)
    admin = load_keypair(options.admin_keypair)

    if options.producer_keypair.exists():
        producer = load_keypair(options.producer_keypair)
    else:
        producer = Keypair()
        options.producer_keypair.write_text(json.dumps(list(bytes(producer))))
        options.producer_keypair.chmod(0o600)
        print(f"created producer keypair {options.producer_keypair}")

    api = Api(options.api)

    print("producer sign-in")
    ensure_funded(options.rpc, producer)
    producer_token, producer_me = sign_in(api, producer)
    print(f"  wallet {producer.pubkey()}")

    print("company profile")
    profile = api.post("/api/v1/issuers", PROFILE, token=producer_token)
    name_hash = bytes(profile["instruction"]["name_hash"]) if profile["instruction"] else bytes.fromhex(producer_me["name_hash"])
    register_issuer(options.rpc, program, producer, name_hash)

    print("admin sign-in")
    sign_in(api, admin)
    verify_issuer(options.rpc, program, admin, producer.pubkey())

    print("create batch")
    prepared = api.post(
        "/api/v1/batches/prepare",
        {
            "industry": "medicine",
            "details": MEDICINE_DETAILS,
            "units": options.units,
            "manufactured_at": "2026-11-01",
            "expires_at": "2028-11-01",
        },
        token=producer_token,
    )
    batch_address, signature = create_batch(options.rpc, program, producer, prepared)
    batch = api.post(
        f"/api/v1/batches/{prepared['batch_id']}/confirm",
        {"tx_signature": signature},
        token=producer_token,
    )
    print(f"  batch {batch_address}")
    print(f"  merkle root {batch['merkle_root']}")

    serials = api.get(
        f"/api/v1/batches/{prepared['batch_id']}/serials?limit=1",
        token=producer_token,
    )["serials"]
    serial = serials[0]

    def check(label: str) -> dict:
        result = api.get(
            f"/api/v1/verify/{batch['public_code']}/{serial}",
            params={"proof": "true"},
        )
        print(f"  {label}: {result['verdict']} — {result['message']}")
        return result

    print("shopper check")
    result = check("before recall")
    config = api.get("/api/v1/config")

    print()
    print("demo links")
    print(f"  shopper  {config['web_base_url']}/v/{batch['public_code']}/{serial}")
    print(f"  producer {config['web_base_url']}/producer")
    print(f"  admin    {config['web_base_url']}/admin")
    print()
    print(f"  public code {batch['public_code']}")
    print(f"  serial      {serial}")
    print(f"  proof root  {result['proof']['root'] if result['proof'] else 'n/a'}")

    if options.recall:
        print("recall")
        recall_batch(options.rpc, program, producer, batch_address)
        api.post(
            f"/api/v1/batches/{prepared['batch_id']}/recall/confirm",
            {"reason": 1},
            token=producer_token,
        )
        time.sleep(3)
        check("after recall")


if __name__ == "__main__":
    main()
