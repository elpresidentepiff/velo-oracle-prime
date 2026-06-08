from __future__ import annotations

import json
from pathlib import Path

from new_build_velo.archive_pipeline import (
    RPR_POLICY,
    TRUST_POLICY,
    build_plan,
    build_report,
    counts_for_date,
    validate_plan,
)


def test_counts_for_date_reads_archive_spine(tmp_path: Path) -> None:
    day = tmp_path / "2026-05-25"
    day.mkdir()
    (day / "racecard_injection.json").write_text(
        json.dumps(
            {
                "races": [
                    {"runners": [{"horse": "A"}, {"horse": "B"}]},
                    {"runners": [{"horse": "C"}]},
                ]
            }
        ),
        encoding="utf-8",
    )
    (day / "horse_profiles.json").write_text(json.dumps({"horse_profiles": [{"horse": "A"}]}), encoding="utf-8")
    (day / "horse_dossiers.json").write_text(json.dumps({"dossiers": [{}, {}, {}]}), encoding="utf-8")
    (day / "race_dossiers.json").write_text(json.dumps({"dossiers": [{}, {}]}), encoding="utf-8")

    counts = counts_for_date("2026-05-25", parsed_root=tmp_path)

    assert counts.races == 2
    assert counts.runners == 3
    assert counts.horse_profiles == 1
    assert counts.horse_dossiers == 3
    assert counts.race_dossiers == 2
    assert counts.has_racecard is True


def test_plan_contains_no_live_or_shadow_commands() -> None:
    steps = build_plan("2026-05-25", "2026-05-26", execute_local=True, supabase_dry_run=True)
    validate_plan(steps)

    joined = "\n".join(" ".join(step.command).lower() for step in steps)
    assert "run_prime_today" not in joined
    assert "sentient_state" not in joined
    assert "telegram" not in joined
    assert "daily-eod" not in joined
    assert "build_rp_horse_dossiers.py" in joined
    assert "upload_rp_archive_to_supabase.py" in joined


def test_report_locks_archive_only_policy() -> None:
    steps = build_plan("2026-05-25", "2026-05-25")
    report = build_report("2026-05-25", "2026-05-25", counts=[], steps=steps, step_results=[], mode="PLAN_ONLY")

    assert report["trust_policy"] == TRUST_POLICY
    assert report["rpr_policy"] == RPR_POLICY
    assert report["velo_scoring_allowed"] is False
    assert report["live_velo_touched"] is False
    assert report["shadow_velo_touched"] is False

