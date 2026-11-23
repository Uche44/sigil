"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = API_DIR.parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    rpc_url: str = "https://api.devnet.solana.com"
    program_id: str = "A1JYKRSENgPY1Zqa9GjT41m4LuyqMv9dgqeNQ6bSh6HF"
    db_path: Path = API_DIR / "sigil.db"
    uploads_dir: Path = API_DIR / "uploads"
    packs_dir: Path = REPO_DIR / "packs"
    public_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    admin_pubkeys: frozenset[str] = field(default_factory=frozenset)
    token_secret: str = "dev-only-change-me"
    device_secret: str = "dev-only-change-me-too"
    token_ttl_seconds: int = 60 * 60 * 12
    nonce_ttl_seconds: int = 5 * 60
    chain_cache_seconds: int = 20
    scan_retention_days: int = 90
    max_units: int = 100_000
    # Scan-hint thresholds
    travel_window_seconds: int = 60 * 60
    many_places_regions: int = 3
    many_places_window_seconds: int = 7 * 24 * 60 * 60
    batch_alert_share: float = 0.2
    batch_alert_min_serials: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        admins = frozenset(
            item.strip()
            for item in os.environ.get("SIGIL_ADMIN_PUBKEYS", "").split(",")
            if item.strip()
        )
        return cls(
            rpc_url=os.environ.get("SIGIL_RPC_URL", cls.rpc_url),
            program_id=os.environ.get("SIGIL_PROGRAM_ID", cls.program_id),
            db_path=Path(os.environ.get("SIGIL_DB_PATH", cls.db_path)),
            uploads_dir=Path(os.environ.get("SIGIL_UPLOADS_DIR", cls.uploads_dir)),
            packs_dir=Path(os.environ.get("SIGIL_PACKS_DIR", cls.packs_dir)),
            public_base_url=os.environ.get(
                "SIGIL_PUBLIC_BASE_URL", cls.public_base_url
            ).rstrip("/"),
            web_base_url=os.environ.get(
                "SIGIL_WEB_BASE_URL", cls.web_base_url
            ).rstrip("/"),
            cors_origins=tuple(
                item.strip()
                for item in os.environ.get(
                    "SIGIL_CORS_ORIGINS", "http://localhost:3000"
                ).split(",")
                if item.strip()
            ),
            admin_pubkeys=admins,
            token_secret=os.environ.get("SIGIL_TOKEN_SECRET", cls.token_secret),
            device_secret=os.environ.get("SIGIL_DEVICE_SECRET", cls.device_secret),
            token_ttl_seconds=_int("SIGIL_TOKEN_TTL", cls.token_ttl_seconds),
            nonce_ttl_seconds=_int("SIGIL_NONCE_TTL", cls.nonce_ttl_seconds),
            chain_cache_seconds=_int("SIGIL_CHAIN_CACHE", cls.chain_cache_seconds),
            scan_retention_days=_int(
                "SIGIL_SCAN_RETENTION_DAYS", cls.scan_retention_days
            ),
            max_units=_int("SIGIL_MAX_UNITS", cls.max_units),
        )
