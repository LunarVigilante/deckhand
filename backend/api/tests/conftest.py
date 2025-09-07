import os
import sys
import base64
import os as _os
import types
import time as _time
import pytest

# Ensure backend package is importable when running from repo root
CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.api.app import create_app  # noqa: E402
from flask_jwt_extended import create_access_token  # noqa: E402


class FakeStore:
    """Minimal in-memory Redis-like store for tests"""
    def __init__(self):
        self._data = {}
        self._exp = {}

    def _gc(self):
        now = int(_time.time())
        for k in list(self._exp.keys()):
            if self._exp[k] <= now:
                self._data.pop(k, None)
                self._exp.pop(k, None)

    def get(self, key):
        self._gc()
        return self._data.get(key)

    def setex(self, key, ttl, value):
        self._data[key] = str(value)
        self._exp[key] = int(_time.time()) + int(ttl)
        return True

    def incr(self, key):
        self._gc()
        v = int(self._data.get(key, "0")) + 1
        self._data[key] = str(v)
        return v

    def expire(self, key, ttl):
        self._exp[key] = int(_time.time()) + int(ttl)
        return True

    def exists(self, key):
        self._gc()
        return 1 if key in self._data else 0


@pytest.fixture(scope="session")
def app():
    # Set required encryption key for exports
    _os.environ.setdefault("PII_ENCRYPTION_KEY", base64.b64encode(_os.urandom(32)).decode())
    _os.environ.setdefault("ENCRYPTION_KEY_ID", "test-key-v1")
    _os.environ.setdefault("FLASK_ENV", "testing")
    _os.environ.setdefault("JWT_SECRET_KEY", base64.b64encode(_os.urandom(32)).decode())
    _os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

    application = create_app("testing")
    # Install fake token store for limiter and JWT blocklist
    application.extensions["token_store"] = FakeStore()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(app):
    with app.app_context():
        token = create_access_token(identity={"sub": "1"})
    return {"Authorization": f"Bearer {token}"}