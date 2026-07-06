#!/usr/bin/env python3
"""
JULY06-SIGMA-LEARNING-NOW

Runs Sigma-style learning for 2026-07-06 from runtime model-suggestion
artifacts, because Supabase's velo_verdicts table has zero rows for that
date (no live production scorer run happened). This is NOT
OFFICIAL_LIVE_VERDICT_SIGMA — it is
SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS: valid learning
evidence built from artifacts that already exist on disk, joined against
parsed RP results. No Telegram, no staking, no training, no promotion, no
Supabase writes. Every row is promotion_eligible=false.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ops.model_suggestions_builder import build_model_suggestions, MODEL_LABELS

RESULTS_PATH = ROOT / "data" / "results" / "rp_results_2026_07_06.json"
RPT_DIR = ROOT / "data" / "reports"
DATE_STR = "2026-07-06"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def load_results_index() -> tuple[dict[str, dict], dict[str, dict[str, dict]], dict[str, dict[str, dict]]]:
    """Returns (race_meta_by_id, runner_by_race_and_id, runner_by_race_and_normname)."""
    d = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    race_meta: dict[str, dict] = {}
    by_id: dict[str, dict[str, dict]] = {}
    by_name: dict[str, dict[str, dict]] = {}
    for race in d.get("results", []):
        rid = str(race.get("race_id") or "")
        if not rid:
            continue
        race_meta[rid] = race
        by_id[rid] = {}
        by_name[rid] = {}
        for run in race.get("runners", []):
            hid = str(run.get("horse_id") or "")
            if hid:
                by_id[rid][hid] = run
            nm = _norm_name(run.get("horse"))
            if nm:
                by_name[rid][nm] = run
    return race_meta, by_id, by_name


def match_result(rid: str, horse_id: str, horse_name: str, by_id, by_name) -> tuple[dict | None, str]:
    race_ids = by_id.get(rid, {})
    if horse_id and horse_id in race_ids:
        return race_ids[horse_id], "ID_MATCH"
    nm = _norm_name(horse_name)
    race_names = by_name.get(rid, {})
    if nm and nm in race_names:
        return race_names[nm], "NAME_FALLBACK_MATCH"
    return None, "NO_RESULT_MATCH"


def build() -> dict[str, Any]:
    suggestions = build_model_suggestions(DATE_STR)
    race_meta, by_id, by_name = load_results_index()

    lane_rows: dict[str, list[dict]] = {label: [] for label in MODEL_LABELS}
    canonical_rows: list[dict] = []
    learning_events: list[dict] = []
    match_audit = {"ID_MATCH": 0, "NAME_FALLBACK_MATCH": 0, "NO_RESULT_MATCH": 0}

    for row in suggestions["rows"]:
        rid = str(row["race_id"])
        result, match_kind = match_result(rid, row.get("horse_id", ""), row.get("horse", ""), by_id, by_name)
        match_audit[match_kind] += 1
        race = race_meta.get(rid, {})

        result_position = result.get("position") if result else None
        sp_dec = result.get("sp_dec") if result else None
        win = bool(result and str(result_position) == "1")
        frame = bool(result and str(result_position) in ("1", "2", "3"))
        is_top_pick = row.get("rank") == 1

        lane_rows[row["model_label"]].append({
            **row,
            "result_position": result_position,
            "sp_dec": sp_dec,
            "win": win,
            "frame": frame,
            "match_kind": match_kind,
            "race_off_time": race.get("off"),
        })

        canonical_rows.append({
            "run_date": DATE_STR,
            "race_id": rid,
            "model_name": row["model_label"],
            "lane_name": row["lane_name"],
            "horse": row["horse"],
            "horse_id": row.get("horse_id") or "",
            "source_path": row["source_path"],
            "source_field": row["source_field"],
            "rank": row.get("rank"),
            "score": row.get("score"),
            "sp_dec": sp_dec,
            "result_position": result_position,
            "win": win,
            "frame": frame,
            "policy_decision": row.get("policy_decision"),
            "stake_authorised": False,
            "promotion_eligible": False,
            "dashboard_visible": True,
            "learning_class": "RUNTIME_RACEDAY_MODEL_SUGGESTION",
            "match_kind": match_kind,
        })

        if not is_top_pick:
            continue

        # ── Learning event classification (top-pick rows only) ──────────────
        event_class = None
        if match_kind == "NO_RESULT_MATCH":
            event_class = "RESULT_PARSE_GAP"
        elif row["model_label"] in ("SQPE_NO_RPR_SHADOW", "CHAMPION_INTENT_SHADOW"):
            event_class = "SHADOW_SIGNAL_HIT" if win else "SHADOW_SIGNAL_MISS"
        elif row.get("policy_decision") and row["policy_decision"] != "WIN_TRUST":
            event_class = "POLICY_BLOCKED"
        elif win and sp_dec and sp_dec >= 6.0:
            event_class = "VALUE_DISCOVERY"
        elif (not win) and sp_dec and sp_dec <= 2.5:
            event_class = "SHORT_PRICE_TRAP"
        elif win:
            event_class = "MODEL_HIT_RUNTIME_ONLY"
        else:
            event_class = "MODEL_MISS_RUNTIME_ONLY"

        learning_events.append({
            "run_date": DATE_STR,
            "race_id": rid,
            "model_name": row["model_label"],
            "horse": row["horse"],
            "horse_id": row.get("horse_id") or "",
            "event_class": event_class,
            "sp_dec": sp_dec,
            "result_position": result_position,
            "win": win,
            "frame": frame,
            "source_path": row["source_path"],
            "match_kind": match_kind,
            "promotion_eligible": False,
            "promotion_block_reason": "JULY06_RUNTIME_ARTIFACT_LEARNING_NOT_PROMOTION_GRADE",
        })

    for label in suggestions["models_missing"]:
        learning_events.append({
            "run_date": DATE_STR,
            "race_id": "",
            "model_name": label,
            "horse": "",
            "horse_id": "",
            "event_class": "MISSING_ARTIFACT",
            "sp_dec": None,
            "result_position": None,
            "win": False,
            "frame": False,
            "source_path": next(
                (m["expected_source_path"] for m in suggestions["missing_artifacts"] if m["model_label"] == label), ""
            ),
            "match_kind": "N/A",
            "promotion_eligible": False,
            "promotion_block_reason": "JULY06_RUNTIME_ARTIFACT_LEARNING_NOT_PROMOTION_GRADE",
        })

    # ── Per-lane summary stats (Task 1) ──────────────────────────────────────
    lane_stats = []
    for label in MODEL_LABELS:
        rows = lane_rows[label]
        if not rows:
            lane_stats.append({
                "model_label": label, "races_covered": 0, "runners_scored": 0,
                "top_pick_races": 0, "winners": 0, "strike_rate": None,
                "frames": 0, "frame_rate": None, "best_winner_sp": None,
                "avg_winner_sp": None, "onept_win_pl": None, "worst_miss_sp": None,
                "missing_artifact": True,
                "source_path": next((m["expected_source_path"] for m in suggestions["missing_artifacts"] if m["model_label"] == label), ""),
            })
            continue
        top_picks = [r for r in rows if r.get("rank") == 1]
        races_covered = len({r["race_id"] for r in rows})
        top_pick_races = len(top_picks)
        winners = [r for r in top_picks if r["win"]]
        frames = [r for r in top_picks if r["frame"]]
        sp_values = [r["sp_dec"] for r in winners if r.get("sp_dec")]
        onept_pl = sum((r["sp_dec"] - 1.0) if r["win"] else -1.0 for r in top_picks if r.get("sp_dec"))
        misses = [r for r in top_picks if not r["win"] and r.get("sp_dec")]
        worst_miss = min(misses, key=lambda r: r["sp_dec"]) if misses else None
        lane_stats.append({
            "model_label": label,
            "races_covered": races_covered,
            "runners_scored": len(rows),
            "top_pick_races": top_pick_races,
            "winners": len(winners),
            "strike_rate": round(len(winners) / top_pick_races, 4) if top_pick_races else None,
            "frames": len(frames),
            "frame_rate": round(len(frames) / top_pick_races, 4) if top_pick_races else None,
            "best_winner_sp": max(sp_values) if sp_values else None,
            "best_winner_horse": max(winners, key=lambda r: r["sp_dec"])["horse"] if winners and sp_values else None,
            "avg_winner_sp": round(sum(sp_values) / len(sp_values), 2) if sp_values else None,
            "onept_win_pl": round(onept_pl, 2) if top_picks else None,
            "worst_miss_sp": worst_miss["sp_dec"] if worst_miss else None,
            "worst_miss_horse": worst_miss["horse"] if worst_miss else None,
            "missing_artifact": False,
            "source_path": rows[0]["source_path"],
        })

    return {
        "generated_at": _utc_now(),
        "date": DATE_STR,
        "match_audit": match_audit,
        "lane_stats": lane_stats,
        "canonical_rows": canonical_rows,
        "learning_events": learning_events,
        "models_available": suggestions["models_available"],
        "models_missing": suggestions["models_missing"],
        "results_races_parsed": len(race_meta),
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    result = build()
    RPT_DIR.mkdir(parents=True, exist_ok=True)

    # Task 1
    _write_csv(RPT_DIR / "july06_model_results_by_lane.csv", result["lane_stats"])
    lane_md = ["# July 06 Model Results By Lane", "", "| Model | Races | Top-Pick Races | Winners | SR | Frames | FR | Best Winner SP | Avg Winner SP | 1pt P/L | Worst Miss | Missing |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in result["lane_stats"]:
        sr = f"{s['strike_rate']*100:.1f}%" if s["strike_rate"] is not None else "—"
        fr = f"{s['frame_rate']*100:.1f}%" if s["frame_rate"] is not None else "—"
        bw = f"{s['best_winner_sp']:.1f} ({s.get('best_winner_horse','')})" if s.get("best_winner_sp") else "—"
        wm = f"{s['worst_miss_sp']:.1f} ({s.get('worst_miss_horse','')})" if s.get("worst_miss_sp") else "—"
        lane_md.append(
            f"| {s['model_label']} | {s['races_covered']} | {s['top_pick_races']} | {s['winners']} | {sr} | "
            f"{s['frames']} | {fr} | {bw} | {s.get('avg_winner_sp') or '—'} | {s.get('onept_win_pl') or '—'} | {wm} | "
            f"{'YES' if s['missing_artifact'] else 'no'} |"
        )
    (RPT_DIR / "july06_model_results_by_lane_summary.md").write_text("\n".join(lane_md), encoding="utf-8")
    (RPT_DIR / "july06_model_results_by_lane_audit.json").write_text(json.dumps({
        "generated_at": result["generated_at"], "date": result["date"],
        "match_audit": result["match_audit"], "results_races_parsed": result["results_races_parsed"],
        "models_available": result["models_available"], "models_missing": result["models_missing"],
    }, indent=2), encoding="utf-8")

    # Task 2 — Sigma runtime learning
    total_top_pick_events = [e for e in result["learning_events"] if e["event_class"] not in ("MISSING_ARTIFACT",)]
    hits = sum(1 for e in total_top_pick_events if e["win"])
    sigma_summary_md = f"""# July 06 Sigma Runtime Learning Summary

Classification: **SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS**
(NOT OFFICIAL_LIVE_VERDICT_SIGMA)

Generated: {result['generated_at']}

## Why runtime artifacts, not velo_verdicts

July 06 did not have pre-race Supabase `velo_verdicts` rows — no live production
scorer run happened for this date. Sigma was run from existing raceday runtime
artifacts (Old VELO report-only scorer, New Build two-lane readiness, Champion
Intent Shadow scorecard, dashboard model-suggestions join) and parsed RP
results instead. This is valid learning evidence. It is not live-staking proof.
Promotion remains gated.

## Result

- Top-pick events evaluated: {len(total_top_pick_events)}
- Hits: {hits}
- Races with parsed results: {result['results_races_parsed']}/36
- Match audit: {json.dumps(result['match_audit'])}
- Models available: {', '.join(result['models_available'])}
- Models missing: {', '.join(result['models_missing']) or 'none'}
"""
    (RPT_DIR / "july06_sigma_runtime_learning_summary.md").write_text(sigma_summary_md, encoding="utf-8")
    (RPT_DIR / "july06_sigma_runtime_learning_audit.json").write_text(json.dumps({
        "generated_at": result["generated_at"],
        "classification": "SIGMA_RUNTIME_LEARNING_FROM_EXISTING_RACEDAY_ARTIFACTS",
        "not_classification": "OFFICIAL_LIVE_VERDICT_SIGMA",
        "status": "PASS",
        "top_pick_events_evaluated": len(total_top_pick_events),
        "hits": hits,
        "match_audit": result["match_audit"],
        "results_races_parsed": result["results_races_parsed"],
        "promotion_gated": True,
        "no_telegram": True,
        "no_staking": True,
        "no_supabase_write": True,
    }, indent=2), encoding="utf-8")
    _write_csv(RPT_DIR / "july06_sigma_runtime_learning_events.csv", total_top_pick_events)

    # Task 3 — canonical scorecard runtime candidate
    _write_csv(RPT_DIR / "canonical_model_scorecard_2026_07_06_runtime.csv", result["canonical_rows"])
    (RPT_DIR / "canonical_model_scorecard_2026_07_06_runtime_summary.md").write_text(
        f"# Canonical Model Scorecard — 2026-07-06 (RUNTIME candidate)\n\n"
        f"Source type: RUNTIME_RACEDAY_MODEL_SUGGESTION\n\n"
        f"Rows: {len(result['canonical_rows'])}\n\n"
        f"All rows: promotion_eligible=false, stake_authorised=false.\n"
        f"This is a candidate for later canonical persistence, not yet written to Supabase.\n",
        encoding="utf-8",
    )
    (RPT_DIR / "canonical_model_scorecard_2026_07_06_runtime_audit.json").write_text(json.dumps({
        "generated_at": result["generated_at"], "date": result["date"],
        "row_count": len(result["canonical_rows"]),
        "source_type": "RUNTIME_RACEDAY_MODEL_SUGGESTION",
        "promotion_eligible": False,
        "supabase_write": False,
    }, indent=2), encoding="utf-8")

    # Task 4 — learning events
    _write_csv(RPT_DIR / "canonical_learning_events_2026_07_06_runtime.csv", result["learning_events"])
    from collections import Counter
    ev_counts = Counter(e["event_class"] for e in result["learning_events"])
    (RPT_DIR / "canonical_learning_events_2026_07_06_runtime_summary.md").write_text(
        "# Canonical Learning Events — 2026-07-06 (RUNTIME candidate)\n\n"
        f"Rows: {len(result['learning_events'])}\n\n"
        "| Event class | Count |\n|---|---|\n" +
        "\n".join(f"| {k} | {v} |" for k, v in sorted(ev_counts.items())) +
        "\n\nAll rows: promotion_eligible=false, "
        "promotion_block_reason=JULY06_RUNTIME_ARTIFACT_LEARNING_NOT_PROMOTION_GRADE\n",
        encoding="utf-8",
    )
    (RPT_DIR / "canonical_learning_events_2026_07_06_runtime_audit.json").write_text(json.dumps({
        "generated_at": result["generated_at"], "date": result["date"],
        "row_count": len(result["learning_events"]),
        "event_class_counts": dict(ev_counts),
        "promotion_eligible": False,
        "supabase_write": False,
    }, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "lane_stats": result["lane_stats"],
        "canonical_rows": len(result["canonical_rows"]),
        "learning_events": len(result["learning_events"]),
        "match_audit": result["match_audit"],
        "results_races_parsed": result["results_races_parsed"],
    }, indent=2))


if __name__ == "__main__":
    main()
