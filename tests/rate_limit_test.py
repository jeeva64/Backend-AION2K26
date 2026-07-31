"""Verifies slowapi rate limiting returns the envelope 429 when enabled."""

from app.middleware.rate_limit import limiter


def test_login_rate_limit(client):
    limiter.reset()
    limiter.enabled = True
    try:
        for _ in range(10):
            r = client.post("/admin/adminlogin", json={"adminId": "nobody", "password": "wrong"})
            assert r.status_code == 401
        r = client.post("/admin/adminlogin", json={"adminId": "nobody", "password": "wrong"})
        assert r.status_code == 429
        assert r.json().get("success") is False
    finally:
        limiter.enabled = False
