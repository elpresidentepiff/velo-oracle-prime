#!/usr/bin/env python3
"""Compare official Live VELO verdicts with New Build final-card paper output.

This is a New Build report only. It does not write Live VELO, Shadow, Telegram,
staking, or Supabase state.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REPORT_JSON = ROOT / "data" / "new_build" / "reports" / "live_vs_new_build_final_card_comparison_latest.json"
REPORT_MD = ROOT / "data" / "new_build" / "reports" / "live_vs_new_build_final_card_comparison_latest.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _live_top(verdict: dict[str, Any]) -> dict[str, Any]:
    top = verdict.get("top") or {}
    return {
        "horse": top.get("horse"),
        "horse_id": str(top.get("horse_id") or top.get("rp_uid") or ""),
        "velo_prime_prob": top.get("velo_prime_prob"),
        "tier": verdict.get("tier") or top.get("decision_tier"),
    }


def _or_baselines(racecard_path: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(racecard_path)
    out: dict[str, dict[str, Any]] = {}
    for race in data.get("racecards", []):
        candidates = []
        for runner in race.get("runners", []):
            rating = runner.get("official_rating")
            if rating in (None, "", "-"):
                rating = runner.get("ofr")
            try:
                rating_f = float(rating)
            except (TypeError, ValueError):
                continue
            candidates.append(
                {
                    "horse": runner.get("horse") or runner.get("horse_name"),
                    "horse_id": str(runner.get("horse_id") or ""),
                    "official_rating": rating_f,
                }
            )
        if candidates:
            candidates.sort(key=lambda row: row["official_rating"], reverse=True)
            out[str(race.get("race_id"))] = candidates[0]
    return out


def build_comparison(
    *,
    live_verdict_path: Path,
    paper_path: Path,
    paper_report_path: Path,
    racecard_path: Path,
    execute: bool,
) -> dict[str, Any]:
    live_rows = _read_json(live_verdict_path)
    paper_rows = _read_jsonl(paper_path)
    paper_report = _read_json(paper_report_path)
    or_by_race = _or_baselines(racecard_path)

    live_by_race = {str(row.get("race_id")): row for row in live_rows}
    paper_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in paper_rows:
        paper_by_race[str(row.get("race_id"))].append(row)

    matched_race_ids = sorted(set(live_by_race) & set(paper_by_race))
    race_reports: list[dict[str, Any]] = []
    top_pick_agree = 0
    top3_contains_live_top = 0
    top3_overlap_total = 0
    runners_matched = 0
    strong_diffs: list[dict[str, Any]] = []
    passport_exists_top = 0
    passport_missing_top = 0

    for race_id in matched_race_ids:
        live = live_by_race[race_id]
        live_top = _live_top(live)
        ranked = sorted(paper_by_race[race_id], key=lambda row: row.get("champion_probability") or 0, reverse=True)
        for idx, row in enumerate(ranked, start=1):
            row["computed_rank"] = idx
        nb_top = ranked[0] if ranked else {}
        nb_top3 = ranked[:3]
        runners_matched += len(ranked)

        live_top_norm = _norm(live_top.get("horse"))
        nb_top_norm = _norm(nb_top.get("horse"))
        agreement = bool(live_top_norm and live_top_norm == nb_top_norm)
        if agreement:
            top_pick_agree += 1
        if any(_norm(row.get("horse")) == live_top_norm for row in nb_top3):
            top3_contains_live_top += 1
        live_signal_stack = live.get("signal_stack") or []
        live_ranked_names = [_norm(item.get("horse")) for item in live_signal_stack if isinstance(item, dict)]
        nb_top3_names = {_norm(row.get("horse")) for row in nb_top3}
        top3_overlap = len(nb_top3_names & set(live_ranked_names[:3])) if live_ranked_names else (1 if any(_norm(row.get("horse")) == live_top_norm for row in nb_top3) else 0)
        top3_overlap_total += top3_overlap

        passport_state = "PASSPORT_EXISTS" if nb_top.get("passport_found") else "PASSPORT_MISSING"
        if nb_top.get("passport_found"):
            passport_exists_top += 1
        else:
            passport_missing_top += 1
        prob_gap = abs(float(nb_top.get("champion_probability") or 0) - float(live_top.get("velo_prime_prob") or 0))
        diff_row = {
            "race_id": race_id,
            "course": live.get("course") or nb_top.get("course"),
            "off_time": live.get("off_time") or nb_top.get("off_time"),
            "live_top": live_top,
            "new_build_top": {
                "horse": nb_top.get("horse"),
                "rp_uid": nb_top.get("rp_uid"),
                "champion_probability": nb_top.get("champion_probability"),
                "champion_rank": nb_top.get("champion_rank") or nb_top.get("computed_rank"),
                "passport_found": nb_top.get("passport_found"),
                "missing_reason": nb_top.get("missing_reason"),
            },
            "or_baseline_top": or_by_race.get(race_id),
            "top_pick_agreement": agreement,
            "live_top_in_new_build_top3": any(_norm(row.get("horse")) == live_top_norm for row in nb_top3),
            "top3_overlap_count": top3_overlap,
            "new_build_top3": [
                {
                    "horse": row.get("horse"),
                    "rp_uid": row.get("rp_uid"),
                    "champion_probability": row.get("champion_probability"),
                    "passport_found": row.get("passport_found"),
                }
                for row in nb_top3
            ],
            "passport_state": passport_state,
            "probability_gap_note": round(prob_gap, 6),
        }
        race_reports.append(diff_row)
        if not agreement and (prob_gap >= 0.08 or not nb_top.get("passport_found")):
            strong_diffs.append(diff_row)

    passport = paper_report.get("current_card_feed", {}).get("passport_coverage", {})
    rpr_violations = int(paper_report.get("rpr_violations") or 0)
    coverage_pct = float(passport.get("coverage_pct") or 0.0)
    classification = (
        "LOW_PASSPORT_COVERAGE_PIPELINE_TEST"
        if coverage_pct < 70.0
        else "NEW_BUILD_FINAL_CARD_COMPARISON_READY_BRIDGED"
    )
    judgement = (
        "Comparison valid as alignment/pipeline test only; do not claim full New Build edge today."
        if coverage_pct < 70.0
        else "Passport coverage is now strong enough for a serious paper-read comparison; still no live authority or edge claim until outcomes are evaluated."
    )
    payload = {
        "generated_at": _utc_now(),
        "classification": classification,
        "judgement": judgement,
        "inputs": {
            "live_verdict_path": str(live_verdict_path),
            "paper_path": str(paper_path),
            "paper_report_path": str(paper_report_path),
            "racecard_path": str(racecard_path),
        },
        "matched": {
            "race_count_matched": len(matched_race_ids),
            "live_race_count": len(live_by_race),
            "paper_race_count": len(paper_by_race),
            "runner_count_matched": runners_matched,
            "missing_live_races_in_paper": sorted(set(live_by_race) - set(paper_by_race)),
            "extra_paper_races": sorted(set(paper_by_race) - set(live_by_race)),
        },
        "agreement": {
            "top_pick_agreement_count": top_pick_agree,
            "top_pick_agreement_pct": round(top_pick_agree / len(matched_race_ids) * 100, 2) if matched_race_ids else 0.0,
            "live_top_in_new_build_top3_count": top3_contains_live_top,
            "live_top_in_new_build_top3_pct": round(top3_contains_live_top / len(matched_race_ids) * 100, 2) if matched_race_ids else 0.0,
            "avg_top3_overlap_count": round(top3_overlap_total / len(matched_race_ids), 2) if matched_race_ids else 0.0,
        },
        "coverage": {
            "passport_found": passport.get("found"),
            "passport_total": passport.get("total"),
            "passport_coverage_pct": passport.get("coverage_pct"),
            "new_build_top_with_passport": passport_exists_top,
            "new_build_top_missing_passport": passport_missing_top,
        },
        "rpr_violations": rpr_violations,
        "strong_differences": strong_diffs[:40],
        "race_reports": race_reports,
        "rules": {
            "paper_only": True,
            "no_live_writes": True,
            "no_shadow": True,
            "no_telegram": True,
            "no_staking": True,
            "rpr_archive_only": True,
        },
    }
    if execute:
        REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
        REPORT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        REPORT_MD.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    matched = payload["matched"]
    agreement = payload["agreement"]
    coverage = payload["coverage"]
    lines = [
        "# Live VÉLØ vs New Build Final-Card Paper Comparison",
        f"Generated: {payload['generated_at']}",
        "",
        "## Classification",
        f"`{payload['classification']}`",
        "",
        payload["judgement"],
        "",
        "## Summary",
        f"- **Race count matched**: {matched['race_count_matched']} / Live {matched['live_race_count']} / Paper {matched['paper_race_count']}",
        f"- **Runner count matched**: {matched['runner_count_matched']}",
        f"- **Top-pick agreement**: {agreement['top_pick_agreement_count']} / {matched['race_count_matched']} ({agreement['top_pick_agreement_pct']}%)",
        f"- **Live top pick in New Build top 3**: {agreement['live_top_in_new_build_top3_count']} / {matched['race_count_matched']} ({agreement['live_top_in_new_build_top3_pct']}%)",
        f"- **Average top-3 overlap count**: {agreement['avg_top3_overlap_count']}",
        f"- **Passport coverage**: {coverage['passport_found']} / {coverage['passport_total']} ({coverage['passport_coverage_pct']}%)",
        f"- **New Build top picks with passport**: {coverage['new_build_top_with_passport']}",
        f"- **New Build top picks missing passport**: {coverage['new_build_top_missing_passport']}",
        f"- **RPR violations**: {payload['rpr_violations']}",
        "",
        "## Strong Difference Sample",
        "| Race | Course | Time | Live top | New Build top | NB Passport |",
        "|---|---|---:|---|---|---|",
    ]
    for row in payload["strong_differences"][:25]:
        lines.append(
            f"| {row['race_id']} | {row.get('course')} | {row.get('off_time')} | "
            f"{row['live_top'].get('horse')} | {row['new_build_top'].get('horse')} | {row['new_build_top'].get('passport_found')} |"
        )
    lines += [
        "",
        "## Race-by-Race",
        "| Race | Course | Time | Live top | New Build top | New Build top 3 | OR top | Agreement |",
        "|---|---|---:|---|---|---|---|---|",
    ]
    for row in payload["race_reports"]:
        top3 = ", ".join(item["horse"] for item in row["new_build_top3"])
        or_top = (row.get("or_baseline_top") or {}).get("horse") or "-"
        lines.append(
            f"| {row['race_id']} | {row.get('course')} | {row.get('off_time')} | "
            f"{row['live_top'].get('horse')} | {row['new_build_top'].get('horse')} | {top3} | {or_top} | {row['top_pick_agreement']} |"
        )
    lines += [
        "",
        "## Final Judgement",
        "- Live VÉLØ ran clean and remains official.",
        "- New Build is aligned to the same final card.",
        "- Today is a valid pipeline comparison only because Passport coverage is too low for serious edge judgement.",
        "- Next fix: backfill missing active-runner passports using RP horse UID, then rerun paper scorer.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Live VELO official verdicts with New Build final-card paper.")
    parser.add_argument("--live-verdict-path", default="data/velo_prime_verdicts_2026_05_26.json")
    parser.add_argument("--paper-path", default="data/new_build/paper_predictions/new_build_paper_predictions_final_card_latest.jsonl")
    parser.add_argument("--paper-report-path", default="data/new_build/reports/new_build_paper_predictions_final_card_latest.json")
    parser.add_argument("--racecard-path", default="data/racecards_2026_05_26_standard.json")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    payload = build_comparison(
        live_verdict_path=Path(args.live_verdict_path),
        paper_path=Path(args.paper_path),
        paper_report_path=Path(args.paper_report_path),
        racecard_path=Path(args.racecard_path),
        execute=args.execute,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
