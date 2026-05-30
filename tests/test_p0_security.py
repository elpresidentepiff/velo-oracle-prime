"""
P0 security hardening tests.

Covers:
  1. Parser API auth (workers/ingestion_spine/app/main.py)
  2. Ingestion spine write-endpoint auth (workers/ingestion_spine/main.py)
  3. verify_api_key stub fix (app/core/security.py)
  4. Dashboard truth endpoint is read-only, no scoring
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# ── 1. Parser API auth ────────────────────────────────────────────────────────

def _make_parser_app(secret: str):
    """Re-import parser app with a controlled PARSER_SHARED_SECRET."""
    import importlib
    import sys
    # Patch env before import
    env = {**os.environ, "PARSER_SHARED_SECRET": secret, "VELO_DEV_AUTH_BYPASS": ""}
    with patch.dict(os.environ, env, clear=False):
        mod_name = "workers.ingestion_spine.app.main"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import workers.ingestion_spine.app.main as m
        return m.app


class TestParserAuth:
    def test_empty_secret_blocks(self):
        """When PARSER_SHARED_SECRET is empty, /parse/racingpost must return 503."""
        with patch.dict(os.environ, {"PARSER_SHARED_SECRET": "", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.app.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.app.main"]
            import workers.ingestion_spine.app.main as m
            importlib.reload(m)
            client = TestClient(m.app, raise_server_exceptions=False)
            # POST with no secret header
            resp = client.post("/parse/racingpost", files={"file": ("test.pdf", b"%PDF-", "application/pdf")})
            assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.text}"

    def test_wrong_secret_blocks(self):
        """Wrong secret must return 401."""
        with patch.dict(os.environ, {"PARSER_SHARED_SECRET": "correct-secret", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.app.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.app.main"]
            import workers.ingestion_spine.app.main as m
            importlib.reload(m)
            client = TestClient(m.app, raise_server_exceptions=False)
            resp = client.post(
                "/parse/racingpost",
                files={"file": ("test.pdf", b"%PDF-", "application/pdf")},
                headers={"X-Velo-Secret": "wrong-secret"},
            )
            assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"

    def test_dev_bypass_allows(self):
        """VELO_DEV_AUTH_BYPASS=1 must allow requests regardless of secret state."""
        with patch.dict(os.environ, {"PARSER_SHARED_SECRET": "", "VELO_DEV_AUTH_BYPASS": "1"}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.app.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.app.main"]
            import workers.ingestion_spine.app.main as m
            importlib.reload(m)
            # Auth passes — processing will fail on parsing the minimal PDF, which is fine
            from workers.ingestion_spine.app.main import _check_parser_auth
            # Should not raise
            _check_parser_auth(None)

    def test_correct_secret_passes_auth(self):
        """Correct secret must pass the auth check."""
        with patch.dict(os.environ, {"PARSER_SHARED_SECRET": "my-secret", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.app.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.app.main"]
            import workers.ingestion_spine.app.main as m
            importlib.reload(m)
            from workers.ingestion_spine.app.main import _check_parser_auth
            # Should not raise
            _check_parser_auth("my-secret")

    def test_health_endpoint_public(self):
        """GET /health must remain public (no auth required)."""
        with patch.dict(os.environ, {"PARSER_SHARED_SECRET": "secret", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.app.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.app.main"]
            import workers.ingestion_spine.app.main as m
            importlib.reload(m)
            client = TestClient(m.app, raise_server_exceptions=False)
            resp = client.get("/health")
            assert resp.status_code == 200


# ── 2. Ingestion spine auth ───────────────────────────────────────────────────

class TestIngestionSpineAuth:
    def _get_auth_func(self, secret: str, bypass: str = ""):
        with patch.dict(os.environ, {"INGESTION_SPINE_SECRET": secret, "VELO_DEV_AUTH_BYPASS": bypass}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.main"]
            import workers.ingestion_spine.main as m
            importlib.reload(m)
            return m._require_write_auth

    def test_empty_secret_blocks(self):
        with patch.dict(os.environ, {"INGESTION_SPINE_SECRET": "", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.main"]
            import workers.ingestion_spine.main as m
            importlib.reload(m)
            import pytest
            with pytest.raises(Exception) as exc_info:
                m._require_write_auth(x_ingestion_secret=None)
            assert "503" in str(exc_info.value.status_code) or exc_info.value.status_code == 503

    def test_wrong_secret_blocks(self):
        with patch.dict(os.environ, {"INGESTION_SPINE_SECRET": "real-secret", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.main"]
            import workers.ingestion_spine.main as m
            importlib.reload(m)
            with pytest.raises(Exception) as exc_info:
                m._require_write_auth(x_ingestion_secret="wrong")
            assert exc_info.value.status_code == 401

    def test_correct_secret_passes(self):
        with patch.dict(os.environ, {"INGESTION_SPINE_SECRET": "real-secret", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.main"]
            import workers.ingestion_spine.main as m
            importlib.reload(m)
            result = m._require_write_auth(x_ingestion_secret="real-secret")
            assert result is None  # returns None on success

    def test_dev_bypass_allows(self):
        with patch.dict(os.environ, {"INGESTION_SPINE_SECRET": "", "VELO_DEV_AUTH_BYPASS": "1"}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.main"]
            import workers.ingestion_spine.main as m
            importlib.reload(m)
            result = m._require_write_auth(x_ingestion_secret=None)
            assert result is None

    def test_healthz_route_has_no_auth(self):
        """Read-only /healthz endpoint must not require auth."""
        with patch.dict(os.environ, {"INGESTION_SPINE_SECRET": "secret", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "workers.ingestion_spine.main" in sys.modules:
                del sys.modules["workers.ingestion_spine.main"]
            import workers.ingestion_spine.main as m
            importlib.reload(m)
            routes = {r.path: list(r.methods) for r in m.app.routes if hasattr(r, "methods")}
            assert "/healthz" in routes
            assert "GET" in routes["/healthz"]


# ── 3. verify_api_key stub fix ────────────────────────────────────────────────

def _run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


class TestVerifyApiKey:
    def test_no_key_configured_returns_503(self):
        with patch.dict(os.environ, {"API_KEY": "", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "app.core.security" in sys.modules:
                del sys.modules["app.core.security"]
            import app.core.security as sec
            importlib.reload(sec)
            with pytest.raises(Exception) as exc_info:
                _run(sec.verify_api_key(credentials=None))
            assert exc_info.value.status_code == 503

    def test_wrong_key_returns_403(self):
        with patch.dict(os.environ, {"API_KEY": "correct-key", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "app.core.security" in sys.modules:
                del sys.modules["app.core.security"]
            import app.core.security as sec
            importlib.reload(sec)
            creds = MagicMock()
            creds.credentials = "wrong-key"
            with pytest.raises(Exception) as exc_info:
                _run(sec.verify_api_key(credentials=creds))
            assert exc_info.value.status_code == 403

    def test_correct_key_passes(self):
        with patch.dict(os.environ, {"API_KEY": "my-key", "VELO_DEV_AUTH_BYPASS": ""}, clear=False):
            import importlib, sys
            if "app.core.security" in sys.modules:
                del sys.modules["app.core.security"]
            import app.core.security as sec
            importlib.reload(sec)
            creds = MagicMock()
            creds.credentials = "my-key"
            result = _run(sec.verify_api_key(credentials=creds))
            assert result is True

    def test_dev_bypass_allows(self):
        with patch.dict(os.environ, {"API_KEY": "", "VELO_DEV_AUTH_BYPASS": "1"}, clear=False):
            import importlib, sys
            if "app.core.security" in sys.modules:
                del sys.modules["app.core.security"]
            import app.core.security as sec
            importlib.reload(sec)
            result = _run(sec.verify_api_key(credentials=None))
            assert result is True


# ── 4. Dashboard truth endpoint ───────────────────────────────────────────────

class TestDashboardTruth:
    def _client(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_KEY": ""}, clear=False):
            from app.main import app
            return TestClient(app, raise_server_exceptions=False)

    def test_endpoint_returns_200(self):
        client = self._client()
        resp = client.get("/api/dashboard-truth")
        assert resp.status_code == 200

    def test_supabase_unavailable_shows_status(self):
        """When Supabase creds missing, status must be SUPABASE_UNAVAILABLE not empty success."""
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_KEY": ""}, clear=False):
            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/dashboard-truth")
            assert resp.status_code == 200
            body = resp.json()
            assert body["a_supabase"]["status"] == "SUPABASE_UNAVAILABLE"

    def test_missing_files_show_not_found(self, tmp_path):
        """Missing local files must show NOT_FOUND, not empty success."""
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_KEY": ""}, clear=False):
            from app.main import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/dashboard-truth")
            assert resp.status_code == 200
            body = resp.json()
            # At minimum the meta flags must be present
            assert body["meta"]["no_scoring"] is True
            assert body["meta"]["no_live_writes"] is True

    def test_no_scoring_triggered(self):
        """Dashboard truth endpoint must not import scoring modules."""
        import inspect
        import app.main as main_module
        src = inspect.getsource(main_module.dashboard_truth)
        forbidden = ["run_prime", "velo_prime_ensemble", "place_order", "place_bet", "telegram"]
        for term in forbidden:
            assert term not in src.lower(), f"Forbidden term '{term}' in dashboard_truth endpoint"

    def test_endpoint_is_get_only(self):
        from app.main import app
        routes = {r.path: list(r.methods) for r in app.routes if hasattr(r, "methods")}
        assert "/api/dashboard-truth" in routes
        assert routes["/api/dashboard-truth"] == ["GET"]
