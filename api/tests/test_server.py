"""HTTP-level smoke tests. No chain calls are needed for these paths."""

from __future__ import annotations

import os
import tempfile

from solders.keypair import Keypair

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
os.environ.setdefault("SIGIL_DB_PATH", _db.name)
os.environ.setdefault("SIGIL_ADMIN_PUBKEYS", "11111111111111111111111111111111")

from fastapi.testclient import TestClient  # noqa: E402

from sigil.server import app  # noqa: E402


def test_health_config_and_packs():
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}

        config = client.get("/api/v1/config").json()
        assert len(config["program_id"]) >= 32
        assert config["registry_pda"]

        industries = client.get("/api/v1/industries").json()["industries"]
        assert {item["id"] for item in industries} == {
            "generic",
            "medicine",
            "cosmetics",
            "food",
            "precious",
        }
        medicine = next(item for item in industries if item["id"] == "medicine")
        assert medicine["expiry_required"] is True
        assert any(field["key"] == "regulator_registration_number" for field in medicine["fields"])


def test_unknown_code_returns_unknown_and_logs():
    with TestClient(app) as client:
        response = client.get("/api/v1/verify/nosuchbatch/AAAAAAAABBBBBBBB")
        assert response.status_code == 200
        body = response.json()
        assert body["verdict"] == "UNKNOWN"
        assert body["reason"] == "batch_not_found"
        assert "not registered" in body["message"].lower()
        assert response.headers["cache-control"] == "no-store"


def test_invalid_serial_is_rejected():
    with TestClient(app) as client:
        response = client.get("/api/v1/verify/nosuchbatch/1234567890123456")
        assert response.status_code == 422


def test_auth_requires_a_real_wallet_and_signature():
    wallet = str(Keypair().pubkey())
    with TestClient(app) as client:
        bad = client.post("/api/v1/auth/nonce", json={"wallet": "not-a-wallet"})
        assert bad.status_code == 422

        nonce_response = client.post("/api/v1/auth/nonce", json={"wallet": wallet})
        assert nonce_response.status_code == 200
        challenge = nonce_response.json()
        assert wallet in challenge["message"]
        assert challenge["nonce"] in challenge["message"]

        wrong = client.post(
            "/api/v1/auth/verify",
            json={
                "wallet": wallet,
                "nonce": challenge["nonce"],
                "signature": "1" * 64,
            },
        )
        assert wrong.status_code == 401


def test_producer_and_admin_endpoints_need_a_session():
    with TestClient(app) as client:
        assert client.post("/api/v1/issuers", json={"name": "Acme"}).status_code == 401
        assert client.get("/api/v1/batches").status_code == 401
        assert client.get("/api/v1/admin/issuers").status_code == 401
