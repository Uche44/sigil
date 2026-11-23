"""SQLite storage. Chain state is the source of truth; this holds off-chain data."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS issuers (
    id INTEGER PRIMARY KEY,
    authority TEXT NOT NULL UNIQUE,
    name_hash TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY,
    public_code TEXT NOT NULL UNIQUE,
    issuer_id INTEGER NOT NULL REFERENCES issuers(id),
    issuer_pda TEXT NOT NULL,
    batch_pda TEXT,
    nonce INTEGER NOT NULL,
    industry INTEGER NOT NULL,
    details_json TEXT NOT NULL,
    details_hash TEXT NOT NULL,
    merkle_root TEXT NOT NULL,
    units INTEGER NOT NULL,
    manufactured_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    tx_signature TEXT,
    created_at INTEGER NOT NULL,
    confirmed_at INTEGER,
    recalled_at INTEGER,
    recall_reason INTEGER,
    UNIQUE (issuer_pda, nonce)
);

CREATE TABLE IF NOT EXISTS serials (
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    serial TEXT NOT NULL,
    leaf_index INTEGER NOT NULL,
    PRIMARY KEY (batch_id, serial)
);

CREATE INDEX IF NOT EXISTS serials_serial ON serials (serial);

CREATE TABLE IF NOT EXISTS scan_events (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    serial TEXT,
    scanned_at INTEGER NOT NULL,
    region TEXT,
    country TEXT,
    device_hash TEXT,
    verdict TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS scans_batch_serial ON scan_events (batch_id, serial, scanned_at);
CREATE INDEX IF NOT EXISTS scans_time ON scan_events (scanned_at);

CREATE TABLE IF NOT EXISTS nonces (
    wallet TEXT NOT NULL,
    nonce TEXT NOT NULL,
    message TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (wallet, nonce)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    serial TEXT,
    note TEXT NOT NULL,
    photo_ref TEXT,
    created_at INTEGER NOT NULL
);
"""


def now() -> int:
    return int(time.time())


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA)
