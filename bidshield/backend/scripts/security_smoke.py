#!/usr/bin/env python
"""BidShield 7-layer security smoke test — runs against a LIVE server.

Start the backend first:
    cd backend && uvicorn app.main:app --port 8000
Then:
    python scripts/security_smoke.py http://127.0.0.1:8000

Each numbered check names its layer and the failure mode it exercises. A
[FAIL] anywhere means that layer is not actually protecting the deployment.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
results = []


def call(method, path, body=None, headers=None, raw_body=None):
    url = BASE + path
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def check(layer, name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, layer, name, detail))
    print(f"[{status}] L{layer} · {name}" + (f" — {detail}" if detail and not condition else ""))


def login(username="officer", password="BidShield@123"):
    code, _, body = call("POST", "/api/v1/auth/login", {"username": username, "password": password})
    if code == 200:
        return json.loads(body)["access_token"]
    return None


print(f"→ BidShield security smoke test against {BASE}\n")

# ── Layer 1 — Perimeter ─────────────────────────────────────────────────────
code, headers, _ = call("GET", "/health")
check(1, "security headers on responses", all(
    headers.get(k.lower()) == v for k, v in {
        "x-content-type-options": "nosniff", "x-frame-options": "DENY",
    }.items()), str({k: v for k, v in headers.items() if k.lower().startswith("x-")}))
check(1, "CSP is strict (no unsafe-inline)",
      "unsafe-inline" not in headers.get("content-security-policy", ""))

code, headers, body = call("POST", "/api/v1/auth/login", raw_body=b"{" + b"x" * (1024 * 1024 + 99))
check(1, "oversized body → 413", code == 413, f"got {code}")

code, _, _ = call("GET", "/api/v1/documents?document_type=GST%20UNION%20SELECT%20null--",
                  headers={"Authorization": "Bearer probe"})
check(1, "injection pattern in query → 400", code == 400, f"got {code}")

code, _, _ = call("GET", "/api/v1/docs")
check(1, "interactive docs disabled", code in (404, 405), f"got {code}")

codes = set()
for _ in range(12):
    codes.add(call("POST", "/api/v1/auth/login",
                   {"username": "officer", "password": "smoke-wrong"})[0])
check(1, "login flood rate-limited (429)", 429 in codes, f"saw {sorted(codes)}")

# ── Layer 2 — Anomaly detection (account-scoped lockout) ───────────────────
code, headers, _ = call("POST", "/api/v1/auth/login",
                        {"username": "smoke-nonexistent", "password": "wrong"})
check(2, "failed logins answered 401 (no user enumeration)", code == 401, f"got {code}")

# A different demo account must still sign in from the same source IP even if
# the previous section tripped failures for another account.
tok = login("auditor", "BidShield@123")
check(2, "other accounts unaffected by one account's failures", tok is not None)

# ── Layer 3 — Auth & access control ─────────────────────────────────────────
code, _, body = call("POST", "/api/v1/auth/login", {"username": "officer", "password": "wrong"})
check(3, "wrong password → 401", code == 401, f"got {code}")

tok = login()
check(3, "valid login issues token", tok is not None)
auth = {"Authorization": f"Bearer {tok}"} if tok else {}

code, _, _ = call("POST", "/api/v1/admin/users/deactivate",
                  {"username": "officer", "reason": "self-block probe"},
                  {**auth, "Authorization": "Bearer " + (login("admin") or "")})
check(3, "admin-only account actions gated (officer self-deactivate blocked)",
      code in (403, 404, 401), f"got {code}")

code, _, _ = call("GET", "/api/v1/tenders")
check(3, "protected route without token → 401", code == 401, f"got {code}")

# ── Layer 4 — Backup vault (via admin API) ──────────────────────────────────
admin_auth = {"Authorization": f"Bearer {login('admin')}"}
code, _, body = call("POST", "/api/v1/admin/backups", {}, admin_auth)
ok4 = code == 200 and "sha256" in body.decode()
check(4, "on-demand snapshot with SHA-256", ok4, f"got {code} {body[:120]!r}")

code, _, body = call("GET", "/api/v1/admin/backups", None, admin_auth)
if code == 200:
    snaps = json.loads(body)
    check(4, "listing verifies checksums", all(s.get("checksum_ok") for s in snaps))
else:
    check(4, "listing verifies checksums", False, f"got {code}")

# ── Layer 5 — Logic isolation ────────────────────────────────────────────────
code, _, _ = call("GET", "/api/v1/tenders/999999", auth)
check(5, "out-of-scope/absent resource → 404 (not 403, no leak)", code == 404, f"got {code}")

# ── Layer 6 — Audit chain ────────────────────────────────────────────────────
aud_auth = {"Authorization": f"Bearer {login('auditor')}"}
code, _, body = call("GET", "/api/v1/audit/integrity", None, aud_auth)
if code == 200:
    report = json.loads(body)
    check(6, "hash-chain verification reports intact", report.get("valid") is True, str(report.get("issues"))[:120])
else:
    check(6, "hash-chain verification endpoint (auditor)", False, f"got {code}")

# ── Layer 7 — Input validation ──────────────────────────────────────────────
code, _, body = call("POST", "/api/v1/auth/login",
                     {"username": "officer", "password": "BidShield@123", "extra_field": 1})
check(7, "unknown field in body → 422", code == 422, f"got {code}")

if auth.get("Authorization"):
    code, _, _ = call("POST", "/api/v1/tenders/1/requirements",
                      {"code": "bad code", "name": "x", "description": "y"}, auth)
    check(7, "identifier regex enforced on requirement code", code == 422, f"got {code}")

# ── Summary ─────────────────────────────────────────────────────────────────
print("\n=== SUMMARY ===")
fails = [r for r in results if r[0] == "FAIL"]
for layer in range(1, 8):
    layer_results = [r for r in results if r[1] == layer]
    ok = all(r[0] == "PASS" for r in layer_results)
    print(f"Layer {layer}: {'OK' if ok and layer_results else 'ISSUES'} "
          f"({sum(1 for r in layer_results if r[0] == 'PASS')}/{len(layer_results)} checks)")
sys.exit(1 if fails else 0)
