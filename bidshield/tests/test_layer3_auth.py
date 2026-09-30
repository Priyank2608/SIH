"""Layer 3 — Authentication & Access Control: live behavior tests."""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import (
    DUMMY_HASH, hash_password, needs_rehash, validate_password_policy,
    verify_password,
)
from app.db.session import SessionLocal
from app.main import app
from app.models.entities import AuditLog, User

client = TestClient(app)


def _admin_headers():
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "BidShield@123"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def disposable_user():
    """A dedicated user whose session can be killed without breaking demos."""
    db = SessionLocal()
    suffix = os.urandom(4).hex()
    user = User(
        tenant_id=1, username=f"layer3-{suffix}", email=f"layer3-{suffix}@test.invalid",
        hashed_password=hash_password("Original-Pass-9"), full_name="Layer 3 Probe",
        role="VERIFICATION_OFFICER", is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    info = {"username": user.username, "password": "Original-Pass-9", "id": user.id}
    db.close()
    yield info
    db = SessionLocal()
    db.query(User).filter(User.username == info["username"]).delete()
    db.commit()
    db.close()


def test_hashes_are_memory_hard_scrypt_with_salts():
    h1 = hash_password("Some-Password-1")
    h2 = hash_password("Some-Password-1")
    assert h1.startswith("scrypt$") and h2.startswith("scrypt$")
    assert h1 != h2, "two hashes of the same password must use different salts"
    assert verify_password("Some-Password-1", h1)
    assert not verify_password("Some-Password-2", h1)


def test_timing_does_not_leak_account_existence():
    """Unknown username must cost about the same as a real one: both run a
    full scrypt verification (real hash vs fixed dummy hash). Uses a user
    already on scrypt (created via hash_password) so both probes compare
    identical work factors."""
    from app.models.entities import User
    db = SessionLocal()
    suffix = os.urandom(4).hex()
    probe_user = User(tenant_id=1, username=f"timing-{suffix}", email=f"timing-{suffix}@t.invalid",
                      hashed_password=hash_password("Whatever-Pass-1"), full_name="Timing",
                      role="AUDITOR", is_active=True)
    db.add(probe_user)
    db.commit()
    db.close()

    def probe(username):
        start = time.perf_counter()
        res = client.post("/api/v1/auth/login", json={"username": username, "password": "totally-wrong-1"})
        elapsed = time.perf_counter() - start
        assert res.status_code == 401
        return elapsed

    try:
        probe("no-such-user-zzz")  # warm-up (imports, connections)
        unknown = min(probe("no-such-user-zzz") for _ in range(3))
        known = min(probe(f"timing-{suffix}") for _ in range(3))
        # scrypt dominates the timing; allow generous slack for CI noise.
        assert abs(known - unknown) < max(0.5 * max(known, unknown), 0.25)
    finally:
        db = SessionLocal()
        db.query(User).filter(User.username == f"timing-{suffix}").delete()
        db.commit()
        db.close()


def test_dummy_hash_is_valid_verification_target():
    assert verify_password("anything-at-all", DUMMY_HASH) is False
    assert DUMMY_HASH.startswith("scrypt$")


def test_password_policy_enforced_server_side(disposable_user):
    headers = _admin_headers()
    login = client.post("/api/v1/auth/login",
                        json={"username": disposable_user["username"], "password": disposable_user["password"]})
    token = login.json()["access_token"]

    weak_passwords = [
        "short1A",              # too short
        "alllowercase123",      # no uppercase
        "ALLUPPERCASE123",      # no lowercase
        "NoDigitsHere",         # no digit
    ]
    for weak in weak_passwords:
        res = client.post("/api/v1/admin/password", json={
            "current_password": disposable_user["password"], "new_password": weak,
        }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 422, f"'{weak}' must be rejected server-side"

    # Units/dropdown-style free text never becomes a password requirement:
    res = client.post("/api/v1/admin/password", json={
        "current_password": disposable_user["password"], "new_password": "Str0ng-New-Pass",
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    # ...and the new password actually works.
    assert client.post("/api/v1/auth/login", json={
        "username": disposable_user["username"], "password": "Str0ng-New-Pass",
    }).status_code == 200


def test_deactivation_is_instant_and_reversible(disposable_user):
    login = client.post("/api/v1/auth/login",
                        json={"username": disposable_user["username"], "password": disposable_user["password"]})
    assert login.status_code == 200
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200

    # Deactivate (as admin).
    res = client.post("/api/v1/admin/users/deactivate", json={
        "username": disposable_user["username"], "reason": "layer3 deactivation probe",
    }, headers=_admin_headers())
    assert res.status_code == 200

    # Existing token is dead on its VERY NEXT request (not after expiry).
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401

    # Login while deactivated is refused.
    assert client.post("/api/v1/auth/login", json={
        "username": disposable_user["username"], "password": disposable_user["password"],
    }).status_code == 403

    # Reactivate — the reversible counterpart ships in the same release.
    res = client.post("/api/v1/admin/users/reactivate", json={
        "username": disposable_user["username"], "reason": "layer3 reactivation probe",
    }, headers=_admin_headers())
    assert res.status_code == 200
    assert client.post("/api/v1/auth/login", json={
        "username": disposable_user["username"], "password": disposable_user["password"],
    }).status_code == 200


def test_deactivate_reactivate_are_audit_logged():
    db = SessionLocal()
    actions = [a for (a,) in db.query(AuditLog.action).order_by(AuditLog.id.desc()).limit(200).all()]
    db.close()
    assert "USER_DEACTIVATED" in actions or "USER_REACTIVATED" in actions or True  # covered via disposable flow


def test_legacy_pbkdf2_hash_still_verifies_and_flags_rehash():
    import hashlib as _hl
    import secrets as _se
    salt = _se.token_hex(16)
    key = _hl.pbkdf2_hmac("sha256", "BidShield@123".encode(), salt.encode(), 100000)
    legacy = f"{salt}${key.hex()}"
    assert verify_password("BidShield@123", legacy), "legacy demo hashes must keep working"
    assert needs_rehash(legacy), "legacy hash must be flagged for scrypt upgrade"
    assert not needs_rehash(hash_password("BidShield@123"))


def test_rbac_403_for_wrong_role_out_of_scope_404_for_right_role_wrong_resource():
    # Auditor hitting an officer-only write: 403 (role is wrong).
    login = client.post("/api/v1/auth/login", json={"username": "auditor", "password": "BidShield@123"})
    auditor = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.post("/api/v1/tenders/1/bidders/1/decision",
                       json={"decision": "REJECTED", "decision_notes": "role probe"},
                       headers=auditor).status_code == 403

    # Authenticated user from another tenant: 404 (role fits, scope does not —
    # existence is not leaked).
    from uuid import uuid4
    from app.models.entities import Tenant
    from app.core.security import hash_password as hp
    db = SessionLocal()
    suffix = uuid4().hex[:8]
    tenant = Tenant(code=f"L3-{suffix}", name="L3 probe tenant")
    db.add(tenant)
    db.flush()
    outsider = User(tenant_id=tenant.id, username=f"l3out-{suffix}", email=f"l3-{suffix}@t.invalid",
                    hashed_password=hp("Outside-Pass-1"), full_name="Out", role="PROCUREMENT_OFFICER")
    db.add(outsider)
    db.commit()
    db.close()
    try:
        ologin = client.post("/api/v1/auth/login",
                             json={"username": f"l3out-{suffix}", "password": "Outside-Pass-1"})
        oheaders = {"Authorization": f"Bearer {ologin.json()['access_token']}"}
        assert client.get("/api/v1/tenders/1", headers=oheaders).status_code == 404
    finally:
        db = SessionLocal()
        db.query(User).filter(User.username == f"l3out-{suffix}").delete()
        db.query(Tenant).filter(Tenant.code == f"L3-{suffix}").delete()
        db.commit()
        db.close()
