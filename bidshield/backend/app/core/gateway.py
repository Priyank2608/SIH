"""Layer 1 — Perimeter & API Gateway.

Pure-ASGI middleware (no BaseHTTPMiddleware — it cannot correctly cap a
streaming request body). Four independent gates, each testable in isolation:

  1. Rate limiting: per-client windows — 120 req/min/IP globally,
     10 req/min/IP on the login endpoint. 429 + Retry-After on breach.
  2. Body cap: JSON/request bodies are capped at 1 MB (413 when over).
     File-upload endpoints can be exempted and enforce max_upload_mb at the
     endpoint instead.
  3. Injection heuristics: request bodies + query strings are scanned for
     common attack patterns (SQLi keywords, <script, ../). This is an ALERT
     layer only — the real defenses are parameterized queries (Layer 5) and
     schema validation (Layer 7). Matches are logged to Layer 2 and rejected
     with 400.
  4. Security headers on EVERY response, including 4xx/5xx errors.

CORS is configured separately in main.py from an explicit allow-list.
"""
import json
import logging
import threading
import time
from collections import defaultdict, deque
from urllib.parse import unquote

from app.core.config import settings
from app.services.anomaly_service import log_security_event

logger = logging.getLogger("bidshield.gateway")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

# Heuristic attack patterns. Deliberately case-insensitive, applied to decoded
# request payloads and query strings. NOT a primary defense.
INJECTION_PATTERNS = [
    "union select", "union all select", "drop table", "insert into",
    "' or '1'='1", "' or 1=1", "\" or \"1\"=\"1", "or 1=1 --",
    "sleep(", "benchmark(", "waitfor delay", "load_file(", "information_schema",
    "<script", "javascript:", "onerror=", "onload=", "onfocus=", "<iframe",
    "../", "..\\", "%2e%2e%2f", "%2e%2e/",
]

RETRY_AFTER_DEFAULT = "60"


def _client_ip(scope) -> str:
    client = scope.get("client")
    return client[0] if client else "0.0.0.0"


def _header_map(scope) -> dict:
    return {k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])}


class GatewayMiddleware:
    """ASGI middleware implementing the Layer 1 gates."""

    def __init__(self, app):
        self.app = app
        self._buckets: dict = defaultdict(deque)   # key -> deque[timestamps]
        self._bucket_lock = threading.Lock()

    # ── ASGI entry ─────────────────────────────────────────────────────
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        ip = _client_ip(scope)

        # (4) Security headers on every response — applied even to rejects.
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                existing = {k.lower() for k, _v in headers}
                for name, value in SECURITY_HEADERS.items():
                    if name.lower() not in existing:
                        headers.append((name.encode("latin-1"), value.encode("latin-1")))
            await send(message)

        # (2) Body-size cap from declared Content-Length.
        if self._body_cap_violation(scope, path):
            await self._reject(send_with_headers, 413,
                               "Request body exceeds the gateway size limit")
            return

        # (3) Injection heuristics. May buffer a JSON body; the returned
        # receive callable REPLAYS it so the app still receives the body.
        receive = await self._scan_injections(scope, receive, path)
        if receive is None:
            await self._reject(send_with_headers, 400, "Request rejected by perimeter scan")
            return

        # (1) Rate limiting (strict on login).
        retry_after = self._rate_limit_check(ip, path)
        if retry_after is not None:
            await self._reject(send_with_headers, 429,
                               "Rate limit exceeded — slow down and retry shortly",
                               extra_headers={"Retry-After": str(retry_after)})
            return

        await self.app(scope, receive, send_with_headers)

    # ── Gate 2: body cap ─────────────────────────────────────────────────
    def _body_limit_for(self, path: str) -> int:
        """Upload endpoints stream large files; the endpoint enforces the
        real per-file cap (max_upload_mb). JSON APIs stay at max_body_bytes."""
        for prefix in [p.strip() for p in settings.max_body_bytes_exempt_prefixes.split(",") if p.strip()]:
            if path.startswith(prefix):
                return settings.max_upload_mb * 1024 * 1024
        return settings.max_body_bytes

    def _body_cap_violation(self, scope, path) -> bool:
        content_length = _header_map(scope).get("content-length")
        if not content_length:
            return False
        try:
            declared = int(content_length)
        except ValueError:
            return False
        return declared > self._body_limit_for(path)

    # ── Gate 3: injection heuristics ─────────────────────────────────────
    async def _scan_injections(self, scope, receive, path):
        """Scan query string and JSON body. Returns the receive callable the
        app must use (replaying a buffered body), or None when blocked."""
        sample = unquote(scope.get("query_string", b"").decode("latin-1"))
        body_bytes = b""

        headers = _header_map(scope)
        content_type = headers.get("content-type", "")
        content_length = headers.get("content-length")
        try:
            declared = int(content_length) if content_length else 0
        except ValueError:
            declared = 0

        replay_needed = False
        # Only buffer JSON bodies for scanning (bounded by the cap).
        if declared and declared <= settings.max_body_bytes and "application/json" in content_type:
            chunks = []
            remaining = declared
            while remaining > 0:
                message = await receive()
                if message["type"] == "http.request":
                    body = message.get("body", b"")
                    chunks.append(body)
                    remaining -= len(body)
                    if not message.get("more_body", False):
                        break
                else:  # http.disconnect
                    return None
            body_bytes = b"".join(chunks)
            replay_needed = True

        haystack = (sample + " " + body_bytes.decode("latin-1", "ignore")).lower()
        for pattern in INJECTION_PATTERNS:
            if pattern in haystack:
                self._log_injection(scope, path, pattern, sample or body_bytes[:300])
                return None

        if not replay_needed:
            return receive

        cached = body_bytes

        async def receive_replay():
            nonlocal cached
            if cached is not None:
                body, cached = cached, None
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return receive_replay

    def _log_injection(self, scope, path, pattern, sample) -> None:
        """Record the hit in Layer 2's security_events (own session — the
        request's dependency session is not open at middleware depth)."""
        try:
            from app.db.session import SessionLocal
            db = SessionLocal()
            try:
                log_security_event(
                    db, kind="INJECTION_PATTERN",
                    source_ip=_client_ip(scope),
                    detail={"path": path, "pattern": pattern,
                            "sample": json.dumps(str(sample[:300]))},
                )
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to persist injection-pattern security event")

    # ── Gate 1: rate limiting ───────────────────────────────────────────
    def _limit_for(self, path: str) -> int:
        if path.rstrip("/").endswith("/auth/login"):
            return settings.login_rate_limit_per_minute
        return settings.rate_limit_per_minute

    def _rate_limit_check(self, ip: str, path: str):
        """Returns None when allowed, or the Retry-After seconds when limited."""
        limit = self._limit_for(path)
        bucket_key = (ip, "login" if limit == settings.login_rate_limit_per_minute else "global")
        now = time.monotonic()
        with self._bucket_lock:
            window = self._buckets[bucket_key]
            while window and now - window[0] > 60.0:
                window.popleft()
            if len(window) >= limit:
                oldest = window[0]
                return max(1, int(60.0 - (now - oldest)) + 1)
            window.append(now)
        return None

    # ── Shared reject helper ─────────────────────────────────────────────
    async def _reject(self, send, status_code: int, detail: str,
                      extra_headers: dict = None) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        headers = [(b"content-type", b"application/json")]
        for name, value in (extra_headers or {}).items():
            headers.append((name.encode("latin-1"), value.encode("latin-1")))
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": body})
