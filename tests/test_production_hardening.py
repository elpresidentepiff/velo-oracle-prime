from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services import security_validator
from app.services.velo_prime_service import persist_race_predictions


class _FakeQuery:
    def __init__(self, name: str, fail_message: str | None = None):
        self.name = name
        self.fail_message = fail_message

    def select(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def in_(self, *args, **kwargs):
        return self

    def execute(self):
        if self.fail_message and self.name == "pg_class":
            raise RuntimeError(self.fail_message)
        return SimpleNamespace(data=[])


class _FakeSecurityClient:
    def __init__(self, pg_class_error: str | None = None):
        self.pg_class_error = pg_class_error

    def table(self, name: str):
        return _FakeQuery(name, fail_message=self.pg_class_error)


class _FakeUpsertQuery:
    def __init__(self, parent: "_FakeVerdictsTable", payload: dict, on_conflict: str):
        self.parent = parent
        self.payload = payload
        self.on_conflict = on_conflict

    def execute(self):
        self.parent.payloads.append(dict(self.payload))
        behavior = self.parent.behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


class _FakeVerdictsTable:
    def __init__(self, behaviors: list[object]):
        self.behaviors = list(behaviors)
        self.payloads: list[dict] = []

    def upsert(self, payload: dict, on_conflict: str):
        return _FakeUpsertQuery(self, payload, on_conflict)


class _FakeSupabaseClient:
    def __init__(self, verdicts_table: _FakeVerdictsTable):
        self.verdicts_table = verdicts_table

    def table(self, name: str):
        if name != "velo_verdicts":
            raise AssertionError(f"Unexpected table access: {name}")
        return self.verdicts_table


def _sample_race() -> dict:
    return {
        "race_id": "race-1",
        "region": "uk",
    }


def _sample_predictions() -> list[dict]:
    return [
        {
            "horse": "Signal Horse",
            "horse_id": "horse-1",
            "velo_prime_prob": 0.44,
            "confidence_level": "high",
            "confidence_level_raw": "high",
            "confidence_level_effective": "high",
            "improvement_score": 0.2,
            "market_deception_score": 0.1,
            "release_day_prob": 0.1,
            "place_prob": 0.6,
            "longshot_prob": 0.05,
            "macro_regime_label": "stable",
            "macro_chaos_mode": False,
            "favourite_trap_risk": "normal",
            "ensemble_version": "velo_prime_v1",
            "active_components": ["sqpe"],
            "excluded_from_ensemble": ["shadow"],
            "horse_state": {
                "readiness_state": "ready",
                "release_state": "steady",
                "rest_pattern": "normal",
                "class_move_state": "flat",
                "stable_heat": "warm",
                "jockey_signal": "positive",
                "market_state": "aligned",
                "race_fit_state": "good",
                "chaos_exposure": "low",
                "live_signals": 3,
                "state_evidence": ["signal"],
            },
            "race_archetype": "control",
            "archetype_confidence": "high",
            "archetype_bet_style": "win",
            "archetype_suppression": "none",
            "archetype_trap_flag": False,
            "g_shadow_multiplier": 1.0,
            "g_shadow_flags": [],
            "g_shadow_horse_id": "horse-1",
            "g_shadow_mode": "shadow",
            "a_tier_weak_place_flag": False,
        }
    ]


def test_security_validator_returns_unverified_on_pg_class_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda *_args, **_kwargs: _FakeSecurityClient("permission denied for relation pg_class")),
    )

    result = security_validator.run_security_check()

    assert result["verified"] is False
    assert result["status"] == "error"
    assert result["error_code"] == "permission_denied"
    assert result["metrics"] is None


def test_security_validator_distinguishes_transport_errors(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("connection timed out"))),
    )

    result = security_validator.run_security_check()

    assert result["verified"] is False
    assert result["status"] == "error"
    assert result["error_code"] == "transport_error"


def test_security_validator_reports_partial_coverage_when_rls_check_passes(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda *_args, **_kwargs: _FakeSecurityClient()),
    )

    result = security_validator.run_security_check()

    assert result["status"] == "partial"
    assert result["coverage_scope"] == "partial"
    assert "RLS:runner_results" in result["checked_objects"]
    assert any(item.startswith("views_not_invoker:") for item in result["unchecked_objects"])


def test_persist_retry_does_not_remove_optional_groups_on_unclassified_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    table = _FakeVerdictsTable([RuntimeError("connection reset by peer")])
    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda *_args, **_kwargs: _FakeSupabaseClient(table)),
    )
    monkeypatch.setattr(
        "app.services.velo_prime_service._enrich_full_analysis_from_warehouse",
        lambda predictions, race, sb: predictions,
    )

    ok = persist_race_predictions(_sample_race(), _sample_predictions(), decision_tier="A")

    assert ok is False
    assert len(table.payloads) == 1
    assert "active_components" in table.payloads[0]
    assert "top_horse_readiness_state" in table.payloads[0]


def test_persist_retry_removes_only_proven_bad_group(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    table = _FakeVerdictsTable(
        [
            RuntimeError("Could not find the 'active_components' column of 'velo_verdicts' in the schema cache"),
            SimpleNamespace(data=[{"ok": True}]),
        ]
    )
    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda *_args, **_kwargs: _FakeSupabaseClient(table)),
    )
    monkeypatch.setattr(
        "app.services.velo_prime_service._enrich_full_analysis_from_warehouse",
        lambda predictions, race, sb: predictions,
    )

    ok = persist_race_predictions(_sample_race(), _sample_predictions(), decision_tier="A")

    assert ok is False
    assert len(table.payloads) == 2
    assert "active_components" in table.payloads[0]
    assert "excluded_from_ensemble" in table.payloads[0]
    assert "active_components" not in table.payloads[1]
    assert "excluded_from_ensemble" not in table.payloads[1]
    assert "top_horse_readiness_state" in table.payloads[1]


def test_persist_rejects_missing_required_audit_fields(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    table = _FakeVerdictsTable([SimpleNamespace(data=[{"ok": True}])])
    monkeypatch.setitem(
        sys.modules,
        "supabase",
        SimpleNamespace(create_client=lambda *_args, **_kwargs: _FakeSupabaseClient(table)),
    )
    monkeypatch.setattr(
        "app.services.velo_prime_service._enrich_full_analysis_from_warehouse",
        lambda predictions, race, sb: predictions,
    )

    preds = _sample_predictions()
    preds[0]["horse_id"] = ""

    ok = persist_race_predictions(_sample_race(), preds, decision_tier="A")

    assert ok is False
    assert table.payloads == []


def test_production_config_rejects_wildcard_cors_with_credentials():
    with pytest.raises(ValidationError):
        Settings(API_ENV="production", CORS_ORIGINS=["*"], CORS_ALLOW_CREDENTIALS=True)
