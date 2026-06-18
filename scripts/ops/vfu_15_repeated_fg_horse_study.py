#!/usr/bin/env python3
"""
VFU-15: Repeated False-GREEN Horse Study

For each horse that appears 2+ times in the VFU-14 false-green enriched cases,
build a per-horse profile to distinguish structural VP over-rating from
single-event noise.

Input:  data/reports/vfu_14_false_green_sp_enriched_cases.jsonl (121 cases)
Output: data/reports/vfu_15_repeated_fg_horse_profiles.json
        data/reports/vfu_15_repeated_fg_summary.json

Governance:
  blocked_from_live_use = True
  paper_only = True
  No Supabase writes
  No Telegram
  No VP threshold change
  No model promotion
  No live scoring change
  Mar-Apr quarantine rows included in analysis (read-only inspection)
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = DATA / "reports"

VFU15_VERSION = "VFU_15_REPEATED_FG_HORSE_STUDY_V1"
REPEAT_THRESHOLD = 2  # minimum FG races to qualify as a repeater

FG_INPUT = REPORTS / "vfu_14_false_green_sp_enriched_cases.jsonl"
LEDGER_INPUT = REPORTS / "vfu_21_pick_sp_backfill_ledger.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_fg_cases(path: pathlib.Path | None = None) -> list[dict]:
    p = path or FG_INPUT
    rows = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_ledger(path: pathlib.Path | None = None) -> list[dict]:
    p = path or LEDGER_INPUT
    rows = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _horse_key(row: dict) -> str:
    """Canonical horse key: horse_id if available, else horse_name normalised."""
    hid = row.get("horse_id")
    if hid and str(hid).strip() not in ("", "None", "null"):
        return f"ID:{hid}"
    name = (row.get("horse_name") or "").strip().lower()
    return f"NAME:{name}" if name else "UNKNOWN"


def _severity_score(row: dict) -> float:
    sev = row.get("false_green_severity", "MEDIUM")
    return {"LOW": 1.0, "MEDIUM": 2.0, "HIGH": 3.0, "CRITICAL": 4.0}.get(str(sev).upper(), 2.0)


def build_horse_profiles(
    fg_cases: list[dict],
    ledger: list[dict] | None = None,
    threshold: int = REPEAT_THRESHOLD,
) -> tuple[list[dict], list[dict], dict]:
    """
    Group FG cases by horse, build per-horse profiles.
    Returns (repeaters, singles, stats_dict).
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in fg_cases:
        key = _horse_key(row)
        grouped[key].append(row)

    repeaters = []
    singles = []

    for key, cases in grouped.items():
        cases_sorted = sorted(cases, key=lambda r: r.get("race_date", ""))
        count = len(cases_sorted)

        horse_name = cases_sorted[0].get("horse_name", "UNKNOWN")
        horse_id = next(
            (str(r["horse_id"]) for r in cases_sorted if r.get("horse_id")), None
        )

        vps = [r["vp"] for r in cases_sorted if r.get("vp") is not None]
        sps = [r["pick_sp"] for r in cases_sorted if r.get("pick_sp") is not None]
        outcomes = Counter(r.get("outcome", "UNKNOWN") for r in cases_sorted)
        is_miss_count = sum(1 for r in cases_sorted if r.get("is_miss"))
        is_placed_count = sum(1 for r in cases_sorted if r.get("is_placed_not_won"))
        failure_classes = Counter(r.get("failure_class", "UNKNOWN") for r in cases_sorted)
        price_attrs = Counter(r.get("price_attribution_status", "UNKNOWN") for r in cases_sorted)
        severity_total = sum(_severity_score(r) for r in cases_sorted)

        # Classify repeater type
        if count >= 3:
            repeater_class = "STRUCTURAL_REPEATER"
        elif count == 2:
            fc_list = list(failure_classes.keys())
            if len(fc_list) == 1:
                repeater_class = "CONSISTENT_CAUSE_REPEATER"
            else:
                repeater_class = "MODERATE_REPEATER"
        else:
            repeater_class = "SINGLE_EVENT"

        profile = {
            "horse_key": key,
            "horse_name": horse_name,
            "horse_id": horse_id,
            "fg_count": count,
            "repeater_class": repeater_class,
            "is_repeater": count >= threshold,
            "severity_total": round(severity_total, 1),
            "avg_severity": round(severity_total / count, 2),
            "vp_min": min(vps) if vps else None,
            "vp_max": max(vps) if vps else None,
            "vp_mean": round(sum(vps) / len(vps), 4) if vps else None,
            "sp_min": min(sps) if sps else None,
            "sp_max": max(sps) if sps else None,
            "sp_mean": round(sum(sps) / len(sps), 4) if sps else None,
            "outcome_counts": dict(outcomes),
            "miss_count": is_miss_count,
            "placed_not_won_count": is_placed_count,
            "top_failure_class": failure_classes.most_common(1)[0][0] if failure_classes else None,
            "failure_classes": dict(failure_classes),
            "price_attributions": dict(price_attrs),
            "race_dates": [r.get("race_date") for r in cases_sorted],
            "race_ids": [r.get("race_id") for r in cases_sorted],
            "courses": [r.get("course") for r in cases_sorted],
            "blocked_from_live_use": True,
            "human_review_required": True,
        }

        if count >= threshold:
            repeaters.append(profile)
        else:
            singles.append(profile)

    repeaters.sort(key=lambda p: (-p["fg_count"], -p["severity_total"]))
    singles.sort(key=lambda p: -p["severity_total"])

    total_horses = len(grouped)
    total_cases = len(fg_cases)
    repeater_horses = len(repeaters)
    repeater_cases = sum(p["fg_count"] for p in repeaters)
    class_dist = Counter(p["repeater_class"] for p in repeaters)
    top_fc_overall = Counter(
        r.get("failure_class", "UNKNOWN") for r in fg_cases
    ).most_common(5)

    stats = {
        "total_fg_cases": total_cases,
        "total_unique_horses": total_horses,
        "repeater_threshold": threshold,
        "repeater_horses": repeater_horses,
        "repeater_cases": repeater_cases,
        "single_event_horses": total_horses - repeater_horses,
        "repeater_pct_of_horses": round(repeater_horses / total_horses * 100, 1) if total_horses else None,
        "repeater_pct_of_cases": round(repeater_cases / total_cases * 100, 1) if total_cases else None,
        "repeater_class_distribution": dict(class_dist),
        "top_failure_classes_overall": dict(top_fc_overall),
    }

    return repeaters, singles, stats


def build_ledger_context(
    repeaters: list[dict], ledger: list[dict]
) -> list[dict]:
    """
    For each repeater, pull ALL their ledger rows (not just FG cases)
    to see their full prediction history — total races, overall SR etc.
    """
    ledger_by_name: dict[str, list[dict]] = defaultdict(list)
    ledger_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in ledger:
        name = (row.get("horse_name") or "").strip().lower()
        hid = str(row.get("horse_id") or "")
        if name:
            ledger_by_name[name].append(row)
        if hid and hid not in ("", "None"):
            ledger_by_id[hid].append(row)

    enriched = []
    for profile in repeaters:
        name = (profile.get("horse_name") or "").strip().lower()
        hid = profile.get("horse_id") or ""
        rows = ledger_by_id.get(hid, []) or ledger_by_name.get(name, [])
        total_ledger = len(rows)
        outcomes = Counter(r.get("outcome", "MISS") for r in rows)
        profile = dict(profile)
        profile["ledger_total_races"] = total_ledger
        profile["ledger_outcomes"] = dict(outcomes)
        profile["ledger_win_rate"] = (
            round(outcomes.get("WIN", 0) / total_ledger * 100, 1) if total_ledger else None
        )
        profile["ledger_frame_rate"] = (
            round(
                (outcomes.get("WIN", 0) + outcomes.get("PLACED", 0)) / total_ledger * 100, 1
            ) if total_ledger else None
        )
        profile["fg_pct_of_ledger"] = (
            round(profile["fg_count"] / total_ledger * 100, 1) if total_ledger else None
        )
        enriched.append(profile)
    return enriched


def main() -> None:
    print(f"VFU-15: Repeated FG Horse Study — {_utc_now()}")

    fg_cases = load_fg_cases()
    print(f"Loaded {len(fg_cases)} FG cases")

    ledger = load_ledger()
    print(f"Loaded {len(ledger)} ledger rows")

    repeaters, singles, stats = build_horse_profiles(fg_cases, ledger)
    repeaters = build_ledger_context(repeaters, ledger)

    print(f"\nUnique horses:    {stats['total_unique_horses']}")
    print(f"Repeaters (>=2):  {stats['repeater_horses']}")
    print(f"Single-event:     {stats['single_event_horses']}")
    print(f"Repeater % cases: {stats['repeater_pct_of_cases']}%")
    print()

    print("Repeater horses (by FG count):")
    for p in repeaters:
        name = p["horse_name"]
        n = p["fg_count"]
        rclass = p["repeater_class"]
        sev = p["severity_total"]
        fc = p["top_failure_class"]
        vp_range = f"{p['vp_min']:.3f}-{p['vp_max']:.3f}" if p["vp_min"] else "n/a"
        lr = p.get("ledger_total_races", "?")
        fg_pct = p.get("fg_pct_of_ledger", "?")
        print(
            f"  {name:30}  FG={n}  {rclass:35}  VP={vp_range}"
            f"  sev={sev}  ledger={lr}  fg%={fg_pct}%  cause={fc}"
        )

    print(f"\nTop failure classes: {stats['top_failure_classes_overall']}")

    summary = {
        "vfu": "VFU-15",
        "version": VFU15_VERSION,
        "generated_at": _utc_now(),
        "stats": stats,
        "blocked_from_live_use": True,
        "paper_only": True,
        "no_supabase_writes": True,
        "no_telegram": True,
        "no_model_promotion": True,
        "no_vp_threshold_change": True,
        "no_live_scoring_change": True,
        "classifications": [
            "VFU_15_REPEATED_FG_STUDY_COMPLETE",
            "BLOCKED_FROM_LIVE_USE",
            "NO_SUPABASE_WRITES",
            "NO_TELEGRAM",
            "NO_MODEL_PROMOTION",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        ],
    }

    profiles_out = {
        "vfu": "VFU-15",
        "version": VFU15_VERSION,
        "generated_at": _utc_now(),
        "paper_only": True,
        "blocked_from_live_use": True,
        "stats": stats,
        "repeater_profiles": repeaters,
        "single_event_count": len(singles),
        "classifications": summary["classifications"],
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "vfu_15_repeated_fg_horse_profiles.json").write_text(
        json.dumps(profiles_out, indent=2), encoding="utf-8"
    )
    (REPORTS / "vfu_15_repeated_fg_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(f"\nWritten: vfu_15_repeated_fg_horse_profiles.json")
    print(f"Written: vfu_15_repeated_fg_summary.json")
    print(f"Classification: VFU_15_REPEATED_FG_STUDY_COMPLETE")


if __name__ == "__main__":
    main()
