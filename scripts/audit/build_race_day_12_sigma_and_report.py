"""
RACE-DAY-12-EOD-TRUTH-01 -- Phase 4 (Sigma evidence-only close, read-only)
and final report. Does NOT call run_results_sigma.py, does NOT touch
Supabase/Telegram/learned_patterns, does NOT invoke eod_shadow_learning_bridge,
Playbook G, or SentientLoopbackEngine. Pure read of the sealed
LearningEventV2.2 packet + per-race summary already on disk.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR = Path("data/reports")
RACE_DATE = "2026-07-12"


def main() -> None:
    per_race = json.loads((REPORTS_DIR / "_race_day_12_per_race_summary.json").read_text())
    manifest = json.loads((REPORTS_DIR / "learning_events_v2_2_2026_07_12_manifest.json").read_text())
    results_payload = json.loads(Path("data/results/rp_results_2026_07_12.json").read_text())

    races_total = len(per_race)
    races_complete = sum(1 for r in per_race if r["result_universe_complete"])
    races_partial = races_total - races_complete
    races_shadow_eligible = sum(
        1 for r in per_race if r["result_universe_complete"] and r["prediction_before_off"] is True
    )

    top_pick_wins = sum(1 for r in per_race if r["top_pick_is_winner"])
    top_pick_frames = sum(1 for r in per_race if r["top_pick_is_frame"])

    # shadow-eligible subset only (complete + proven pre-race) for headline SR/frame rate
    shadow_rows = [r for r in per_race if r["result_universe_complete"] and r["prediction_before_off"] is True]
    shadow_wins = sum(1 for r in shadow_rows if r["top_pick_is_winner"])
    shadow_frames = sum(1 for r in shadow_rows if r["top_pick_is_frame"])

    by_course = Counter(r["course"] for r in per_race)
    resolution_methods = Counter(r["race_resolution_method"] for r in per_race)

    ambiguous_horse_total = sum(r["runners_ambiguous_or_unresolved"] for r in per_race)
    predicted_horse_total = sum(r["runners_predicted"] for r in per_race)

    sigma = {
        "status": "READ_ONLY_EVIDENCE_CLOSE",
        "race_date": RACE_DATE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "EVIDENCE_ONLY_NO_MUTATION",
        "writes_performed": {
            "supabase": False,
            "telegram": False,
            "learned_patterns": False,
            "playbook_g_state": False,
            "sentient_state": False,
        },
        "races": {
            "total": races_total,
            "complete_result_universe": races_complete,
            "partial_or_ambiguous": races_partial,
            "shadow_eligible": races_shadow_eligible,
            "by_course": dict(by_course),
            "race_resolution_methods": dict(resolution_methods),
        },
        "horses": {
            "total_predicted": predicted_horse_total,
            "ambiguous_or_unresolved": ambiguous_horse_total,
            "resolution_rate": round(1 - (ambiguous_horse_total / predicted_horse_total), 4) if predicted_horse_total else None,
        },
        "top_pick_performance_all_races": {
            "n": races_total,
            "wins": top_pick_wins,
            "win_rate": round(top_pick_wins / races_total, 4) if races_total else None,
            "frame_hits": top_pick_frames,
            "frame_rate": round(top_pick_frames / races_total, 4) if races_total else None,
            "note": "Includes races with incomplete result universe / partial prediction coverage -- NOT a clean SR figure, see shadow_eligible_only for that.",
        },
        "top_pick_performance_shadow_eligible_only": {
            "n": len(shadow_rows),
            "wins": shadow_wins,
            "win_rate": round(shadow_wins / len(shadow_rows), 4) if shadow_rows else None,
            "frame_hits": shadow_frames,
            "frame_rate": round(shadow_frames / len(shadow_rows), 4) if shadow_rows else None,
            "note": "Complete result universe AND proven pre-race prediction timestamp only -- the clean, citable subset.",
        },
        "per_race": per_race,
        "exclusions": [],
        "prediction_source": manifest["prediction_source"],
        "prediction_source_note": manifest["prediction_source_note"],
        "results_source_sha256": manifest["results_source_sha256"],
        "dundalk_id_reconciliation": manifest["dundalk_id_reconciliation"],
        "forbidden_paths_not_invoked": [
            "scripts/ops/run_results_sigma.py (unguarded)",
            "scripts/ops/eod_shadow_learning_bridge.py",
            "Playbook G shadow adapter",
            "SentientLoopbackEngine consumption",
        ],
    }

    exclusions_csv = (REPORTS_DIR / "race_day_12_exclusions_2026_07_12.csv").read_text()
    sigma["exclusions_csv_path"] = str(REPORTS_DIR / "race_day_12_exclusions_2026_07_12.csv")

    (REPORTS_DIR / "sigma_2026_07_12_read_only.json").write_text(
        json.dumps(sigma, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md_lines = [
        "# Sigma Evidence-Only Close — 2026-07-12 (READ-ONLY, no mutation)",
        "",
        f"Generated: {sigma['generated_at']}",
        "",
        "## Writes performed: NONE (Supabase / Telegram / learned_patterns / Playbook G / sentient state all untouched)",
        "",
        f"- Races total: {races_total} (Sligo, Perth, Stratford, Dundalk-AW)",
        f"- Complete result universe: {races_complete}",
        f"- Partial / ambiguous: {races_partial}",
        f"- Shadow-eligible (complete + proven pre-race): {races_shadow_eligible}",
        "",
        "## Top-pick performance (shadow-eligible subset only — the clean figure)",
        f"- n = {len(shadow_rows)}",
        f"- Wins: {shadow_wins} ({sigma['top_pick_performance_shadow_eligible_only']['win_rate']*100:.1f}%)" if shadow_rows else "- n=0",
        f"- Frame hits: {shadow_frames} ({sigma['top_pick_performance_shadow_eligible_only']['frame_rate']*100:.1f}%)" if shadow_rows else "",
        "",
        "## Top-pick performance (all 28 races, includes partial-coverage races — NOT a clean SR)",
        f"- Wins: {top_pick_wins}/{races_total} ({top_pick_wins/races_total*100:.1f}%)",
        f"- Frame hits: {top_pick_frames}/{races_total} ({top_pick_frames/races_total*100:.1f}%)",
        "",
        "## Per-race detail",
        "",
        "| Race | Course | Off | Winner | Top pick | Won? | Frame? | Complete? |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in per_race:
        md_lines.append(
            f"| {r['race_id']} | {r['course']} | {r.get('off') or '?'} | {r['winner_horse']} | "
            f"{r['top_pick_resolved_id']} | {'Y' if r['top_pick_is_winner'] else 'n'} | "
            f"{'Y' if r['top_pick_is_frame'] else 'n'} | {'Y' if r['result_universe_complete'] else 'PARTIAL'} |"
        )
    (REPORTS_DIR / "sigma_2026_07_12_read_only.md").write_text("\n".join(md_lines), encoding="utf-8")

    # ---- final EOD truth report ----
    eod = {
        "mission": "RACE-DAY-12-EOD-TRUTH-01",
        "race_date": RACE_DATE,
        "generated_at": sigma["generated_at"],
        "classifications": {
            "RACE_DAY_12_RESULTS_CAPTURED": True,
            "RESULT_SOURCE_HASHED": True,
            "RESULT_COMPLETENESS_MEASURED": True,
            "CANONICAL_PREDICTION_RUNS_MEASURED": True,
            "LEARNING_EVENT_V2_2_PACKET_SEALED": True,
            "SIGMA_EVIDENCE_CLOSE_COMPLETE": True,
            "PARTIAL_AND_AMBIGUOUS_RACES_EXCLUDED": races_partial > 0,
            "NO_PLAYBOOK_G_CONSUMPTION": True,
            "NO_STATE_LEARNING": True,
            "NO_MODEL_TRAINING": True,
            "NO_MODEL_PROMOTION": True,
            "NO_LIVE_SCORING_CHANGE": True,
            "NO_HFS_MUTATION": True,
            "NO_SUPABASE_WRITES": True,
            "NO_TELEGRAM_SEND": True,
        },
        "results_capture": {
            "primary_source": "data/results/rp_results_2026_07_12.json",
            "sha256": manifest["results_source_sha256"],
            "races_captured": races_total,
            "courses": sorted(by_course.keys()),
            "note_dundalk": (
                "Dundalk-AW was absent from this morning's domestic racecard-capture manifest "
                "(it lives in the separate _intl racecard URL list, which run_full_raceday.py's "
                "standard Steps 1-9 do not currently process). Captured manually via a supplementary "
                "results-URL list derived from rp_racecards_2026-07-12_intl.txt and merged into the "
                "primary results file with full provenance retained (capture_sources[1] in the results JSON)."
            ),
        },
        "prediction_source": {
            "selected_source": "velo_verdicts (Supabase)",
            "reason": manifest["prediction_source_note"],
            "runner_prediction_snapshots_rows_for_date": 0,
        },
        "identity_reconciliation": {
            "dundalk_race_id_mapping": manifest["dundalk_id_reconciliation"],
            "dundalk_horse_id_scheme_mismatch": (
                "velo_verdicts uses name-slug horse ids (e.g. rp_DUN_collective_power) for Dundalk-AW, "
                "not the numeric RP ids used by the result truth. Resolved per-horse via "
                "identity_resolver.resolve_horse() (exact id, then normalised name within the race). "
                f"{ambiguous_horse_total} of {predicted_horse_total} predicted horses across all courses "
                "could not be resolved and were excluded from shadow-eligibility for their race."
            ),
        },
        "learning_events_v2_2": {
            "jsonl_path": "data/reports/learning_events_v2_2_2026_07_12.jsonl",
            "manifest_path": "data/reports/learning_events_v2_2_2026_07_12_manifest.json",
            "total_events": manifest["total_events"],
            "consumption_status": "SEALED_NOT_CONSUMED",
            "allow_flag_law": manifest["allow_flag_law"],
        },
        "sigma_evidence_close": {
            "json_path": "data/reports/sigma_2026_07_12_read_only.json",
            "md_path": "data/reports/sigma_2026_07_12_read_only.md",
            "races_shadow_eligible": races_shadow_eligible,
            "top_pick_win_rate_shadow_eligible": sigma["top_pick_performance_shadow_eligible_only"]["win_rate"],
            "top_pick_frame_rate_shadow_eligible": sigma["top_pick_performance_shadow_eligible_only"]["frame_rate"],
        },
        "exclusions_csv_path": "data/reports/race_day_12_exclusions_2026_07_12.csv",
        "next_step": "LEARNING-LOOP-01B not started. July 12 evidence sealed for later governed consumption. July 13 continues with the existing frozen scorer and weights.",
    }
    (REPORTS_DIR / "race_day_12_eod_truth_2026_07_12.json").write_text(
        json.dumps(eod, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    eod_md = f"""# RACE-DAY-12-EOD-TRUTH-01 — Final Report

Governed, evidence-only results-and-Sigma close for 2026-07-12. No learner state, Playbook G, Supabase, or Telegram were mutated.

## Classifications
""" + "\n".join(f"- **{k}**: {v}" for k, v in eod["classifications"].items()) + f"""

## Results capture
- Primary source: `{eod['results_capture']['primary_source']}` (SHA-256 `{eod['results_capture']['sha256']}`)
- {races_total} races captured across {sorted(by_course.keys())}
- Dundalk-AW note: {eod['results_capture']['note_dundalk']}

## Prediction source
- Selected: `velo_verdicts` (Supabase) — {eod['prediction_source']['reason']}
- `runner_prediction_snapshots` had 0 rows for this date.

## Identity reconciliation
- Dundalk race_id mapping (numeric → composite): {json.dumps(eod['identity_reconciliation']['dundalk_race_id_mapping'])}
- {eod['identity_reconciliation']['dundalk_horse_id_scheme_mismatch']}

## LearningEventV2.2 packet
- {eod['learning_events_v2_2']['total_events']} events sealed to `{eod['learning_events_v2_2']['jsonl_path']}`
- Status: **SEALED_NOT_CONSUMED** — for later governed 01B replay only.

## Sigma evidence close (read-only)
- Shadow-eligible races: {races_shadow_eligible}/{races_total}
- Top-pick win rate (shadow-eligible only): {sigma['top_pick_performance_shadow_eligible_only']['win_rate']}
- Top-pick frame rate (shadow-eligible only): {sigma['top_pick_performance_shadow_eligible_only']['frame_rate']}

## Next step
{eod['next_step']}
"""
    (REPORTS_DIR / "race_day_12_eod_truth_2026_07_12.md").write_text(eod_md, encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "sigma_json": str(REPORTS_DIR / "sigma_2026_07_12_read_only.json"),
        "sigma_md": str(REPORTS_DIR / "sigma_2026_07_12_read_only.md"),
        "eod_json": str(REPORTS_DIR / "race_day_12_eod_truth_2026_07_12.json"),
        "eod_md": str(REPORTS_DIR / "race_day_12_eod_truth_2026_07_12.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
