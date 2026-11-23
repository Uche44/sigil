"""Merkle tree over unit serials.

Leaf    = SHA-256("sigil:leaf:v1" || batch_pda_bytes || serial_bytes)
Node    = SHA-256("sigil:node:v1" || left || right)
Odd levels duplicate the last node.

The root is committed on-chain, so the server cannot invent valid serials
after a batch has been signed. Verification happens off-chain; a client may
check the proof against the on-chain root itself.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Sequence

from .canonical import canonical_json_bytes

LEAF_PREFIX = b"sigil:leaf:v1"
NODE_PREFIX = b"sigil:node:v1"

HASH_BYTES = 32


class MerkleError(ValueError):
    pass


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(batch_pda: bytes, serial: bytes) -> bytes:
    return sha256(LEAF_PREFIX + batch_pda + serial)


def node_hash(left: bytes, right: bytes) -> bytes:
    return sha256(NODE_PREFIX + left + right)


def details_hash(details: dict) -> bytes:
    return sha256(canonical_json_bytes(details))


def serial_leaves(batch_pda: bytes, serials: Iterable[bytes]) -> list[bytes]:
    return [leaf_hash(batch_pda, serial) for serial in serials]


@dataclass(frozen=True)
class ProofStep:
    sibling: bytes
    left: bool

    def to_json(self) -> dict:
        return {"sibling": self.sibling.hex(), "left": self.left}

    @classmethod
    def from_json(cls, value: dict) -> "ProofStep":
        return cls(sibling=bytes.fromhex(value["sibling"]), left=bool(value["left"]))


class MerkleTree:
    def __init__(self, leaves: Sequence[bytes]) -> None:
        if not leaves:
            raise MerkleError("a batch needs at least one leaf")
        for leaf in leaves:
            if len(leaf) != HASH_BYTES:
                raise MerkleError("leaves must be 32-byte hashes")
        self.leaves = list(leaves)
        self.levels: list[list[bytes]] = [self.leaves]
        current = self.leaves
        while len(current) > 1:
            padded = current if len(current) % 2 == 0 else current + [current[-1]]
            current = [
                node_hash(padded[i], padded[i + 1])
                for i in range(0, len(padded), 2)
            ]
            self.levels.append(current)

    @classmethod
    def from_serials(cls, batch_pda: bytes, serials: Sequence[bytes]) -> "MerkleTree":
        return cls(serial_leaves(batch_pda, serials))

    @property
    def root(self) -> bytes:
        return self.levels[-1][0]

    @property
    def root_hex(self) -> str:
        return self.root.hex()

    @property
    def leaf_count(self) -> int:
        return len(self.leaves)

    def proof(self, index: int) -> list[ProofStep]:
        if not 0 <= index < len(self.leaves):
            raise MerkleError(f"leaf index {index} out of range")
        steps: list[ProofStep] = []
        position = index
        for level in self.levels[:-1]:
            if len(level) % 2 == 1:
                level = level + [level[-1]]
            sibling_index = position ^ 1
            steps.append(
                ProofStep(sibling=level[sibling_index], left=sibling_index < position)
            )
            position //= 2
        return steps


def verify_proof(leaf: bytes, proof: Sequence[ProofStep], root: bytes) -> bool:
    current = leaf
    for step in proof:
        if step.left:
            current = node_hash(step.sibling, current)
        else:
            current = node_hash(current, step.sibling)
    return current == root
