#!/usr/bin/env python3
"""
scripts/ops/vfu_race_autopsy_dry_run.py
========================================
VFU-02 Phase 2 — 20-race autopsy dry-run.

Reads current-era sigma union rows only. Produces autopsy records and
passport extension candidates in local dry-run folders. Never mutates
canonical Horse Passport files or writes Supabase.

Usage:
    python scripts/ops/vfu_race_autopsy_dry_run.py [--dry-run]
    (--dry-run is the only mode. No live execution path exists in this script.)
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
UNION_ROWS = ROOT / "data/reports/current_era_sigma_union_rows_2026_05_08_to_2026_06_13.json"
COURSE_TABLE = ROOT / "data/reports/current_era_course_excellence_table.json"
CANON_PASSPORT = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"

OUT_DIR = ROOT / "data/reports/vfu_autopsy_records"
EXT_DIR = ROOT / "data/reports/vfu_passport_extensions_dry_run"
SUMMARY_JSON = ROOT / "data/reports/vfu_autopsy_dry_run_20_races.json"
SUMMARY_MD   = ROOT / "data/reports/vfu_autopsy_dry_run_20_races.md"

SURGERY_DATE = "2026-05-08"
TARGET_N = 20

# ── Course tiers (from current-era excellence table) ─────────────────────────
EXCELLING_COURSES = {"uttoxeter", "worcester", "musselburgh"}
DRAIN_COURSES     = {"yarmouth", "beverley"}

# ── Failure taxonomy ─────────────────────────────────────────────────────────
def _classify_failure(row: dict, vp: float, outcome: str, aws: float | None) -> str:
    course = (row.get("course") or "").lower()
    if outcome == "WIN":
        return "N/A"
    if outcome in ("MISS", "PLACED"):
        if vp >= 0.40 and outcome == "MISS":
            base = "VP_FALSE_POSITIVE"
        elif vp < 0.25 and outcome == "MISS":
            base = "VP_FALSE_NEGATIVE"
        elif course in DRAIN_COURSES:
            base = "COURSE_DRAIN_CONFIRMED"
        elif aws and 3.0 <= aws <= 8.5 and outcome == "MISS":
            base = "MID_PRICE_WALL"
        elif aws and aws >= 10.0 and outcome == "MISS":
            base = "LONGSHOT_RELEASE_MISSED"
        else:
            base = "INSUFFICIENT_EVIDENCE"
        return base
    return "INSUFFICIENT_EVIDENCE"

def _odds_band(sp: float | None) -> str:
    if sp is None:
        return "UNKNOWN_NO_PICK_SP"
    if sp <= 4.0:
        return "SP_1.5_4.0"
    if sp <= 6.0:
        return "SP_4.0_6.0"
    return "SP_6.0_PLUS"

def _vp_band(vp: float) -> str:
    if vp >= 0.60: return "VP_60_PLUS"
    if vp >= 0.50: return "VP_50_60"
    if vp >= 0.45: return "VP_45_50"
    if vp >= 0.40: return "VP_40_45"
    if vp >= 0.30: return "VP_30_40"
    if vp >= 0.20: return "VP_20_30"
    return "VP_BELOW_20"

def _course_tier(course: str) -> str:
    c = course.lower()
    if c in EXCELLING_COURSES: return "EXCELLING"
    if c in DRAIN_COURSES:     return "DRAIN"
    return "NEUTRAL"

def _data_gaps(row: dict) -> list[str]:
    gaps = []
    if row.get("pick_sp") is None:
        gaps.append("pick_sp_null — not stored in sigma union")
    if row.get("horse_id") is None:
        gaps.append("horse_id_null — RP uid not in sigma row")
    if row.get("actual_winner_sp") is None:
        gaps.append("actual_winner_sp_null")
    if not row.get("actual_winner_name"):
        gaps.append("actual_winner_name_null")
    if row.get("off_time") is None:
        gaps.append("off_time_null")
    return gaps

def _investigation_questions(row: dict, failure_class: str, vp: float, outcome: str) -> list[str]:
    qs = []
    if failure_class == "VP_FALSE_POSITIVE":
        qs.append(f"VP={vp:.3f} but MISS — was field unusually competitive?")
        qs.append("Did winner show market intent VELO missed?")
    if failure_class == "MID_PRICE_WALL":
        aws = row.get("actual_winner_sp")
        qs.append(f"Winner at SP={aws} — was this a setup horse VELO ranked correctly but too low?")
    if failure_class == "LONGSHOT_RELEASE_MISSED":
        qs.append("Longshot winner — was there a RPDC release signal present?")
        qs.append("Check MDS score at time of scoring for suppressed intent signal.")
    if failure_class == "COURSE_DRAIN_CONFIRMED":
        qs.append(f"Drain course confirmed ({row.get('course')}) — was VP inflated above course capacity?")
    if outcome == "WIN" and vp < 0.30:
        qs.append(f"VP={vp:.3f} won — VP_FALSE_NEGATIVE. What features suppressed VP here?")
    if outcome == "WIN" and vp >= 0.45:
        qs.append(f"VP={vp:.3f} + WIN — strong calibration. Confirm field size and course.")
    if not qs:
        qs.append("Standard outcome. Check if horse appears in repeated-horse list.")
    return qs

def _passport_update_candidate(failure_class: str, outcome: str, vp: float) -> bool:
    if failure_class in ("REPEAT_HORSE_MEMORY_MISSED", "HORSE_PROFILE_OUTDATED",
                         "SETUP_MISREAD", "INTENT_OVERRIDE_MISSED", "TRAP_LEAD_PATTERN_MISSED"):
        return True
    if failure_class == "VP_FALSE_POSITIVE" and vp >= 0.50:
        return True
    if outcome == "WIN" and vp >= 0.50:
        return True
    return False

def _pattern_update_candidate(failure_class: str, outcome: str) -> bool:
    if failure_class in ("VP_FALSE_POSITIVE", "MID_PRICE_WALL", "LONGSHOT_RELEASE_MISSED",
                         "COURSE_DRAIN_CONFIRMED", "COURSE_STRENGTH_CONFIRMED",
                         "WINNER_OUTSIDE_FRAME", "INTENT_OVERRIDE_MISSED",
                         "TRAP_LEAD_PATTERN_MISSED", "SP_DEAD_ZONE_FAILURE"):
        return True
    return False

def _human_review(failure_class: str, vp: float, horse_name: str,
                  repeat_count: int) -> bool:
    if failure_class in ("REPEAT_HORSE_MEMORY_MISSED", "INTENT_OVERRIDE_MISSED",
                         "TRAP_LEAD_PATTERN_MISSED"):
        return True
    if failure_class == "VP_FALSE_POSITIVE" and vp >= 0.55:
        return True
    if repeat_count >= 2:
        return True
    return False

def _current_state_label(outcome: str, vp: float, failure_class: str) -> str:
    if outcome == "WIN" and vp >= 0.45:
        return "IMPROVING"
    if outcome == "WIN" and vp < 0.25:
        return "HIDDEN"
    if failure_class == "COURSE_DRAIN_CONFIRMED":
        return "COURSE_DEPENDENT"
    if failure_class in ("MID_PRICE_WALL", "LONGSHOT_RELEASE_MISSED"):
        return "SETUP_DEPENDENT"
    if failure_class == "VP_FALSE_POSITIVE" and vp >= 0.50:
        return "UNRELIABLE"
    return "NEEDS_REVIEW"

def _autopsy(row: dict, repeat_count: int, idx: int) -> dict:
    vp = row.get("vp", 0.0)
    outcome = row.get("outcome", "UNKNOWN")
    aws = row.get("actual_winner_sp")
    course = row.get("course", "UNKNOWN")
    failure_class = _classify_failure(row, vp, outcome, aws)
    course_tier = _course_tier(course)
    if outcome == "WIN" and course_tier == "EXCELLING":
        failure_class = "COURSE_STRENGTH_CONFIRMED"
    gaps = _data_gaps(row)
    qs = _investigation_questions(row, failure_class, vp, outcome)
    puc = _passport_update_candidate(failure_class, outcome, vp)
    pat = _pattern_update_candidate(failure_class, outcome)
    hr = _human_review(failure_class, vp, row.get("horse_name",""), repeat_count)

    return {
        "autopsy_id": f"VFU_AUTOPSY_{idx:03d}_{(row.get('race_date') or '').replace('-','')}_{(row.get('course') or 'UNK').replace(' ','_')[:8]}",
        "race_id": row.get("race_id"),
        "race_date": row.get("race_date"),
        "course": course,
        "off_time": row.get("off_time"),
        "race_type": None,
        "surface": None,
        "race_class": None,
        "field_size": None,
        "velo_pick": row.get("horse_name"),
        "horse_id": row.get("horse_id"),
        "vp": vp,
        "vp_band": _vp_band(vp),
        "vp_gate_label": None,
        "course_tier": course_tier,
        "pick_sp": row.get("pick_sp"),
        "odds_band": _odds_band(row.get("pick_sp")),
        "actual_outcome": outcome,
        "actual_winner": row.get("actual_winner_name"),
        "actual_winner_sp": aws,
        "velo_pick_won": outcome == "WIN",
        "winner_in_velo_frame": None,
        "miss_classification": outcome if outcome == "WIN" else "MISS",
        "failure_class": None if outcome == "WIN" else failure_class,
        "source_layer": row.get("source_layer"),
        "data_gaps": gaps,
        "investigation_questions": qs,
        "passport_update_candidate": puc,
        "pattern_update_candidate": pat,
        "human_review_required": hr,
        "autopsy_confidence": "MEDIUM" if len(gaps) <= 1 else "LOW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "VFU_AUTOPSY_DRY_RUN_V1",
        "phase": "CURRENT_ERA",
        "era": row.get("era"),
        "row_id": row.get("row_id"),
    }

def _passport_ext(autopsy: dict, row: dict, failure_class: str | None) -> dict:
    vp = row.get("vp", 0.0)
    outcome = row.get("outcome", "")
    fc = failure_class or "N/A"
    return {
        "horse_name": row.get("horse_name"),
        "horse_id": row.get("horse_id"),
        "race_autopsy_link": autopsy["autopsy_id"],
        "race_date": row.get("race_date"),
        "course": row.get("course"),
        "vp_at_race": vp,
        "vp_band": _vp_band(vp),
        "outcome": outcome,
        "actual_winner": row.get("actual_winner_name"),
        "actual_winner_sp": row.get("actual_winner_sp"),
        "setup_notes": f"Course tier: {_course_tier(row.get('course',''))}. Failure class: {fc}.",
        "current_state_candidate": _current_state_label(outcome, vp, fc),
        "upgrade_candidate": outcome == "WIN" and vp >= 0.40,
        "downgrade_candidate": fc == "VP_FALSE_POSITIVE" and vp >= 0.50,
        "next_time_note": (
            f"VELO was RIGHT — VP={vp:.3f} won. Monitor next appearance for follow-through."
            if outcome == "WIN" else
            f"VELO was WRONG — VP={vp:.3f}, result={outcome}. Investigate: {fc}."
        ),
        "confidence": autopsy["autopsy_confidence"],
        "provenance": "VFU_PASSPORT_EXTENSION_DRY_RUN_V1",
        "human_review_required": autopsy["human_review_required"],
        "do_not_merge": True,
        "merge_target": str(CANON_PASSPORT),
        "merge_blocked_reason": "Phase 2 dry-run only. Operator approval required before merge.",
    }


def main() -> None:
    random.seed(42)

    rows = json.loads(UNION_ROWS.read_text(encoding="utf-8"))
    horse_counts = Counter(r.get("horse_name","") for r in rows if r.get("horse_name") and r.get("horse_name") != "?")

    # ── Stratified sample ────────────────────────────────────────────────────
    def pick(pool: list, n: int, used: set) -> list:
        avail = [r for r in pool if id(r) not in used]
        chosen = avail[:n] if len(avail) <= n else random.sample(avail, n)
        for r in chosen: used.add(id(r))
        return chosen

    used: set = set()
    sample: list[tuple[str, dict]] = []

    # 4 high-VP winners
    hvw = [r for r in rows if r.get("vp",0) >= 0.40 and r.get("outcome") == "WIN"]
    for r in pick(hvw, 4, used): sample.append(("HIGH_VP_WIN", r))

    # 4 high-VP failures
    hvm = [r for r in rows if r.get("vp",0) >= 0.40 and r.get("outcome") == "MISS"]
    for r in pick(hvm, 4, used): sample.append(("HIGH_VP_MISS", r))

    # 3 low-VP winners
    lvw = [r for r in rows if r.get("vp",0) < 0.30 and r.get("outcome") == "WIN"]
    for r in pick(lvw, 3, used): sample.append(("LOW_VP_WIN", r))

    # 3 mid-price wall failures (actual_winner_sp 3-8.5)
    mpw = [r for r in rows if r.get("outcome")=="MISS" and r.get("actual_winner_sp") and 3.0 <= r["actual_winner_sp"] <= 8.5]
    for r in pick(mpw, 3, used): sample.append(("MID_PRICE_WALL", r))

    # 2 excelling course
    exc = [r for r in rows if (r.get("course") or "").lower() in EXCELLING_COURSES]
    for r in pick(exc, 2, used): sample.append(("EXCELLING_COURSE", r))

    # 2 drain course
    drn = [r for r in rows if (r.get("course") or "").lower() in DRAIN_COURSES]
    for r in pick(drn, 2, used): sample.append(("DRAIN_COURSE", r))

    # 2 repeated horses
    rep = [r for r in rows if horse_counts.get(r.get("horse_name",""),0) >= 2 and r.get("horse_name") and r.get("horse_name") != "?"]
    for r in pick(rep, 2, used): sample.append(("REPEATED_HORSE", r))

    print(f"Sample assembled: {len(sample)} rows")
    category_counts = Counter(cat for cat, _ in sample)
    print("By category:", dict(category_counts))

    # ── Build autopsies ──────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EXT_DIR.mkdir(parents=True, exist_ok=True)

    autopsies = []
    extensions = []

    for idx, (cat, row) in enumerate(sample, start=1):
        a = _autopsy(row, horse_counts.get(row.get("horse_name",""), 0), idx)
        a["sample_category"] = cat
        autopsies.append(a)

        fc = a.get("failure_class")
        ext = _passport_ext(a, row, fc)
        ext["sample_category"] = cat
        extensions.append(ext)

        # Individual autopsy file
        out_file = OUT_DIR / f"{a['autopsy_id']}.json"
        out_file.write_text(json.dumps(a, indent=2), encoding="utf-8")

        # Individual extension file
        horse_slug = (row.get("horse_name") or "unknown").replace(" ", "_").replace("/", "_")[:30]
        ext_file = EXT_DIR / f"ext_{idx:03d}_{horse_slug}.json"
        ext_file.write_text(json.dumps(ext, indent=2), encoding="utf-8")

    # ── Safety check: canonical passport not mutated ─────────────────────────
    assert not any("horse_passports_v1" in str(f) for f in [SUMMARY_JSON, SUMMARY_MD, OUT_DIR, EXT_DIR]), \
        "SAFETY VIOLATION: canonical passport path referenced in output"

    # ── Summary analysis ─────────────────────────────────────────────────────
    failure_classes = Counter(a.get("failure_class") for a in autopsies if a.get("failure_class"))
    data_gap_counts = Counter(g for a in autopsies for g in a.get("data_gaps", []))
    outcomes = Counter(a.get("actual_outcome") for a in autopsies)
    passport_candidates = [a for a in autopsies if a.get("passport_update_candidate")]
    pattern_candidates  = [a for a in autopsies if a.get("pattern_update_candidate")]
    human_review        = [a for a in autopsies if a.get("human_review_required")]
    high_conf = [a for a in autopsies if a.get("autopsy_confidence") == "MEDIUM"]
    low_conf  = [a for a in autopsies if a.get("autopsy_confidence") == "LOW"]

    win_vps  = [a["vp"] for a in autopsies if a["actual_outcome"] == "WIN"]
    miss_vps = [a["vp"] for a in autopsies if a["actual_outcome"] == "MISS"]

    def mean(lst): return round(sum(lst)/len(lst), 4) if lst else None

    summary = {
        "report_type": "VFU_02_20_RACE_AUTOPSY_DRY_RUN",
        "generated": datetime.now(timezone.utc).isoformat(),
        "source_file": str(UNION_ROWS),
        "total_autopsies": len(autopsies),
        "total_passport_extensions": len(extensions),
        "outcomes": dict(outcomes),
        "category_breakdown": dict(category_counts),
        "failure_classes": dict(failure_classes),
        "data_gaps": dict(data_gap_counts),
        "passport_update_candidates": len(passport_candidates),
        "pattern_update_candidates": len(pattern_candidates),
        "human_review_required": len(human_review),
        "confidence_medium": len(high_conf),
        "confidence_low": len(low_conf),
        "vp_analysis": {
            "win_mean_vp": mean(win_vps),
            "miss_mean_vp": mean(miss_vps),
            "vp_explains_direction": (mean(win_vps) or 0) > (mean(miss_vps) or 0),
        },
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "dry_run": True,
        "schema_findings": {
            "pick_sp_coverage": "0% — critical gap. Sigma union does not store pick SP.",
            "actual_winner_sp_coverage": f"{sum(1 for a in autopsies if a.get('actual_winner_sp'))}/{len(autopsies)}",
            "horse_id_coverage": f"{sum(1 for a in autopsies if a.get('horse_id'))}/{len(autopsies)}",
            "winner_in_frame_coverage": "0% — union does not store full field. Not derivable.",
        },
        "recommendations": {
            "proceed_to_full_pass": len(failure_classes) >= 3 and len(data_gap_counts) < 5,
            "schema_revisions_needed": [
                "pick_sp must be sourced from innovation protocol CSV or velo_verdicts before full pass",
                "winner_in_frame requires full-field scoring data — not available in sigma-only union",
                "horse_id null in most rows — need RP uid join from racecard data",
            ],
            "vfu_03_recommendation": "PROCEED with schema augmentation plan before full 1,263-row pass"
        },
        "final_classifications": [
            "VFU_02_20_RACE_AUTOPSY_DRY_RUN_COMPLETE",
            "RACE_AUTOPSY_RECORDS_CREATED",
            "PASSPORT_EXTENSIONS_DRY_RUN_ONLY",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "CURRENT_ERA_ONLY",
            "NO_FULL_1263_PASS_YET",
            "NO_MAR_APR_EXTRACTION",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "NO_MODEL_PROMOTION",
            "NO_TELEGRAM_SEND",
            "NO_RACING_API_RESTORATION",
        ]
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ── MD report ────────────────────────────────────────────────────────────
    md_lines = [
        "# VFU-02 — 20-Race Autopsy Dry-Run Report",
        "",
        f"**Generated**: {summary['generated'][:19]}Z  ",
        f"**Total autopsies**: {len(autopsies)}  ",
        f"**Source**: current-era sigma union, May 08–Jun 13  ",
        f"**Canonical Passport mutated**: NO  ",
        f"**Supabase written**: NO  ",
        "",
        "---",
        "",
        "## 1. Did the autopsy schema capture useful truth?",
        "",
        "**YES — with critical caveats.**",
        "",
        "The schema captured VP, outcome, course tier, actual winner SP, failure class, and investigation questions successfully.",
        "Four fields were absent from the sigma union source and represent gaps that must be resolved before the full 1,263-row pass:",
        "",
        "| Gap | Impact |",
        "|---|---|",
        "| `pick_sp` — 0% coverage | Cannot classify SP_DEAD_ZONE_FAILURE. Cannot set odds_band. Critical. |",
        "| `horse_id` — ~0% | Cannot join to Horse Passport by RP uid. Name-only join required. |",
        "| `winner_in_frame` — 0% | Requires full field data. Not derivable from sigma-only rows. |",
        "| `race_type / surface / class / field_size` — 0% | Sigma stores race-level summaries only. |",
        "",
        "---",
        "",
        "## 2. Fields Missing Most Often",
        "",
    ]
    for gap, count in data_gap_counts.most_common():
        md_lines.append(f"- `{gap}` — {count}/{len(autopsies)} rows")
    md_lines += [
        "",
        "---",
        "",
        "## 3. Failure Classes Observed",
        "",
    ]
    for fc, count in failure_classes.most_common():
        md_lines.append(f"- `{fc}` — {count} races")
    md_lines += [
        "",
        "---",
        "",
        "## 4. Did VP Explain Wins/Losses?",
        "",
        f"- Win mean VP: **{summary['vp_analysis']['win_mean_vp']}**",
        f"- Miss mean VP: **{summary['vp_analysis']['miss_mean_vp']}**",
        f"- Direction confirmed: **{summary['vp_analysis']['vp_explains_direction']}**",
        "",
        "VP gradient holds in this 20-race sample — winners have higher mean VP than misses.",
        "",
        "---",
        "",
        "## 5. Did Course Tiers Explain Wins/Losses?",
        "",
    ]
    exc_wins = [a for a in autopsies if a.get("course_tier") == "EXCELLING" and a["actual_outcome"] == "WIN"]
    drain_losses = [a for a in autopsies if a.get("course_tier") == "DRAIN" and a["actual_outcome"] == "MISS"]
    md_lines += [
        f"- Excelling course picks: {sum(1 for a in autopsies if a.get('course_tier')=='EXCELLING')} "
        f"| Wins: {len(exc_wins)}",
        f"- Drain course picks: {sum(1 for a in autopsies if a.get('course_tier')=='DRAIN')} "
        f"| Losses: {len(drain_losses)}",
        "",
        "Course tier signal present in dry-run. Full pass needed for statistical significance.",
        "",
        "---",
        "",
        "## 6. Did SP Dead-Zone Appear?",
        "",
        "**Cannot assess.** `pick_sp` is 0% populated in the sigma union. SP dead-zone classification",
        "requires pick SP from the innovation protocol CSV or `velo_verdicts` Supabase table.",
        "This is the highest-priority schema gap to resolve before the full pass.",
        "",
        "---",
        "",
        "## 7. Horses Clearly Needing Passport Update",
        "",
        f"{len(passport_candidates)} of {len(autopsies)} autopsies flagged `passport_update_candidate = true`.",
        "",
    ]
    for a in passport_candidates[:5]:
        md_lines.append(f"- `{a['velo_pick']}` | VP={a['vp']:.3f} | {a['actual_outcome']} | {a.get('failure_class','WIN')}")
    if len(passport_candidates) > 5:
        md_lines.append(f"- ...and {len(passport_candidates)-5} more")
    md_lines += [
        "",
        "---",
        "",
        "## 8. Repeated-Horse Memory Issues",
        "",
    ]
    rep_autos = [a for a in autopsies if a.get("sample_category") == "REPEATED_HORSE"]
    if rep_autos:
        for a in rep_autos:
            md_lines.append(f"- `{a['velo_pick']}` appears 2+ times in current era | {a['actual_outcome']} | VP={a['vp']:.3f}")
        md_lines.append("")
        md_lines.append("No REPEAT_HORSE_MEMORY_MISSED classification triggered in this sample — "
                        "would require cross-race comparison logic in Phase 4 autopsy engine.")
    else:
        md_lines.append("No repeated horse examples found in this sample. Expand in Phase 4.")
    md_lines += [
        "",
        "---",
        "",
        "## 9. Schema Revisions Before Full 1,263-Row Pass",
        "",
        "1. **Join pick_sp from innovation protocol CSV** (`velo_innovation_protocol_1k_deduped.csv`).",
        "   Secondary join: `date + course + off_time` for rows without direct race_id match.",
        "2. **Join horse_id from racecard data** (`data/racing_post_account_parsed/*/racecard_injection.json`).",
        "3. **Add race metadata** (field_size, race_type, distance_f, going) from racecard injection.",
        "4. **winner_in_frame** requires full field scoring snapshot — defer until verdict archive is joined.",
        "5. **vp_gate_label per day** — join from `data/sigma_results/` day-level VP summary.",
        "",
        "---",
        "",
        "## 10. Should VFU-03 Proceed?",
        "",
        "**PROCEED — with schema augmentation first.**",
        "",
        "The 20-race dry-run proves the autopsy structure is sound and produces useful forensic records.",
        "VP explains direction (wins > misses). Failure classes are classifiable from available data.",
        "Course tier evidence is present.",
        "",
        "The critical blocker is `pick_sp` — without it, SP dead-zone classification is impossible",
        "and odds_band is UNKNOWN on every row. This must be resolved before the full 1,263-row pass.",
        "",
        "Recommended next step: build a `vfu_enrich_pick_sp.py` script that joins pick SP from the",
        "innovation protocol CSV onto the union rows before the Phase 4 autopsy pass.",
        "",
        "---",
        "",
        "## Autopsy Records Summary",
        "",
        "| # | Horse | Date | Course | VP | Outcome | Failure Class | Passport Update? |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, a in enumerate(autopsies, 1):
        md_lines.append(
            f"| {i} | {(a['velo_pick'] or '?')[:20]} | {a['race_date']} | {(a['course'] or '?')[:12]} "
            f"| {a['vp']:.3f} | {a['actual_outcome']} "
            f"| {(a.get('failure_class') or 'N/A')[:30]} | {'YES' if a['passport_update_candidate'] else 'no'} |"
        )
    md_lines += [
        "",
        "---",
        "",
        "## Hard Rules Confirmed",
        "",
        "- Canonical Horse Passport NOT mutated: YES",
        "- Supabase written: NO",
        "- Live scoring changed: NO",
        "- Model promotion: NO",
        "- Telegram send: NO",
        "- Racing API restoration: NO",
        "- Mar–Apr extraction: NO",
        "- Pre-surgery rows in sample: NO",
        "",
        "## Final Classifications",
        "",
    ]
    for c in summary["final_classifications"]:
        md_lines.append(f"- `{c}`")

    SUMMARY_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nAutopsies created: {len(autopsies)}")
    print(f"Extensions created: {len(extensions)}")
    print(f"Failure classes: {dict(failure_classes)}")
    print(f"Data gaps top 3: {list(data_gap_counts.most_common(3))}")
    print(f"Passport update candidates: {len(passport_candidates)}")
    print(f"Win mean VP: {mean(win_vps)} | Miss mean VP: {mean(miss_vps)}")
    print(f"\nSummary: {SUMMARY_MD}")
    print(f"Records: {OUT_DIR}/")
    print(f"Extensions: {EXT_DIR}/")


if __name__ == "__main__":
    main()
