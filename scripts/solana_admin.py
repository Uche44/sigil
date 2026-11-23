"""Small CLI for registry and issuer administration without a browser.

Signs with a local Solana keypair (default ~/.config/solana/id.json) and talks
to the devnet RPC directly. Useful for setup and for repairing a demo.

Usage:
  python scripts/solana_admin.py init-registry
  python scripts/solana_admin.py registry-info
  python scripts/solana_admin.py set-issuer-status <wallet> <0|1|2>
  python scripts/solana_admin.py issuer-info <wallet>
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

import httpx
from solders.account_meta import AccountMeta
from solders.hash import Hash
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction

SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
DEFAULT_KEYPAIR = Path.home() / ".config" / "solana" / "id.json"

STATUS_LABELS = {0: "Pending", 1: "Verified", 2: "Suspended"}


def disc(name: str) -> bytes:
    return hashlib.sha256(f"global:{name}".encode()).digest()[:8]


def rpc(url: str, method: str, params: list) -> dict:
    response = httpx.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise SystemExit(f"RPC error: {body['error']}")
    return body["result"]


def send(url: str, payer: Keypair, instruction: Instruction) -> str:
    blockhash = Hash.from_string(
        rpc(url, "getLatestBlockhash", [{"commitment": "confirmed"}])["value"][
            "blockhash"
        ]
    )
    transaction = Transaction.new_signed_with_payer(
        [instruction], payer.pubkey(), [payer], blockhash
    )
    encoded = base64.b64encode(bytes(transaction)).decode()
    signature = rpc(
        url,
        "sendTransaction",
        [encoded, {"encoding": "base64", "skipPreflight": False}],
    )
    for _ in range(40):
        status = rpc(
            url, "getSignatureStatuses", [[signature], {"searchTransactionHistory": True}]
        )["value"][0]
        if status and status.get("err") is not None:
            raise SystemExit(f"transaction failed: {status['err']}")
        if status and status.get("confirmationStatus") in ("confirmed", "finalized"):
            return signature
        time.sleep(1)
    raise SystemExit("timed out waiting for confirmation")


def account(url: str, address: Pubkey) -> bytes | None:
    result = rpc(
        url,
        "getAccountInfo",
        [str(address), {"encoding": "base64", "commitment": "confirmed"}],
    )
    value = result["value"]
    return None if value is None else base64.b64decode(value["data"][0])


def registry_pda(program: Pubkey) -> Pubkey:
    return Pubkey.find_program_address([b"registry"], program)[0]


def issuer_pda(program: Pubkey, wallet: Pubkey) -> Pubkey:
    return Pubkey.find_program_address([b"issuer", bytes(wallet)], program)[0]


def batch_pda(program: Pubkey, issuer: Pubkey, nonce: int) -> Pubkey:
    return Pubkey.find_program_address(
        [b"batch", bytes(issuer), nonce.to_bytes(8, "little")], program
    )[0]


def decode_issuer(data: bytes) -> dict:
    offset = 8
    authority = str(Pubkey.from_bytes(data[offset : offset + 32]))
    offset += 32
    name_hash = data[offset : offset + 32]
    offset += 32
    status = data[offset]
    offset += 1
    created_at = struct.unpack_from("<q", data, offset)[0]
    offset += 8
    verified_at = struct.unpack_from("<q", data, offset)[0]
    return {
        "authority": authority,
        "name_hash": name_hash.hex(),
        "status": status,
        "status_label": STATUS_LABELS.get(status, "Unknown"),
        "created_at": created_at,
        "verified_at": verified_at,
    }


def load_keypair(path: Path) -> Keypair:
    if not path.exists():
        raise SystemExit(
            f"keypair not found at {path}. Run `solana-keygen new` first."
        )
    return Keypair.from_json(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rpc",
        default=os.environ.get("SIGIL_RPC_URL", "https://api.devnet.solana.com"),
    )
    parser.add_argument(
        "--program",
        default=os.environ.get(
            "SIGIL_PROGRAM_ID", "A1JYKRSENgPY1Zqa9GjT41m4LuyqMv9dgqeNQ6bSh6HF"
        ),
    )
    parser.add_argument("--keypair", type=Path, default=DEFAULT_KEYPAIR)
    parser.add_argument(
        "command",
        choices=["init-registry", "registry-info", "set-issuer-status", "issuer-info"],
    )
    parser.add_argument("args", nargs="*")
    options = parser.parse_args()

    program = Pubkey.from_string(options.program)
    keypair = load_keypair(options.keypair)
    registry = registry_pda(program)

    print(f"cluster  {options.rpc}")
    print(f"program  {program}")
    print(f"registry {registry}")
    print(f"wallet   {keypair.pubkey()}\n")

    if options.command == "registry-info":
        data = account(options.rpc, registry)
        if data is None:
            print("registry does not exist yet. Run init-registry.")
            return
        admin = Pubkey.from_bytes(data[8:40])
        count = struct.unpack_from("<I", data, 40)[0]
        print(json.dumps({"admin": str(admin), "issuer_count": count}, indent=2))
        return

    if options.command == "init-registry":
        if account(options.rpc, registry) is not None:
            print("registry already exists")
            return
        instruction = Instruction(
            program,
            disc("initialize_registry"),
            [
                AccountMeta(registry, False, True),
                AccountMeta(keypair.pubkey(), True, True),
                AccountMeta(SYSTEM_PROGRAM, False, False),
            ],
        )
        signature = send(options.rpc, keypair, instruction)
        print(f"initialized: {signature}")
        return

    if options.command == "issuer-info":
        if not options.args:
            raise SystemExit("usage: issuer-info <wallet>")
        wallet = Pubkey.from_string(options.args[0])
        data = account(options.rpc, issuer_pda(program, wallet))
        if data is None:
            print("issuer does not exist")
            return
        print(json.dumps(decode_issuer(data), indent=2))
        return

    if options.command == "set-issuer-status":
        if len(options.args) != 2:
            raise SystemExit("usage: set-issuer-status <wallet> <0|1|2>")
        wallet = Pubkey.from_string(options.args[0])
        status = int(options.args[1])
        issuer = issuer_pda(program, wallet)
        instruction = Instruction(
            program,
            disc("set_issuer_status") + struct.pack("<B", status),
            [
                AccountMeta(registry, False, False),
                AccountMeta(keypair.pubkey(), True, False),
                AccountMeta(issuer, False, True),
            ],
        )
        signature = send(options.rpc, keypair, instruction)
        print(f"issuer {issuer} -> {STATUS_LABELS.get(status)} ({signature})")
        return


if __name__ == "__main__":
    sys.exit(main())
