from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.velo import world_scorecard_store as store
from src.velo.world_scorecard_store import (
    build_rows,
    build_run_rows,
    decide_freeze,
    top_tie_size,
    usable_price,
)

OFF = datetime(2026, 11, 5, 18, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)


def _market(best=7.0, captured="2026-11-05T09:30:00Z", stale=False):
    return {"best_win": best, "quotes": [{"win": best, "stale": stale, "capturedAt": captured}]}


def test_usable_price_accepts_a_dated_pre_off_quote() -> None:
    price, at = usable_price(_market(), OFF, NOW)
    assert price == 7.0
    assert at == "2026-11-05T09:30:00+00:00"


@pytest.mark.parametrize(
    "market",
    [
        None,
        {},
        {"best_win": None, "quotes": []},
        {"best_win": 1.0, "quotes": [{"win": 1.0, "capturedAt": "2026-11-05T09:30:00Z"}]},
        # no capture time: cannot be shown to be pre-off
        {"best_win": 7.0, "quotes": [{"win": 7.0}]},
        # every quote stale
        _market(stale=True),
        # captured at/after the off
        _market(captured="2026-11-05T18:00:00Z"),
        # captured after this run started (clock skew or a future-dated row)
        _market(captured="2026-11-05T10:30:00Z"),
    ],
)
def test_usable_price_rejects_what_it_cannot_date(market) -> None:
    assert usable_price(market, OFF, NOW) == (None, None)


def test_top_tie_size() -> None:
    card = [{"velo_prime_prob": 0.1396}] * 5 + [{"velo_prime_prob": 0.1364}]
    assert top_tie_size(card) == 5
    assert top_tie_size([{"velo_prime_prob": 0.2}, {"velo_prime_prob": 0.1}]) == 1
    assert top_tie_size([]) == 0


@pytest.mark.parametrize(
    ("priced", "runners", "feed_live", "minutes", "expected"),
    [
        (8, 14, True, 300, (True, "PRICED")),
        (7, 14, False, 300, (True, "PRICED")),  # exactly half is enough
        (0, 14, True, 300, (False, "AWAITING_PRICES")),  # feed live, wait for it
        (3, 14, True, 300, (False, "AWAITING_PRICES")),
        (0, 14, True, 75, (True, "NO_MARKET")),  # no hourly run left: freeze what we have
        (3, 14, True, 40, (True, "PARTIAL_MARKET")),
        (0, 7, False, 600, (True, "NO_MARKET")),  # country has no price feed: never wait
        (0, 0, True, 600, (False, "AWAITING_PRICES")),
    ],
)
def test_decide_freeze(priced, runners, feed_live, minutes, expected) -> None:
    assert decide_freeze(priced, runners, feed_live, minutes) == expected


def _payload(price_state="MISSING", freeze_state="NO_MARKET", sp_dec=10.0, captured=None):
    return {
        "date": "2026-11-05",
        "generated_at": "2026-11-05T10:00:00+00:00",
        "code_commit": "abc1234",
        "races": [{
            "provider_race_key": "formfav:us:2026-11-05:belmont_park:r1",
            "scheduled_off": "2026-11-05T18:00:00+00:00",
            "country": "us", "course": "Belmont Park", "race_number": 1,
            "freeze_state": freeze_state, "priced_runners": 0, "field_size": 1, "top_tie_size": 1,
            "scorecard": [{
                "rank": 1, "horse": "Miami Beach", "horse_id": "ff_us_1", "velo_prime_prob": 0.17,
                "sp_dec": sp_dec, "captured_price": captured, "price_state": price_state,
                "price_captured_at": "2026-11-05T09:30:00+00:00" if captured else None,
            }],
        }],
    }


def test_the_model_default_is_never_stored_as_a_price() -> None:
    rows = build_rows(_payload(price_state="MISSING", sp_dec=10.0))
    assert rows[0]["captured_price"] is None
    assert rows[0]["feature_payload"]["price_state"] == "MISSING"
    assert rows[0]["feature_payload"]["race_price_state"] == "NO_MARKET"
    assert rows[0]["feature_payload"]["code_commit"] == "abc1234"


def test_a_real_price_keeps_its_provenance() -> None:
    rows = build_rows(_payload(price_state="REAL", freeze_state="PRICED", sp_dec=7.0, captured=7.0))
    assert rows[0]["captured_price"] == 7.0
    assert rows[0]["feature_payload"]["price_state"] == "REAL"
    assert rows[0]["feature_payload"]["price_captured_at"] == "2026-11-05T09:30:00+00:00"


def test_races_awaiting_prices_are_not_frozen() -> None:
    assert build_rows(_payload(freeze_state="AWAITING_PRICES")) == []


def test_run_rows_are_per_country_and_split_errors_by_country() -> None:
    payload = {
        "date": "2026-11-05", "generated_at": "2026-11-05T10:00:00+00:00", "code_commit": "abc1234",
        "fetch_report": {"error_detail": [
            {"kind": "form", "country": "us", "track": "Mountaineer", "race": 1, "message": "miss"},
        ]},
        "by_country": {
            "us": {"seen": 10, "scored": 8, "skipped_post_off": 1, "runners_scored": 70,
                   "deferred": 0, "freeze_states": {"NO_MARKET": 8}},
            "jp": {"seen": 5, "scored": 3, "skipped_post_off": 0, "runners_scored": 30,
                   "deferred": 2, "freeze_states": {"PRICED": 3, "AWAITING_PRICES": 2}},
            "fr": {"seen": 4, "scored": 4, "skipped_post_off": 0, "runners_scored": 40,
                   "deferred": 0, "freeze_states": {"PRICED": 4}},
        },
    }
    rows = {r["country"]: r for r in build_run_rows(payload, {"us": 70, "jp": 30, "fr": 40}, {"us": 0, "jp": 30, "fr": 40})}
    assert rows["us"]["status"] == "PARTIAL" and rows["us"]["details"]["error_count"] == 1
    assert rows["us"]["details"]["rows_ignored_duplicates"] == 70
    assert rows["jp"]["status"] == "PARTIAL" and rows["jp"]["details"]["deferred"] == 2
    assert rows["fr"]["status"] == "PASS" and rows["fr"]["details"]["rows_ignored_duplicates"] == 0
    assert len({r["run_key"] for r in rows.values()}) == 3
    assert all(r["provider_predictions_consumed"] is False for r in rows.values())


def test_run_rows_report_zero_inserted_not_null_when_everything_was_a_duplicate() -> None:
    payload = {
        "date": "2026-11-05", "generated_at": "2026-11-05T10:00:00+00:00",
        "by_country": {"ca": {"seen": 8, "scored": 8, "runners_scored": 64, "freeze_states": {"NO_MARKET": 8}}},
    }
    # 64 rows attempted; PostgREST returned none (all first-wins duplicates), so "ca" is absent from inserted.
    row = build_run_rows(payload, {"ca": 64}, {})[0]
    assert row["details"]["rows_attempted"] == 64
    assert row["details"]["rows_inserted"] == 0
    assert row["details"]["rows_ignored_duplicates"] == 64
    # no persistence happened at all: genuinely unknown
    unknown = build_run_rows(payload)[0]
    assert unknown["details"]["rows_inserted"] is None and unknown["details"]["rows_ignored_duplicates"] is None


def test_persist_counts_inserted_rows_not_rows_sent(monkeypatch) -> None:
    seen: dict = {}

    def fake_post(table, rows, on_conflict, prefer):
        seen.update(table=table, on_conflict=on_conflict, prefer=prefer)
        return rows[:1]  # PostgREST returns only the rows it inserted

    monkeypatch.setattr(store, "_post", fake_post)
    assert store.persist_rows([{"scorecard_key": "a"}, {"scorecard_key": "b"}]) == 1
    assert seen["table"] == "world_model_scorecards"
    assert seen["on_conflict"] == "scorecard_key"
    assert "ignore-duplicates" in seen["prefer"] and "representation" in seen["prefer"]
    assert store.persist_rows([]) == 0


def test_a_race_off_before_generation_is_never_frozen() -> None:
    payload = _payload()
    payload["generated_at"] = (OFF + timedelta(minutes=1)).isoformat()
    assert build_rows(payload) == []
