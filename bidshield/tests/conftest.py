import base64
import io

import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def signature_png_data():
    image = Image.new("RGBA", (1000, 280), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line([(90, 185), (170, 70), (230, 190), (320, 115), (410, 160), (525, 95), (610, 170), (740, 80), (875, 145)],
              fill=(16, 43, 70, 255), width=9, joint="curve")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


@pytest.fixture(autouse=True)
def isolate_gateway_for_business_tests(request):
    """Business-flow tests exercise workflows, not the perimeter, so the
    gateway's per-IP limits are relaxed for them (TestClient shares one IP,
    and the RBAC/e2e suites legitimately make dozens of logins per minute).

    test_layer1_gateway.py is excluded — it tests the REAL limits and uses
    per-test client IPs instead. The login-attempt ledger is cleared around
    every test so one file's failed-login probes can never lock a demo
    account for another file (the availability rule from Layer 2 applies to
    the test suite itself).
    """
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.entities import LoginAttempt

    is_gateway_test = "test_layer1_gateway" in request.node.nodeid
    old_global = settings.rate_limit_per_minute
    old_login = settings.login_rate_limit_per_minute

    db = SessionLocal()
    try:
        db.query(LoginAttempt).delete()
        db.commit()
    finally:
        db.close()

    if not is_gateway_test:
        settings.rate_limit_per_minute = 10 ** 9
        settings.login_rate_limit_per_minute = 10 ** 9
    try:
        yield
    finally:
        if not is_gateway_test:
            settings.rate_limit_per_minute = old_global
            settings.login_rate_limit_per_minute = old_login
        db = SessionLocal()
        try:
            db.query(LoginAttempt).delete()
            db.commit()
        finally:
            db.close()
