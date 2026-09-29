from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ops import build_canonical_learning_events as learning
from scripts.ops import build_canonical_model_scorecard as scorecard
from scripts.ops import persist_canonical_model_scorecard as persistence

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("position", "status", "settlement", "void"),
    [
        ("1", "FINISHED", "SETTLED", False),
        ("PU", "TERMINAL", "SETTLED", False),
        ("F", "TERMINAL", "SETTLED", False),
        ("UR", "TERMINAL", "SETTLED", False),
        ("BD", "TERMINAL", "SETTLED", False),
        ("RO", "TERMINAL", "SETTLED", False),
        ("DSQ", "TERMINAL", "SETTLED", False),
        ("NR", "NON_RUNNER", "VOID", True),
        ("", "UNKNOWN", "UNSETTLED", False),
    ],
)
def test_runner_lookup_reuses_canonical_outcome_vocabulary(position, status, settlement, void):
    row = scorecard._runner_lookup(
        {"runners": [{"horse": "Truth Horse", "position": position, "sp_dec": 4.33}]},
        "Truth Horse",
    )
    assert row["outcome_status"] == status
    assert row["settlement_status"] == settlement
    assert row["stake_void"] is void


def test_runner_lookup_accepts_position_text_without_losing_terminal_code():
    row = scorecard._runner_lookup(
        {"runners": [{"horse": "Refused", "horse_id": "H4", "position_text": "RO"}]},
        "Refused",
    )
    assert row["outcome_code"] == "RO"
    assert row["outcome_status"] == "TERMINAL"
    assert row["settlement_status"] == "SETTLED"


def test_captain_price_and_settlement_truth_remain_separate(tmp_path, monkeypatch):
    reports = tmp_path / "data" / "reports"
    results = tmp_path / "data" / "results"
    reports.mkdir(parents=True)
    results.mkdir(parents=True)
    packet = {
        "generated_at": "2026-09-28T09:00:00+00:00",
        "model_version": "CAPTAIN_VELO_VALUE_V1",
        "races": [{
            "race_id": "R1", "course": "TEST", "off_time": "14:00",
            "action": "SHADOW_SELECTION",
            "selection": {
                "horse": "Value", "horse_id": "H1", "decimal_odds": 11.0,
                "quoted_expected_edge": 0.12, "market_probability": 0.09,
                "structural_probability": 0.20, "consensus_probability": 0.15,
            },
        }],
    }
    (reports / "captain_velo_shadow_2026_09_28.json").write_text(json.dumps(packet), encoding="utf-8")
    result_payload = {"results": [{
        "race_id": "R1", "course": "TEST", "off": "14:00",
        "runners": [{"horse": "Value", "horse_id": "H1", "position": "1", "sp_dec": 4.33}],
    }]}
    (results / "rp_results_2026_09_28.json").write_text(json.dumps(result_payload), encoding="utf-8")
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_args, **_kwargs: ([], "race_id"))

    rows, _audit = scorecard.build_scorecard("2026-09-28")
    captain = next(row for row in rows if row["model_name"] == "CAPTAIN_VELO_VALUE_V1")
    assert captain["captured_odds_dec"] == 11.0
    assert captain["settled_sp_dec"] == 4.33
    assert captain["sp_dec"] == 4.33
    assert captain["odds_timestamp_before_off"] is True
    assert captain["settlement_status"] == "SETTLED"
    assert captain["official_evaluation_eligible"] is True
    assert captain["dashboard_metrics_eligible"] is True


@pytest.mark.parametrize(
    ("off_time", "captured_at", "expected"),
    [
        ("8:00", "2026-09-28T18:59:59+00:00", True),
        ("8:30", "2026-09-28T19:29:59+00:00", True),
        ("9:00", "2026-09-28T19:59:59+00:00", True),
        ("8:00", "2026-09-28T19:00:00+00:00", False),
        ("8:00", "2026-09-28T19:00:01+00:00", False),
        ("8:00", None, False),
    ],
)
def test_captured_before_off_handles_evening_clock_and_fails_closed(off_time, captured_at, expected):
    # 2026-09-28 is BST, so 8pm local is 19:00 UTC.
    assert scorecard._captured_before_off("2026-09-28", off_time, captured_at) is expected


def test_captain_non_runner_is_void_not_miss(tmp_path, monkeypatch):
    reports = tmp_path / "data" / "reports"
    results = tmp_path / "data" / "results"
    reports.mkdir(parents=True)
    results.mkdir(parents=True)
    packet = {
        "generated_at": "2026-09-28T09:00:00+00:00", "model_version": "CAPTAIN_VELO_VALUE_V1",
        "races": [{"race_id": "R1", "off_time": "14:00", "action": "SHADOW_SELECTION",
                   "selection": {"horse": "Withdrawn", "horse_id": "H2", "decimal_odds": 11.0,
                                 "quoted_expected_edge": 0.1}}],
    }
    (reports / "captain_velo_shadow_2026_09_28.json").write_text(json.dumps(packet), encoding="utf-8")
    (results / "rp_results_2026_09_28.json").write_text(json.dumps({"results": [{
        "race_id": "R1", "off": "14:00",
        "runners": [{"horse": "Withdrawn", "horse_id": "H2", "position": "NR", "sp_dec": 0.0}],
        "non_runners": ["Withdrawn"],
    }]}), encoding="utf-8")
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_args, **_kwargs: ([], "race_id"))
    rows, _audit = scorecard.build_scorecard("2026-09-28")
    captain = next(row for row in rows if row["model_name"] == "CAPTAIN_VELO_VALUE_V1")
    assert captain["learning_class"] == "NON_RUNNER_VOID"
    assert captain["subject_outcome_status"] == "NON_RUNNER"
    assert captain["stake_void"] is True
    assert captain["win"] is None
    assert captain["official_evaluation_eligible"] is False
    assert captain["dashboard_metrics_eligible"] is True
    assert captain["evaluation_ineligible_reason"] == "NON_RUNNER_VOID_ACCOUNTING_ONLY"


def test_learning_event_preserves_typed_price_and_void(monkeypatch):
    row = {
        "id": 1, "run_date": "2026-09-28", "race_id": "R1", "model_name": "CAPTAIN_VELO_VALUE_V1",
        "lane_name": "selective_value_forward_shadow_only", "horse": "Withdrawn", "horse_id": "H2",
        "source_field": "selection.quoted_expected_edge", "rank": 1, "score": 0.1,
        "sp_dec": None, "settled_sp_dec": None, "captured_odds_dec": 11.0,
        "odds_capture_ts": "2026-09-28T09:00:00+00:00", "price_source": "CAPTAIN_FORWARD_PACKET_DECIMAL_ODDS",
        "odds_timestamp_before_off": True, "result_position": None, "win": None, "frame": None,
        "subject_outcome_code": "NR", "subject_outcome_status": "NON_RUNNER", "subject_is_non_runner": True,
        "settlement_status": "VOID", "stake_void": True, "result_source_hash": "abc",
        "result_source_complete": True, "official_evaluation_eligible": True,
        "dashboard_metrics_eligible": True, "evaluation_ineligible_reason": None,
        "policy_decision": "SHADOW_SELECTION", "stake_authorised": False,
        "dashboard_visible": False, "learning_class": "NON_RUNNER_VOID", "tie_status": "N/A",
        "source_path": "packet.json", "notes": "",
    }
    monkeypatch.setattr(learning, "_preflight", lambda _date: [row])
    events, _audit = learning.build_events("2026-09-28")
    event = events[0]
    assert event["event_type"] == "NON_RUNNER_VOID"
    assert event["captured_odds_dec"] == 11.0
    assert event["settled_sp_dec"] is None
    assert event["stake_void"] is True
    assert "never a model miss" in event["lesson"]


def test_terminal_code_survives_scorecard_payload_and_event(monkeypatch):
    outcome = scorecard._runner_lookup(
        {"runners": [{"horse": "Pulled Up", "horse_id": "H3", "position": "PU", "sp_dec": 9.0}]},
        "Pulled Up",
    )
    assert outcome["outcome_code"] == "PU"
    csv_row = {column: "" for column in persistence.REQUIRED_COLUMNS}
    csv_row.update({
        "date": "2026-09-28", "race_id": "R3", "model_name": "TEST_MODEL",
        "source_path": "source.json", "lane_name": "shadow", "horse": "Pulled Up",
        "horse_id": "H3", "subject_outcome_code": outcome["outcome_code"],
        "subject_outcome_status": outcome["outcome_status"], "settlement_status": outcome["settlement_status"],
        "stake_void": str(outcome["stake_void"]), "result_position": outcome["position"],
        "learning_class": "TERMINAL_LOSS", "official_evaluation_eligible": "True",
        "dashboard_metrics_eligible": "True",
    })
    payload = persistence._row_to_payload(csv_row, "2026-09-28", "deadbeef")
    assert payload["subject_outcome_code"] == "PU"
    assert payload["subject_outcome_status"] == "TERMINAL"
    monkeypatch.setattr(learning, "_preflight", lambda _date: [{**payload, "id": 33}])
    event = learning.build_events("2026-09-28")[0][0]
    assert event["subject_outcome_code"] == "PU"
    assert event["event_type"] == "TERMINAL_LOSS"
    assert event["settlement_status"] == "SETTLED"


def test_event_rerun_replaces_mutable_classification_for_same_source_row():
    base = {"run_date": "2026-09-28", "source_scorecard_id": 44, "event_identity_key": "2026-09-28:44"}
    events = [
        {**base, "learning_class": "MODEL_MISS", "event_type": "MODEL_MISS_NO_POLICY_LAYER"},
        {**base, "learning_class": "NON_RUNNER_VOID", "event_type": "NON_RUNNER_VOID"},
    ]
    unique, collapsed = learning._dedupe_events(events)
    assert collapsed == 1
    assert unique == [events[-1]]
    assert learning.EVENT_CONFLICT_COLUMNS == ("event_identity_key",)


def test_event_rerun_uses_same_supabase_conflict_identity(monkeypatch):
    calls = []

    def fake_upsert(table, rows, conflict_cols):
        calls.append((table, rows, conflict_cols))
        return len(rows), None

    monkeypatch.setattr(learning, "_sb_upsert", fake_upsert)
    base = {"run_date": "2026-09-28", "source_scorecard_id": 44, "event_identity_key": "2026-09-28:44"}
    learning._persist_events([{**base, "learning_class": "MODEL_MISS", "event_type": "MODEL_MISS_NO_POLICY_LAYER"}])
    learning._persist_events([{**base, "learning_class": "NON_RUNNER_VOID", "event_type": "NON_RUNNER_VOID"}])
    assert [call[2] for call in calls] == [
        "event_identity_key", "event_identity_key"
    ]
    assert calls[1][1][0]["learning_class"] == "NON_RUNNER_VOID"


def test_unresolved_top_tie_is_explicitly_metric_ineligible(tmp_path, monkeypatch):
    results = tmp_path / "data" / "results"
    results.mkdir(parents=True)
    (results / "rp_results_2026_09_28.json").write_text(json.dumps({"results": [{
        "race_id": "R1", "runners": [
            {"horse": "A", "horse_id": "A", "position": "1", "sp_dec": 2.0},
            {"horse": "B", "horse_id": "B", "position": "2", "sp_dec": 3.0},
        ],
    }]}), encoding="utf-8")
    verdict = {"race_id": "R1", "full_analysis": {"predictions": [
        {"horse": "A", "horse_id": "A", "velo_prime_prob": 0.5, "sqpe_no_rpr_shadow_prob": 0.4},
        {"horse": "B", "horse_id": "B", "velo_prime_prob": 0.3, "sqpe_no_rpr_shadow_prob": 0.4},
    ]}}
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_args, **_kwargs: ([verdict], "race_id"))
    rows, _audit = scorecard.build_scorecard("2026-09-28")
    tied = next(row for row in rows if row["model_name"] == "SQPE_NO_RPR_SHADOW")
    assert tied["learning_class"] == "TIE_UNRESOLVED"
    assert tied["official_evaluation_eligible"] is False
    assert tied["dashboard_metrics_eligible"] is False
    assert tied["evaluation_ineligible_reason"] == "UNRESOLVED_TOP_RANK_TIE"


def test_result_source_complete_rejects_partial_scorecard_universe(tmp_path, monkeypatch):
    reports = tmp_path / "data" / "reports"
    results = tmp_path / "data" / "results"
    reports.mkdir(parents=True)
    results.mkdir(parents=True)
    packet = {
        "generated_at": "2026-09-28T09:00:00+00:00", "model_version": "CAPTAIN_VELO_VALUE_V1",
        "races": [
            {"race_id": "R1", "off_time": "14:00", "action": "SHADOW_SELECTION",
             "selection": {"horse": "A", "horse_id": "A", "decimal_odds": 5.0, "quoted_expected_edge": 0.1}},
            {"race_id": "R2", "off_time": "15:00", "action": "SHADOW_SELECTION",
             "selection": {"horse": "B", "horse_id": "B", "decimal_odds": 6.0, "quoted_expected_edge": 0.1}},
        ],
    }
    (reports / "captain_velo_shadow_2026_09_28.json").write_text(json.dumps(packet), encoding="utf-8")
    (results / "rp_results_2026_09_28.json").write_text(json.dumps({"results": [{
        "race_id": "R1", "runners": [{"horse": "A", "horse_id": "A", "position": "1", "sp_dec": 4.0}],
    }]}), encoding="utf-8")
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_args, **_kwargs: ([], "race_id"))
    rows, audit = scorecard.build_scorecard("2026-09-28")
    assert audit["result_source_complete"] is False
    assert all(row["result_source_complete"] is False for row in rows)
    assert all(row["official_evaluation_eligible"] is False for row in rows)
    assert all(row["dashboard_metrics_eligible"] is False for row in rows)


@pytest.mark.parametrize("generated_at", [
    "2026-09-28T13:00:00+00:00",  # equal to 14:00 BST
    "2026-09-28T13:00:01+00:00",  # post-off
    None,
])
def test_captured_price_unsafe_timestamp_is_evaluation_ineligible(tmp_path, monkeypatch, generated_at):
    reports = tmp_path / "data" / "reports"
    results = tmp_path / "data" / "results"
    reports.mkdir(parents=True)
    results.mkdir(parents=True)
    packet = {
        "generated_at": generated_at, "model_version": "CAPTAIN_VELO_VALUE_V1",
        "races": [{"race_id": "R1", "off_time": "14:00", "action": "SHADOW_SELECTION",
                   "selection": {"horse": "A", "horse_id": "A", "decimal_odds": 5.0,
                                 "quoted_expected_edge": 0.1}}],
    }
    (reports / "captain_velo_shadow_2026_09_28.json").write_text(json.dumps(packet), encoding="utf-8")
    (results / "rp_results_2026_09_28.json").write_text(json.dumps({"results": [{
        "race_id": "R1", "off": "14:00",
        "runners": [{"horse": "A", "horse_id": "A", "position": "1", "sp_dec": 4.0}],
    }]}), encoding="utf-8")
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_args, **_kwargs: ([], "race_id"))
    rows, _audit = scorecard.build_scorecard("2026-09-28")
    captain = next(row for row in rows if row["model_name"] == "CAPTAIN_VELO_VALUE_V1")
    assert captain["odds_timestamp_before_off"] is False
    assert captain["official_evaluation_eligible"] is False
    assert captain["dashboard_metrics_eligible"] is False
    assert captain["evaluation_ineligible_reason"] == "CAPTURE_TIMESTAMP_NOT_STRICTLY_PRE_OFF"


def test_migration_is_additive_and_documents_governed_historical_fallback():
    sql = (ROOT / "supabase" / "migrations" / "20260929114325_canonical_settlement_and_price_truth.sql").read_text(encoding="utf-8")
    assert "DROP CONSTRAINT" not in sql.upper()
    assert "pg_constraint" in sql
    assert "Captured prices/timestamps are\n-- never inferred or backfilled" in sql
    assert "uq_canonical_learning_events_identity_v1" in sql
    assert "DELETE FROM public.canonical_learning_events" not in sql
    scorecard_updates = [
        statement for statement in sql.split(";")
        if "UPDATE public.canonical_model_scorecards" in statement
    ]
    event_updates = [
        statement for statement in sql.split(";")
        if "UPDATE public.canonical_learning_events" in statement
    ]
    assert scorecard_updates
    assert all("truth_contract_version IS NULL" in statement for statement in scorecard_updates)
    assert event_updates
    assert all("event.truth_contract_version IS NULL" in statement for statement in event_updates)
    assert all("event.event_identity_key IS NULL" in statement for statement in event_updates)
    assert "conrelid = 'public.canonical_model_scorecards'::regclass" in sql
    assert "conrelid = 'public.canonical_learning_events'::regclass" in sql


def test_governed_rows_emit_version_marker_that_excludes_legacy_backfill(tmp_path, monkeypatch):
    reports = tmp_path / "data" / "reports"
    results = tmp_path / "data" / "results"
    reports.mkdir(parents=True)
    results.mkdir(parents=True)
    packet = {
        "generated_at": "2026-09-28T09:00:00+00:00", "model_version": "CAPTAIN_VELO_VALUE_V1",
        "races": [{"race_id": "R1", "off_time": "14:00", "action": "SHADOW_SELECTION",
                   "selection": {"horse": "A", "horse_id": "A", "decimal_odds": 5.0,
                                 "quoted_expected_edge": 0.1}}],
    }
    (reports / "captain_velo_shadow_2026_09_28.json").write_text(json.dumps(packet), encoding="utf-8")
    (results / "rp_results_2026_09_28.json").write_text(json.dumps({"results": [{
        "race_id": "R1", "runners": [{"horse": "A", "horse_id": "A", "position": "1", "sp_dec": 4.0}],
    }]}), encoding="utf-8")
    monkeypatch.setattr(scorecard, "ROOT", tmp_path)
    monkeypatch.setattr(scorecard, "load_verdicts", lambda *_args, **_kwargs: ([], "race_id"))
    row = scorecard.build_scorecard("2026-09-28")[0][0]
    assert row["truth_contract_version"] == "CANONICAL_TRUTH_V2"
    csv_row = {column: row.get(column, "") for column in persistence.REQUIRED_COLUMNS}
    payload = persistence._row_to_payload(csv_row, "2026-09-28", "deadbeef")
    assert payload["truth_contract_version"] == "CANONICAL_TRUTH_V2"
    payload["id"] = 77
    monkeypatch.setattr(learning, "_preflight", lambda _date: [payload])
    event = learning.build_events("2026-09-28")[0][0]
    assert event["truth_contract_version"] == "CANONICAL_TRUTH_V2"
