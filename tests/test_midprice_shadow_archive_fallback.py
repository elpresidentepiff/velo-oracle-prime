from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "midprice_shadow_today", ROOT / "scripts" / "ops" / "run_midprice_shadow_today.py"
)
assert SPEC and SPEC.loader
midprice = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(midprice)


def test_archive_fallback_is_used_only_when_local_cards_are_unavailable(monkeypatch) -> None:
    archived = [{"race_id": "r-1", "runners": [{"horse": "Frozen Horse"}]}]

    def no_local_cards(**_kwargs):
        raise RuntimeError("missing local capture")

    monkeypatch.setattr(midprice, "load_racecards", no_local_cards)
    monkeypatch.setattr(midprice, "load_supabase_rp_racecards", lambda _date: archived)

    races, source = midprice._load_shadow_racecards("2026-11-18")

    assert races == archived
    assert source == "supabase_rp_archive"


def test_local_cards_remain_preferred_over_archive(monkeypatch) -> None:
    local = [{"race_id": "r-local", "runners": [{"horse": "Local Horse"}]}]
    monkeypatch.setattr(midprice, "load_racecards", lambda **_kwargs: (local, "rp_merged"))
    monkeypatch.setattr(
        midprice,
        "load_supabase_rp_racecards",
        lambda _date: (_ for _ in ()).throw(AssertionError("archive must not be read")),
    )

    races, source = midprice._load_shadow_racecards("2026-11-18")

    assert races == local
    assert source == "rp_merged"


def test_missing_local_and_archive_fails_truthfully(monkeypatch) -> None:
    monkeypatch.setattr(midprice, "load_racecards", lambda **_kwargs: ([], "empty"))
    monkeypatch.setattr(
        midprice,
        "load_supabase_rp_racecards",
        lambda _date: (_ for _ in ()).throw(midprice.SupabaseRacecardError("archive missing")),
    )

    try:
        midprice._load_shadow_racecards("2026-11-18")
    except RuntimeError as exc:
        assert "No frozen racecards available" in str(exc)
        assert "archive missing" in str(exc)
    else:
        raise AssertionError("missing frozen evidence must not score")
