from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "passport_queue", ROOT / "scripts" / "ops" / "build_rp_passport_bank_queue.py"
)
assert SPEC and SPEC.loader
queue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue)


def test_canonical_archive_recovers_imminent_runner_ids_when_local_cards_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    monkeypatch.setattr(queue, "load_supabase_rp_racecards", lambda _day: [{
        "race_id": "frozen-race",
        "runners": [{
            "horse_id": 123456,
            "horse": "Frozen Runner",
            "horse_url": "/profile/horse/123456/frozen-runner/form",
        }],
    }])
    candidates: dict[str, dict] = {}

    seen = queue.add_racing_imminent_candidates(
        candidates, days_ahead=0, today=date(2026, 11, 18)
    )

    assert seen == {"2026-11-18": 1}
    row = candidates["123456"]
    assert row["source"] == "racing_imminent"
    assert row["reason"] == "RACING_WITHIN_48H_CANONICAL_ARCHIVE"
    assert row["profile_url"] == "https://www.racingpost.com/profile/horse/123456/frozen-runner/form"
    assert row["sources"] == [{
        "source": "racing_imminent",
        "date": "2026-11-18",
        "file": "supabase.public.races.raw",
    }]


def test_local_imminent_card_remains_preferred_over_archive(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    local_dir = tmp_path / "data" / "racecard_merged"
    local_dir.mkdir(parents=True)
    (local_dir / "racecard_test_2026-11-18.json").write_text(
        '{"races":[{"horses":[{"horse_id":123456,"horse_name":"Local Runner"}]}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        queue,
        "load_supabase_rp_racecards",
        lambda _day: (_ for _ in ()).throw(AssertionError("archive must not be read")),
    )
    candidates: dict[str, dict] = {}

    seen = queue.add_racing_imminent_candidates(
        candidates, days_ahead=0, today=date(2026, 11, 18)
    )

    assert seen == {"2026-11-18": 1}
    assert candidates["123456"]["reason"] == "RACING_WITHIN_48H"
