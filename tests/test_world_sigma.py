from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.ops.run_world_sigma import settle_dates
from src.velo.world_sigma import (
    build_event,
    merge_audit,
    norm_name,
    price_state_of,
    settle_pick,
)

NOW = datetime(2026, 11, 5, 20, 0, tzinfo=UTC)
RACE = "formfav:jp:2026-11-05:funabashi:r10"


def _sc(rank, name, score, *, price=None, state="REAL", grade="B_RACE_NUMBER_NAME", pre_off=True):
    return {
        "provider_race_key": RACE, "race_date": "2026-11-05", "country": "jp",
        "model_name": "existing_velo_prime_stack", "runner_rank": rank,
        "horse_key": f"ff_jp_{rank}", "horse_name": name, "score": score,
        "captured_price": price, "identity_grade": grade,
        "generated_pre_off": pre_off, "provider_predictions_consumed": False,
        "scheduled_off": "2026-11-05T05:00:00+00:00",
        "feature_payload": {"price_state": state},
    }


def _result(placings, *, interim=False):
    return {
        "provider_race_key": RACE, "result_stage": "correct_weight" if not interim else "interim",
        "interim": interim, "results_payload": {"placings": placings},
    }


def _p(name, pos, scratched=False):
    return {"name": name, "position": pos, "scratched": scratched}


FIELD = [_sc(1, "Sun Lycoris", 0.0813, price=4.0), _sc(2, "Presto Mulan", 0.0791, price=6.0),
         _sc(3, "Blue Passion", 0.0701, price=9.0)]


def test_final_win_with_real_price() -> None:
    a = settle_pick(FIELD, _result([_p("Sun Lycoris", 1), _p("Blue Passion", 2), _p("Presto Mulan", 3)]), computed_at=NOW)
    assert a["basis"] == "final"
    assert (a["top1_win"], a["top1_frame"], a["top1_finish_position"]) == (True, True, 1)
    assert a["level_stake_profit"] == 3.0
    assert a["learning_eligible"] is True and a["learning_block_reason"] is None
    assert a["details"]["skill_sample"] is True


def test_final_miss_is_minus_one_and_still_a_frame() -> None:
    a = settle_pick(FIELD, _result([_p("Blue Passion", 1), _p("Presto Mulan", 2), _p("Sun Lycoris", 3)]), computed_at=NOW)
    assert (a["top1_win"], a["top1_frame"]) == (False, True)
    assert a["level_stake_profit"] == -1.0


def test_identity_grade_d_blocks_learning_but_keeps_the_result() -> None:
    rows = [{**r, "identity_grade": "D_NAME_COUNTRY_ONLY"} for r in FIELD]
    a = settle_pick(rows, _result([_p("Sun Lycoris", 1), _p("Blue Passion", 2)]), computed_at=NOW)
    assert a["basis"] == "final" and a["top1_win"] is True and a["level_stake_profit"] == 3.0
    assert a["learning_eligible"] is False
    assert a["learning_block_reason"] == "IDENTITY_GRADE_D_NAME_COUNTRY_ONLY"


def test_provisional_result_is_stored_but_never_eligible() -> None:
    a = settle_pick(FIELD, _result([_p("Sun Lycoris", 1), _p("Blue Passion", 2)], interim=True), computed_at=NOW)
    assert a["basis"] == "provisional" and a["top1_win"] is True
    assert a["learning_eligible"] is False and a["learning_block_reason"] == "RESULT_NOT_FINAL"
    assert a["details"]["skill_sample"] is False


def test_no_result_and_empty_interim_stub() -> None:
    assert settle_pick(FIELD, None, computed_at=NOW)["basis"] == "no_result"
    stub = _result([_p("Sun Lycoris", None), _p("Blue Passion", None)], interim=True)
    a = settle_pick(FIELD, stub, computed_at=NOW)
    assert a["basis"] == "no_result" and a["top1_win"] is None and a["level_stake_profit"] is None


def test_legacy_ten_point_zero_is_price_blind_not_a_price() -> None:
    legacy = [{**_sc(1, "Sun Lycoris", 0.0813, price=10.0, state=None)} for _ in range(1)]
    legacy[0]["feature_payload"] = {}  # rows frozen before price provenance existed
    assert price_state_of(legacy[0]) == "MISSING"
    a = settle_pick(legacy, _result([_p("Sun Lycoris", 1)]), computed_at=NOW)
    assert a["top1_win"] is True
    assert a["level_stake_profit"] is None and a["captured_price"] is None
    assert "PRICE_BLIND" in a["details"]["block_reasons"] and a["learning_eligible"] is False


def test_tied_top_pick_is_not_a_skill_sample() -> None:
    tied = [_sc(1, "Sun Lycoris", 0.1396, price=4.0), _sc(2, "Presto Mulan", 0.1396, price=6.0)]
    a = settle_pick(tied, _result([_p("Sun Lycoris", 1), _p("Presto Mulan", 2)]), computed_at=NOW)
    assert a["top1_win"] is True
    assert "TIED_TOP_PICK" in a["details"]["block_reasons"]
    assert a["details"]["skill_sample"] is False and a["learning_eligible"] is False


def test_dead_heat_splits_the_return() -> None:
    a = settle_pick(FIELD, _result([_p("Sun Lycoris", 1), _p("Presto Mulan", 1), _p("Blue Passion", 3)]), computed_at=NOW)
    assert a["details"]["dead_heat"] is True and a["top1_win"] is True
    assert a["level_stake_profit"] == 1.0  # 4.0 / 2 - 1


def test_scratched_top_pick_is_a_void_stake_not_a_miss() -> None:
    a = settle_pick(FIELD, _result([_p("Blue Passion", 1), _p("Sun Lycoris", None, scratched=True)]), computed_at=NOW)
    assert a["top1_win"] is None and a["top1_frame"] is None and a["level_stake_profit"] == 0.0
    assert a["learning_block_reason"] == "TOP_PICK_SCRATCHED"
    assert build_event(a)["event_class"] == "TOP_PICK_SCRATCHED"


def test_pick_missing_from_result_is_identity_blocked_never_a_miss() -> None:
    a = settle_pick(FIELD, _result([_p("Somebody Else", 1), _p("Another Horse", 2)]), computed_at=NOW)
    assert a["basis"] == "identity_blocked"
    assert a["top1_win"] is None and a["level_stake_profit"] is None
    assert a["learning_block_reason"] == "TOP_PICK_NOT_IN_RESULT"


def test_ambiguous_name_is_identity_blocked() -> None:
    a = settle_pick(FIELD, _result([_p("Sun Lycoris", 1), _p("SUN LYCORIS", 2)]), computed_at=NOW)
    assert a["basis"] == "identity_blocked" and a["learning_block_reason"] == "TOP_PICK_NAME_AMBIGUOUS"


def test_name_matching_ignores_case_punctuation_and_country_tag() -> None:
    assert norm_name("Irie's Pachira (JPN)") == norm_name("IRIES PACHIRA") == "iriespachira"
    rows = [_sc(1, "Presto Mulan (JPN)", 0.1, price=3.0)]
    a = settle_pick(rows, _result([_p("PRESTO MULAN", 1)]), computed_at=NOW)
    assert a["top1_win"] is True


def test_merge_never_downgrades_a_final_result() -> None:
    final = {"basis": "final", "learning_eligible": True, "learning_block_reason": None}
    provisional = {"basis": "provisional", "learning_eligible": False, "learning_block_reason": "RESULT_NOT_FINAL"}
    assert merge_audit(provisional, final) is final


def test_merge_never_relabels_a_blocked_row_as_eligible() -> None:
    existing = {"basis": "final", "learning_eligible": False, "learning_block_reason": "PRICE_BLIND"}
    new = {"basis": "final", "learning_eligible": True, "learning_block_reason": None}
    out = merge_audit(new, existing)
    assert out["learning_eligible"] is False and out["learning_block_reason"] == "PRICE_BLIND"


def test_merge_lets_a_transient_block_clear() -> None:
    existing = {"basis": "provisional", "learning_eligible": False, "learning_block_reason": "RESULT_NOT_FINAL"}
    new = {"basis": "final", "learning_eligible": True, "learning_block_reason": None}
    assert merge_audit(new, existing)["learning_eligible"] is True
    assert merge_audit(new, None) is new


def test_provisional_and_final_get_distinct_retained_events() -> None:
    prov = settle_pick(FIELD, _result([_p("Sun Lycoris", 1)], interim=True), computed_at=NOW)
    final = settle_pick(FIELD, _result([_p("Sun Lycoris", 1)]), computed_at=NOW)
    assert prov["sigma_key"] == final["sigma_key"]  # one audit row per race, upgraded in place
    assert build_event(prov)["event_key"] != build_event(final)["event_key"]
    changed = settle_pick(FIELD, _result([_p("Blue Passion", 1), _p("Sun Lycoris", 2)]), computed_at=NOW)
    assert build_event(changed)["event_key"] != build_event(final)["event_key"]
    assert all(build_event(a)["consumed"] is False and build_event(a)["retained"] for a in (prov, final, changed))


# ---- I/O wrapper with an in-memory Supabase -------------------------------------------------

# The stored race clock, racecard and field the settlement now checks first (#189).
RACE_ROW = {
    "provider_race_key": RACE, "race_date": "2026-11-05", "race_number": 10,
    "start_time": "2026-11-05T05:00:00+00:00", "timezone": "Asia/Tokyo",
    "metadata": {"raceNumber": 10, "startTime": "2026-11-05T05:00:00Z", "timezone": "Asia/Tokyo"},
    "form_meta": {"raceNumber": 10, "startTime": "2026-11-05T05:00:00Z", "timezone": "Asia/Tokyo", "date": "2026-11-05"},
}
RUNNER_ROWS = [
    {"provider_race_key": RACE, "runner_number": n, "horse_name": name, "scratched": False,
     "updated_at": "2026-11-05T04:30:00+00:00"}
    for n, name in enumerate(("Sun Lycoris", "Presto Mulan", "Blue Passion"), start=1)
]


class FakeDb:
    def __init__(self, scorecards, results, existing=(), race_rows=(RACE_ROW,), runner_rows=RUNNER_ROWS):
        self.scorecards, self.results, self.existing = scorecards, results, list(existing)
        self.race_rows, self.runner_rows = list(race_rows), list(runner_rows)
        self.writes: list[tuple[str, int]] = []
        self.rows: dict[str, list] = {}

    def get_json(self, path):
        table = path.split("?")[0]
        if table == "world_model_scorecards":
            return self.scorecards
        if table == "formfav_results":
            return self.results
        if table == "world_sigma_audits":
            return self.existing
        if table == "formfav_races":
            return self.race_rows
        if table == "formfav_runner_form":
            return self.runner_rows
        raise AssertionError(path)

    def post_json(self, table, rows, on_conflict, prefer):
        self.writes.append((table, len(rows)))
        self.rows.setdefault(table, []).extend(rows)


def _db(result_rows, scheduled_off="2026-11-05T05:00:00+00:00"):
    cards = [{**r, "scheduled_off": scheduled_off} for r in FIELD]
    return FakeDb(cards, result_rows)


def test_settle_dates_dry_run_writes_nothing() -> None:
    db = _db([_result([_p("Sun Lycoris", 1)])])
    rep = settle_dates(["2026-11-05"], get_json=db.get_json, post_json=db.post_json, execute=False, now=NOW)
    assert db.writes == [] and rep["executed"] is False
    assert rep["totals"]["audits"] == 1 and rep["totals"]["basis_final"] == 1


def test_settle_dates_execute_writes_audits_before_events_and_a_run_row() -> None:
    db = _db([_result([_p("Sun Lycoris", 1)])])
    settle_dates(["2026-11-05"], get_json=db.get_json, post_json=db.post_json, execute=True, now=NOW)
    assert [t for t, _ in db.writes] == ["world_sigma_audits", "world_learning_events", "world_pipeline_runs"]
    run = db.rows["world_pipeline_runs"][0]
    assert run["status"] == "PASS" and run["model_name"] == "WORLD_SIGMA_V1" and run["country"] == "world"


def test_a_race_not_yet_due_is_skipped_not_recorded_as_no_result() -> None:
    future_off = (NOW + timedelta(hours=2)).isoformat()
    stub = _result([_p("Sun Lycoris", None)], interim=True)  # empty interim stub seen on live US races
    db = _db([stub], scheduled_off=future_off)
    rep = settle_dates(["2026-11-05"], get_json=db.get_json, post_json=db.post_json, execute=True, now=NOW)
    assert rep["totals"].get("audits", 0) == 0 and rep["totals"]["not_yet_due"] == 1
    assert "world_sigma_audits" not in db.rows


def test_old_race_with_no_result_is_recorded_so_the_gap_is_visible() -> None:
    db = _db([], scheduled_off=(NOW - timedelta(hours=4)).isoformat())
    rep = settle_dates(["2026-11-05"], get_json=db.get_json, post_json=db.post_json, execute=True, now=NOW)
    assert rep["totals"]["basis_no_result"] == 1


def test_one_failing_day_does_not_hide_the_others() -> None:
    db = _db([_result([_p("Sun Lycoris", 1)])])
    calls = {"n": 0}

    def flaky(path):
        if path.startswith("world_model_scorecards") and calls["n"] == 0:
            calls["n"] += 1
            raise OSError("boom")
        return db.get_json(path)

    rep = settle_dates(["2026-11-04", "2026-11-05"], get_json=flaky, post_json=db.post_json, execute=True, now=NOW)
    assert len(rep["errors"]) == 1 and rep["totals"]["audits"] == 1
    assert db.rows["world_pipeline_runs"][0]["status"] == "PARTIAL"
