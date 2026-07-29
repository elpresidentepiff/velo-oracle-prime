#!/usr/bin/env python3
"""
RACEDAY-DASHBOARD-UP-NOW-JULY06 — Task 2/3.

Report-only local scoring pass for Old VELO / Main VELO / No-RPR shadow,
built directly from the cached July 06 standard racecard. This is a
standalone script, NOT run_prime_today.py: no preflight gate, no Supabase
client, no Telegram, no pipeline_run tracking, no live Racing API call.
It calls the pure in-memory score_race_velo_prime() function and writes
report-only local artifacts in the exact shape model_suggestions_builder.py
already expects:

  - data/velo_prime_verdicts_2026_07_06.json   (Old VELO WIN/PLACE/LONGSHOT)
  - data/runner_snapshots_2026_07_06_report_only.jsonl (Main VELO + No-RPR shadow, full field)

No writes anywhere except these two local files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.velo_prime_service import score_race_velo_prime
from workers.racing_api_normalizer import normalize_race

STANDARD_CACHE = ROOT / "data" / "racecards_2026_07_06_standard.json"
DATE_STR = "2026-07-06"
DATE_TAG = "2026_07_06"


def _tier_from_prob(prob: float) -> str:
    if prob >= 0.30:
        return "A"
    if prob >= 0.20:
        return "B"
    return "C"


def main() -> None:
    std = json.loads(STANDARD_CACHE.read_text(encoding="utf-8"))
    races = std if isinstance(std, list) else std.get("races", [])

    verdicts = []
    snapshot_rows = []
    failures = []

    for raw_race in races:
        race = normalize_race(raw_race)
        try:
            scored = score_race_velo_prime(race)
        except Exception as exc:  # report-only pass: skip a failing race, don't crash the whole card
            failures.append({"race_id": race.get("race_id"), "error": str(exc)})
            continue
        if not scored:
            continue

        top = scored[0]
        verdicts.append({
            "race_id": race.get("race_id"),
            "course": race.get("course"),
            "off_time": race.get("off_time"),
            "race_name": race.get("race_name"),
            "tier": _tier_from_prob(float(top.get("velo_prime_prob") or 0.0)),
            "top": top,
        })

        for r in scored:
            snapshot_rows.append({
                "race_id": race.get("race_id"),
                "course": race.get("course"),
                "off_time": race.get("off_time"),
                "race_date": DATE_STR,
                "horse": r.get("horse") or r.get("horse_name"),
                "horse_id": r.get("horse_id") or r.get("horse_rp_uid"),
                "velo_prime_prob": r.get("velo_prime_prob"),
                "sqpe_no_rpr_shadow_prob": r.get("sqpe_no_rpr_shadow_prob"),
                "market_deception_score": r.get("market_deception_score"),
                "improvement_score": r.get("improvement_score"),
                "place_prob": r.get("place_prob"),
                "rank": r.get("rank"),
                "assigned_product": "REPORT_ONLY_NOT_LIVE",
                "execution_allowed": False,
                "report_only": True,
                "trust_policy": "REPORT_ONLY_DASHBOARD_ARTIFACT_NOT_LIVE_VELO",
            })

    out_verdicts = ROOT / "data" / f"velo_prime_verdicts_{DATE_TAG}.json"
    out_verdicts.write_text(json.dumps(verdicts, indent=2, ensure_ascii=False), encoding="utf-8")

    out_snapshots = ROOT / "data" / f"runner_snapshots_{DATE_TAG}_report_only.jsonl"
    out_snapshots.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in snapshot_rows) + ("\n" if snapshot_rows else ""),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "PASS" if verdicts else "NO_ROWS",
        "races_scored": len(verdicts),
        "races_failed": len(failures),
        "failures": failures[:10],
        "runners_scored": len(snapshot_rows),
        "verdicts_path": str(out_verdicts.relative_to(ROOT)),
        "snapshots_path": str(out_snapshots.relative_to(ROOT)),
        "report_only": True,
        "no_telegram": True,
        "no_supabase_write": True,
        "no_staking": True,
    }, indent=2))


if __name__ == "__main__":
    main()
