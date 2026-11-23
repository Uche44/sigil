"""Scan-activity hints. Soft signals only. These never prove anything."""

from __future__ import annotations

import hashlib
import hmac
import sqlite3

from .config import Settings


def device_hash(secret: str, ip: str | None, user_agent: str | None) -> str:
    material = f"{ip or ''}|{user_agent or ''}".encode("utf-8")
    return hmac.new(secret.encode(), material, hashlib.sha256).hexdigest()[:32]


def coarse_region(headers: dict) -> tuple[str | None, str | None]:
    """Region comes from the CDN or a demo header; we never geolocate an IP here."""
    region = headers.get("x-sigil-region") or headers.get("x-vercel-ip-country-region")
    country = headers.get("cf-ipcountry") or headers.get("x-vercel-ip-country")
    region = (region or "").strip()[:64] or None
    country = (country or "").strip()[:8] or None
    return region, country


def serial_is_unusual(
    conn: sqlite3.Connection,
    settings: Settings,
    batch_id: int,
    serial: str,
    region: str | None,
    at: int,
) -> bool:
    """Two hints: same code in far-apart places quickly, or many places in a week.

    We do not have precise coordinates, so 'different region' is treated as 'far'.
    An honest shopper can never be flagged by a single scan or by scan count alone.
    """
    if not region:
        return False

    rows = conn.execute(
        """
        SELECT region, scanned_at FROM scan_events
        WHERE batch_id = ? AND serial = ? AND region IS NOT NULL
        ORDER BY scanned_at DESC LIMIT 200
        """,
        (batch_id, serial),
    ).fetchall()

    travel_cutoff = at - settings.travel_window_seconds
    for row in rows:
        if row["region"] != region and row["scanned_at"] >= travel_cutoff:
            return True

    places_cutoff = at - settings.many_places_window_seconds
    places = {
        row["region"]
        for row in rows
        if row["scanned_at"] >= places_cutoff and row["region"]
    }
    places.add(region)
    return len(places) >= settings.many_places_regions


def batch_alert(conn: sqlite3.Connection, settings: Settings, batch_id: int) -> bool:
    """Share of a batch's scanned serials that have produced a suspicious scan."""
    rows = conn.execute(
        """
        SELECT serial, GROUP_CONCAT(DISTINCT region) AS regions, COUNT(*) AS scans
        FROM scan_events
        WHERE batch_id = ? AND serial IS NOT NULL
        GROUP BY serial
        """,
        (batch_id,),
    ).fetchall()
    if len(rows) < settings.batch_alert_min_serials:
        return False
    flagged = sum(1 for row in rows if len((row["regions"] or "").split(",")) >= 2)
    return flagged / len(rows) >= settings.batch_alert_share
