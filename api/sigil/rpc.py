"""Minimal Solana JSON-RPC reader and manual Borsh account decoding.

Kept deliberately small so it can be swapped if AnchorPy or solders lag behind.
Only reads are performed here; every write is signed by a user's wallet.
"""

from __future__ import annotations

import base64
import hashlib
import struct
import time
from dataclasses import dataclass

import httpx
from solders.pubkey import Pubkey

ISSUER_LEN = 8 + 82
BATCH_LEN = 8 + 144
REGISTRY_LEN = 8 + 37

REGISTRY_DISC = hashlib.sha256(b"account:Registry").digest()[:8]
ISSUER_DISC = hashlib.sha256(b"account:Issuer").digest()[:8]
BATCH_DISC = hashlib.sha256(b"account:Batch").digest()[:8]

STATUS_PENDING = 0
STATUS_VERIFIED = 1
STATUS_SUSPENDED = 2
BATCH_ACTIVE = 0
BATCH_RECALLED = 1


class ChainError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryState:
    address: str
    admin: str
    issuer_count: int


@dataclass(frozen=True)
class IssuerState:
    address: str
    authority: str
    name_hash: bytes
    status: int
    created_at: int
    verified_at: int


@dataclass(frozen=True)
class BatchState:
    address: str
    issuer: str
    nonce: int
    industry: int
    merkle_root: bytes
    details_hash: bytes
    units: int
    manufactured_at: int
    expires_at: int
    status: int
    recalled_at: int
    recall_reason: int
    created_at: int


def _take(data: bytes, offset: int, size: int) -> tuple[bytes, int]:
    end = offset + size
    if end > len(data):
        raise ChainError("account data is shorter than expected")
    return data[offset:end], end


def _pubkey(data: bytes, offset: int) -> tuple[str, int]:
    raw, offset = _take(data, offset, 32)
    return str(Pubkey.from_bytes(raw)), offset


def decode_registry(address: str, data: bytes) -> RegistryState:
    if len(data) != REGISTRY_LEN:
        raise ChainError(f"registry account has unexpected size {len(data)}")
    if data[:8] != REGISTRY_DISC:
        raise ChainError("registry account discriminator is wrong")
    admin = str(Pubkey.from_bytes(data[8:40]))
    (issuer_count,) = struct.unpack_from("<I", data, 40)
    return RegistryState(address=address, admin=admin, issuer_count=issuer_count)


def decode_issuer(address: str, data: bytes) -> IssuerState:
    if len(data) != ISSUER_LEN:
        raise ChainError(f"issuer account has unexpected size {len(data)}")
    if data[:8] != ISSUER_DISC:
        raise ChainError("issuer account discriminator is wrong")
    offset = 8
    authority, offset = _pubkey(data, offset)
    name_hash, offset = _take(data, offset, 32)
    (status,) = struct.unpack_from("<B", data, offset)
    offset += 1
    (created_at,) = struct.unpack_from("<q", data, offset)
    offset += 8
    (verified_at,) = struct.unpack_from("<q", data, offset)
    return IssuerState(
        address=address,
        authority=authority,
        name_hash=name_hash,
        status=status,
        created_at=created_at,
        verified_at=verified_at,
    )


def decode_batch(address: str, data: bytes) -> BatchState:
    if len(data) != BATCH_LEN:
        raise ChainError(f"batch account has unexpected size {len(data)}")
    if data[:8] != BATCH_DISC:
        raise ChainError("batch account discriminator is wrong")
    offset = 8
    issuer, offset = _pubkey(data, offset)
    (nonce,) = struct.unpack_from("<Q", data, offset)
    offset += 8
    (industry,) = struct.unpack_from("<B", data, offset)
    offset += 1
    merkle_root, offset = _take(data, offset, 32)
    details_hash, offset = _take(data, offset, 32)
    (units,) = struct.unpack_from("<I", data, offset)
    offset += 4
    (manufactured_at,) = struct.unpack_from("<q", data, offset)
    offset += 8
    (expires_at,) = struct.unpack_from("<q", data, offset)
    offset += 8
    (status,) = struct.unpack_from("<B", data, offset)
    offset += 1
    (recalled_at,) = struct.unpack_from("<q", data, offset)
    offset += 8
    (recall_reason,) = struct.unpack_from("<B", data, offset)
    offset += 1
    (created_at,) = struct.unpack_from("<q", data, offset)
    return BatchState(
        address=address,
        issuer=issuer,
        nonce=nonce,
        industry=industry,
        merkle_root=merkle_root,
        details_hash=details_hash,
        units=units,
        manufactured_at=manufactured_at,
        expires_at=expires_at,
        status=status,
        recalled_at=recalled_at,
        recall_reason=recall_reason,
        created_at=created_at,
    )


def derive_issuer_pda(program_id: str, authority: str) -> str:
    seeds = [b"issuer", bytes(Pubkey.from_string(authority))]
    return str(Pubkey.find_program_address(seeds, Pubkey.from_string(program_id))[0])


def derive_batch_pda(program_id: str, issuer: str, nonce: int) -> str:
    seeds = [b"batch", bytes(Pubkey.from_string(issuer)), nonce.to_bytes(8, "little")]
    return str(Pubkey.find_program_address(seeds, Pubkey.from_string(program_id))[0])


def derive_registry_pda(program_id: str) -> str:
    return str(Pubkey.find_program_address([b"registry"], Pubkey.from_string(program_id))[0])


class RpcReader:
    def __init__(self, rpc_url: str, program_id: str, cache_seconds: int = 20) -> None:
        self.rpc_url = rpc_url
        self.program_id = program_id
        self.cache_seconds = cache_seconds
        self._cache: dict[str, tuple[float, str | None, bytes | None]] = {}

    async def get_account_data(self, address: str, label: str = "program") -> bytes | None:
        cached = self._cache.get(address)
        if cached and time.monotonic() - cached[0] < self.cache_seconds:
            return cached[2]
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [address, {"encoding": "base64", "commitment": "confirmed"}],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(self.rpc_url, json=payload)
        if response.status_code != 200:
            raise ChainError(f"RPC returned HTTP {response.status_code}")
        body = response.json()
        if "error" in body:
            raise ChainError(f"RPC error: {body['error']}")
        value = body.get("result", {}).get("value")
        owner = None if value is None else value.get("owner")
        data = None if value is None else base64.b64decode(value["data"][0])
        if data is not None and owner != self.program_id:
            raise ChainError(f"{label} account is not owned by the Sigil program")
        self._cache[address] = (time.monotonic(), owner, data)
        return data

    async def issuer(self, address: str) -> IssuerState | None:
        data = await self.get_account_data(address, "issuer")
        return None if data is None else decode_issuer(address, data)

    async def batch(self, address: str) -> BatchState | None:
        data = await self.get_account_data(address, "batch")
        return None if data is None else decode_batch(address, data)

    async def registry(self, address: str) -> RegistryState | None:
        data = await self.get_account_data(address, "registry")
        return None if data is None else decode_registry(address, data)

    def forget(self, address: str) -> None:
        self._cache.pop(address, None)
