"""#189 end-to-end guards: one verified race identity from provider card to dashboard and EOD.

Uses the Remington Park R4 fixtures from tests/test_race_identity.py.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.world_dashboard import build_identities, certify_formfav_picks, world_picks
from scripts.ops import formfav_global_eod as eod
from scripts.ops import formfav_live_worker as worker
from src.velo.formfav_card_adapter import fetch_formfav_racecards
from src.velo.race_identity import BLOCKED_LABEL, verify_race_identity
from src.velo.world_scorecard_store import build_rows
from src.velo.world_sigma import merge_audit, settle_pick
from tests.test_race_identity import (
    FIELD_12,
    FIELD_13,
    FIXED_12,
    FIXED_12_RUNNERS,
    LEGACY_13,
    LEGACY_13_RUNNERS,
    PRE_OFF,
)

CHICAGO = "America/Chicago"
MEETING_RACE = {"raceNumber": 4, "startTime": "2026-11-13T01:54:00Z", "timezone": CHICAGO,
                "raceClass": "MAIDEN SPECIAL WEIGHT", "numberOfRunners": 10}
MEETING = {"country": "us", "track": "Remington Park", "slug": "remington-park", "races": [MEETING_RACE]}


def _card(off, names, date, scratched=()):
    return {
        "track": "Remington Park", "raceNumber": 4, "startTime": off, "timezone": CHICAGO, "date": date,
        "runners": [{"number": i, "name": n, "scratched": n in scratched} for i, n in enumerate(names, start=1)],
    }


CARD_12 = _card("2026-11-13T01:54:00Z", FIELD_12, "2026-11-12", scratched=("Reckless Ride",))
CARD_13 = _card("2026-11-14T01:54:00Z", FIELD_13, "2026-11-13")


class ProviderByLocalDate:
    """Answers every per-race call by the race's LOCAL racing date, as FormFav does."""

    def __init__(self):
        self.calls: list[dict] = []

    def race_form(self, **kw):
        self.calls.append({"call": "form", **kw})
        return {"2026-11-12": CARD_12, "2026-11-13": CARD_13}[kw["date"]]

    def predictions(self, **kw):
        self.calls.append({"call": "predictions", **kw})
        return {"predictions": []}

    def prices(self, **kw):
        self.calls.append({"call": "prices", **kw})
        return {"runners": []}

    def results(self, **kw):
        self.calls.append({"call": "results", **kw})
        return {}

    def meetings(self, date, timezone="UTC"):
        return {"meetings": [MEETING]}


def _capture_worker(monkeypatch):
    written: dict[str, list] = {}
    monkeypatch.setattr(worker, "_upsert", lambda table, rows, conflict: written.setdefault(table, []).extend(rows))
    monkeypatch.setattr(worker, "_insert", lambda table, rows: written.setdefault(table, []).extend(rows))
    monkeypatch.setattr(worker, "persist_capture_rows", lambda rows, request: rows)
    monkeypatch.setattr(worker, "_provider_backoff_remaining", lambda: 0)
    for cache in (worker._last_form, worker._last_prediction, worker._last_price, worker._last_result):
        cache.clear()
    return written


def test_worker_keys_and_fetches_the_overnight_us_race_by_its_local_racing_date(monkeypatch) -> None:
    written = _capture_worker(monkeypatch)
    client = ProviderByLocalDate()
    now = datetime(2026, 11, 13, 0, 30, tzinfo=UTC)
    # the meetings list for UTC date 13 Nov carries the 12 Nov evening card
    worker._process_race(client, "2026-11-13", MEETING, MEETING_RACE, now)
    keys = {r["provider_race_key"] for r in written["formfav_races"]}
    assert keys == {"formfav:us:2026-11-12:remington_park:r4"}
    race = written["formfav_races"][-1]
    assert race["race_date"] == "2026-11-12" and race["start_time"] == "2026-11-13T01:54:00+00:00"
    assert race["form_meta"]["startTime"] == "2026-11-13T01:54:00Z"
    assert all(c["date"] == "2026-11-12" and c["timezone"] == CHICAGO for c in client.calls)
    names = {r["horse_name"]: r["scratched"] for r in written["formfav_runner_form"]}
    assert names["Reckless Ride"] is True and "Stone Cold Lover" not in names


def test_worker_refuses_to_store_a_racecard_that_contradicts_the_race_clock(monkeypatch) -> None:
    written = _capture_worker(monkeypatch)

    class WrongCard(ProviderByLocalDate):
        def race_form(self, **kw):
            return CARD_13  # the next racing day's R4, the pre-fix collision

    worker._process_race(WrongCard(), "2026-11-13", MEETING, MEETING_RACE, datetime(2026, 11, 13, 0, 30, tzinfo=UTC))
    assert "formfav_runner_form" not in written
    assert all("form_meta" not in r for r in written["formfav_races"])


def test_world_adapter_scores_only_the_verified_field_under_the_local_date_key() -> None:
    races, report = fetch_formfav_racecards(
        date_str="2026-11-13", countries={"us"}, include_prices=False, client=ProviderByLocalDate(),
        utc_date="2026-11-13",
    )
    assert report["identity_blocked"] == []
    race = races[0]
    assert race["_formfav"]["provider_race_key"] == "formfav:us:2026-11-12:remington_park:r4"
    assert race["date"] == "2026-11-12" and race["_formfav"]["startTime"] == "2026-11-13T01:54:00Z"
    names = [r["horse"] for r in race["runners"]]
    assert "Vinalia" in names and "It's Time For Zima" in names
    assert "Reckless Ride" not in names and "Stone Cold Lover" not in names
    assert race["_formfav"]["race_identity"]["status"] == "VERIFIED"


def test_world_adapter_blocks_a_mismatched_card_visibly() -> None:
    class WrongCard(ProviderByLocalDate):
        def race_form(self, **kw):
            return CARD_13

    races, report = fetch_formfav_racecards(
        date_str="2026-11-13", countries={"us"}, include_prices=False, client=WrongCard(),
    )
    assert races == []
    assert report["identity_blocked"][0]["provider_race_key"] == "formfav:us:2026-11-12:remington_park:r4"
    assert "START_TIME_CONFLICT" in report["identity_blocked"][0]["reasons"]
    assert any(e.startswith("identity Remington Park R4: RACECARD_MISMATCH") for e in report["errors"])


def test_world_adapter_utc_date_filter_never_loads_a_race_twice() -> None:
    races, _ = fetch_formfav_racecards(
        date_str="2026-11-13", countries={"us"}, include_prices=False, client=ProviderByLocalDate(),
        utc_date="2026-11-12",
    )
    assert races == []


def test_freeze_writes_the_local_racing_date_and_skips_unverified_races() -> None:
    base = {
        "provider_race_key": "formfav:us:2026-11-12:remington_park:r4", "race_date": "2026-11-12",
        "scheduled_off": "2026-11-13T01:54:00Z", "country": "us", "course": "Remington Park",
        "race_number": 4, "freeze_state": "NO_MARKET",
        "scorecard": [{"rank": 1, "horse": "Vinalia", "horse_id": "ff_us_x", "runner_number": 10,
                       "velo_prime_prob": 0.2, "price_state": "MISSING"}],
    }
    payload = {"date": "2026-11-13", "generated_at": "2026-11-13T00:00:00+00:00", "races": [
        {**base, "race_identity": {"status": "VERIFIED", "local_race_date": "2026-11-12",
                                   "start_time_utc": "2026-11-13T01:54:00+00:00"}},
        {**base, "provider_race_key": "formfav:us:2026-11-12:x:r1", "race_identity": {"status": "RACECARD_MISMATCH"}},
    ]}
    rows = build_rows(payload)
    assert len(rows) == 1
    assert rows[0]["race_date"] == "2026-11-12"
    assert rows[0]["feature_payload"]["race_identity"] == "VERIFIED"
    assert rows[0]["feature_payload"]["runner_number"] == 10


def _world_pick_row(key, pick, second=None):
    return {"race_date": key.split(":")[2], "provider_race_key": key, "country": "us", "track": "Remington Park",
            "race_number": 4, "start_time": "2026-11-13T01:54:00+00:00", "pick_name": pick, "second_name": second,
            "pick_score": 0.2, "price_state": "MISSING", "rank1_rows": 1, "tied_top": False,
            "result_basis": "final", "won": True, "framed": True}


def test_dashboard_shows_racecard_mismatch_instead_of_a_horse_on_the_legacy_rows() -> None:
    idents = build_identities([LEGACY_13], LEGACY_13_RUNNERS, now=PRE_OFF)
    ff = [{"country": "us", "track": "Remington Park", "race_number": 4, "pick1_name": "Stone Cold Lover",
           "pick1_number": 3, "off_uk": "01:54"}]
    out = world_picks([_world_pick_row(LEGACY_13["provider_race_key"], "Woman's Intuition", "Bendelene")], ff,
                      now=PRE_OFF, identities=idents)
    race = out["races"][0]
    assert race["pick_name"] is None and race["second_name"] is None and race["formfav_pick"] is None
    assert race["selection_label"] == BLOCKED_LABEL and race["identity_status"] == "RACECARD_MISMATCH"
    assert race["audit_original_picks"]["velo"] == "Woman's Intuition"
    assert race["audit_original_picks"]["formfav"] == "Stone Cold Lover"
    assert "RACECARD_MISMATCH" in race["flags"]
    s = out["summary"]
    assert s["racecard_mismatch"] == 1 and s["verified"] == 0
    assert s["settled_final"] == 0 and s["won_final"] == 0  # a quarantined result is never counted
    certified = certify_formfav_picks(ff, idents)
    assert certified[0]["pick1_name"] is None and certified[0]["selection_label"] == BLOCKED_LABEL
    assert certified[0]["audit_original_picks"]["pick1"] == "Stone Cold Lover"


def test_dashboard_certifies_both_historical_picks_on_the_verified_card() -> None:
    idents = build_identities([FIXED_12], FIXED_12_RUNNERS, now=PRE_OFF)
    ff = [{"country": "us", "track": "Remington Park", "race_number": 4, "pick1_name": "It's Time For Zima",
           "pick1_number": 5}]
    out = world_picks([_world_pick_row(FIXED_12["provider_race_key"], "Vinalia")], ff, now=PRE_OFF, identities=idents)
    race = out["races"][0]
    assert race["selection_status"] == "VERIFIED" and race["pick_name"] == "Vinalia"
    assert race["formfav_pick"] == "It's Time For Zima" and race["formfav_selection_status"] == "VERIFIED"
    assert race["off_label"] == "01:54" and race["local_race_date"] == "2026-11-12"
    assert race["non_runners"] == ["Reckless Ride"] and race["verified_field_size"] == 9
    assert race["racecard_checked_at"] == "2026-11-13T01:30:00+00:00"
    assert certify_formfav_picks(ff, idents)[0]["pick1_name"] == "It's Time For Zima"


def test_dashboard_fails_closed_when_the_racecard_evidence_cannot_be_read() -> None:
    out = world_picks([_world_pick_row(FIXED_12["provider_race_key"], "Vinalia")], [], now=PRE_OFF, identities=None)
    assert out["races"][0]["pick_name"] is None
    assert out["races"][0]["identity_reasons"] == ["IDENTITY_EVIDENCE_UNAVAILABLE"]
    assert certify_formfav_picks([{"pick1_name": "X"}], None)[0]["pick1_name"] is None


def test_dashboard_blocks_a_non_runner_pick_on_a_verified_card() -> None:
    idents = build_identities([FIXED_12], FIXED_12_RUNNERS, now=PRE_OFF)
    out = world_picks([_world_pick_row(FIXED_12["provider_race_key"], "Reckless Ride")], [], now=PRE_OFF,
                      identities=idents)
    assert out["races"][0]["pick_name"] is None and out["races"][0]["selection_status"] == "NON_RUNNER"
    assert out["summary"]["pick_non_runner"] == 1


def test_world_sigma_quarantines_a_mismatched_race_even_over_an_earlier_final() -> None:
    rows = [{"provider_race_key": LEGACY_13["provider_race_key"], "race_date": "2026-11-13", "country": "us",
             "model_name": "existing_velo_prime_stack", "runner_rank": 1, "horse_key": "k",
             "horse_name": "Woman's Intuition", "score": 0.3, "identity_grade": "B", "generated_pre_off": True,
             "feature_payload": {"price_state": "REAL"}, "captured_price": 3.0}]
    result = {"interim": False, "results_payload": {"placings": [{"name": "Woman's Intuition", "position": 1}]}}
    ident = verify_race_identity(LEGACY_13, LEGACY_13_RUNNERS, require_fresh_racecard=False)
    audit = settle_pick(rows, result, identity=ident)
    assert audit["basis"] == "identity_blocked" and audit["learning_eligible"] is False
    assert audit["learning_block_reason"] == "RACECARD_MISMATCH" and audit["top1_win"] is None
    assert audit["details"]["race_identity"]["quarantined"] is True
    earlier_final = {**settle_pick(rows, result), "basis": "final"}
    assert merge_audit(audit, earlier_final)["basis"] == "identity_blocked"


def test_formfav_eod_quarantines_a_mismatched_race_and_settles_a_verified_one() -> None:
    pred = {"model_version": "v", "confidence": "low", "predictions_payload": {"predictions": [
        {"name": "Stone Cold Lover", "number": 3, "modelRank": 1, "winProb": 0.3}]}}
    result = {"interim": False, "results_payload": {"placings": [{"name": "Stone Cold Lover", "number": 3, "position": 1}]}}
    ident = verify_race_identity(LEGACY_13, LEGACY_13_RUNNERS, require_fresh_racecard=False)
    row = eod.reconcile_race(LEGACY_13, pred, result, ident)
    assert row["basis"] == "identity_blocked" and row["top1_hit"] is None
    assert row["details"]["quarantined"] is True
    pred12 = {"model_version": "v", "confidence": "low", "predictions_payload": {"predictions": [
        {"name": "It's Time For Zima", "number": 5, "modelRank": 1, "winProb": 0.3}]}}
    res12 = {"interim": False, "results_payload": {"placings": [{"name": "Vinalia", "number": 10, "position": 1},
                                                                {"name": "It's Time For Zima", "number": 5, "position": 2}]}}
    ok = eod.reconcile_race(FIXED_12, pred12, res12, verify_race_identity(FIXED_12, FIXED_12_RUNNERS, require_fresh_racecard=False))
    assert ok["basis"] == "final" and ok["top1_hit"] is False and ok["top1_finish_position"] == 2
    assert ok["details"]["race_identity"]["status"] == "VERIFIED"


def test_dashboard_renders_the_block_label_and_racecard_column() -> None:
    html = (Path(__file__).resolve().parents[1] / "app" / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert "r.selection_label" in html and "p.selection_label" in html
    assert "<th>RACECARD</th>" in html and "_cardCell" in html
    assert "RACECARD MISMATCH" in html


def test_formfav_worker_image_ships_the_identity_module_and_zone_data() -> None:
    docker = (Path(__file__).resolve().parents[1] / "Dockerfile.formfav").read_text(encoding="utf-8")
    assert "COPY src/velo/race_identity.py src/velo/race_identity.py" in docker
    assert "tzdata" in docker


def test_worker_rereads_the_racecard_close_to_the_off(monkeypatch) -> None:
    monkeypatch.setattr(worker, "FORM_REFRESH_SECONDS", 21600)
    assert worker._form_refresh_seconds(600) == 21600
    # inside the pre-off window the card is re-read well within RACECARD_MAX_AGE (3h)
    assert worker._form_refresh_seconds(worker.PREOFF_FORM_WINDOW_MIN) <= 1800
    assert worker._form_refresh_seconds(10) <= 1800


def test_worker_restart_does_not_leave_every_racecard_due_at_once(monkeypatch) -> None:
    monkeypatch.setattr(worker, "FORM_REFRESH_SECONDS", 21600)
    worker._last_form.clear()
    keys = [f"formfav:gb:2026-11-13:southwell:r{n}" for n in range(1, 8)]
    for k in keys:
        worker._mark_form_fetched(k)
    marks = [worker._last_form[k] for k in keys]
    assert max(marks) - min(marks) > 1800  # next refreshes spread over hours, not one moment
    assert all(worker.time.time() - m <= 21600 / 2 + 1 for m in marks)
    # after the first read a race keeps the plain interval
    worker._mark_form_fetched(keys[0])
    assert worker.time.time() - worker._last_form[keys[0]] < 1
