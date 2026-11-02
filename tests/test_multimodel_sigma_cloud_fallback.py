"""Canonical scorecard fallback tests for ephemeral Railway EOD workers."""

from scripts.ops import run_multimodel_sigma as sigma


class _Response:
    def __init__(self, rows):
        self._rows = rows

    def raise_for_status(self):
        return None

    def json(self):
        return self._rows


def test_load_canonical_rank1_uses_exact_date_model_and_rank(monkeypatch):
    captured = {}

    def fake_get(url, *, params, headers, timeout):
        captured.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return _Response(
            [
                {"race_id": "100", "horse": "Alpha", "score": 0.42},
                {"race_id": "101", "horse": "Beta", "score": 0.31},
            ]
        )

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-secret")
    monkeypatch.setattr(sigma.requests, "get", fake_get)

    rows = sigma._load_canonical_rank1("2026-11-02", "NEW_BUILD_LANE_A_MODEL")

    assert rows == {
        "100": {"horse": "Alpha", "prob": 0.42},
        "101": {"horse": "Beta", "prob": 0.31},
    }
    assert captured["params"] == {
        "select": "race_id,horse,score",
        "run_date": "eq.2026-11-02",
        "model_name": "eq.NEW_BUILD_LANE_A_MODEL",
        "rank": "eq.1",
    }
    assert captured["headers"]["apikey"] == "test-secret"


def test_load_canonical_rank1_without_credentials_is_empty(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert sigma._load_canonical_rank1("2026-11-02", "MODEL") == {}
