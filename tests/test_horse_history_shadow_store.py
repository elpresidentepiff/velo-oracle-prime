"""Shadow store: rows are written once per runner, deduplicated, with a run-status row.
The endpoint reads them back and separates runners from the status row. Supabase is mocked."""
import asyncio
import os

import app.services.horse_history_live as live


def _runner(h, rid="r1", rank=1, prob=0.2, known=True):
    return {"horse": h, "race_id": rid, "prob": prob, "rank_in_race": rank,
            "runs_prior": 3, "history_known": known}


def test_write_dedupes_and_adds_status_row(monkeypatch):
    sent = {}

    class Resp:
        def raise_for_status(self):
            return None

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["rows"] = json
        return Resp()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    import requests
    monkeypatch.setattr(requests, "post", fake_post)
    out = live.write_shadow_rows("2026-11-20", "OK", [_runner("alpha"), _runner("alpha"), _runner("beta", rank=2)])
    assert out == "WRITTEN"
    assert "on_conflict=run_date,race_id,horse" in sent["url"]
    horses = [(r["race_id"], r["horse"]) for r in sent["rows"]]
    assert len(horses) == len(set(horses))                  # no duplicate keys in one upsert
    assert ("__run__", "__run__") in horses                 # status row present
    assert all(r["production_influence"] is False for r in sent["rows"])


def test_write_without_credentials_is_soft(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    assert live.write_shadow_rows("2026-11-20", "FAILED", [], "x") == "NO_CREDENTIALS"


def test_endpoint_shapes_rows(monkeypatch):
    import app.main as main
    rows = [
        {"run_date": "2026-11-20", "race_id": "r1", "horse": "alpha", "prob": 0.31, "rank_in_race": 1,
         "runs_prior": 3, "history_known": True, "status": "OK"},
        {"run_date": "2026-11-20", "race_id": "r1", "horse": "beta", "prob": 0.12, "rank_in_race": 2,
         "runs_prior": 0, "history_known": False, "status": "OK"},
        {"run_date": "2026-11-20", "race_id": "__run__", "horse": "__run__", "prob": None,
         "status": "OK", "rank_in_race": None, "runs_prior": None, "history_known": None},
    ]
    monkeypatch.setattr(main, "_sb_rest_rows", lambda path, timeout=8: rows)
    data = asyncio.run(main.horse_history_shadow_route(date="2026-11-20"))
    assert data["available"] is True
    assert data["run_status"] == "OK"
    assert data["summary"] == {"runners": 2, "with_history": 1, "races": 1}
    assert [x["horse"] for x in data["races"][0]["runners"]] == ["alpha", "beta"]
    assert data["races"][0]["runners"][1]["history_known"] is False
