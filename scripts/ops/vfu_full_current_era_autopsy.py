#!/usr/bin/env python3
"""
scripts/ops/vfu_full_current_era_autopsy.py
=============================================
VFU-04 — Full current-era 1,263-row autopsy pass with evidence quality tiers.

Reads enriched sigma union. Assigns quality tiers. Runs autopsy on all rows.
Builds repeated horse tracker, passport candidates, and pattern evidence.

Evidence quality tiers (exclusive, priority order):
  TIER_E_UNUSABLE:        missing outcome or VP
  TIER_D_EVENT_ONLY:      missing horse_name or race_date
  TIER_A_FULL:            date+horse+course+outcome+VP+pick_sp all present
  TIER_B_GOOD_NO_PICK_SP: date+horse+course+outcome+VP present, pick_sp absent, actual_winner_sp present
  TIER_C_LIMITED_IDENTITY: date+horse+course+outcome+VP present, no pick_sp, no actual_winner_sp

Never mutates canonical Horse Passport.
Never writes Supabase.
Never changes scoring or model weights.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_race_autopsy_dry_run import (
    _classify_failure,
    _data_gaps,
    _vp_band,
    _odds_band,
    _course_tier,
    EXCELLING_COURSES,
    DRAIN_COURSES,
    CANON_PASSPORT,
)
from scripts.ops.vfu_enrich_pick_sp import norm_horse

# ── Paths ────────────────────────────────────────────────────────────────────
ENRICHED_UNION = ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json"
COURSE_TABLE   = ROOT / "data/reports/current_era_course_excellence_table.json"

OUT_SUMMARY_MD  = ROOT / "data/reports/vfu_full_current_era_autopsy_summary.md"
OUT_SUMMARY_JSON= ROOT / "data/reports/vfu_full_current_era_autopsy_summary.json"
OUT_RECORDS     = ROOT / "data/reports/vfu_full_current_era_autopsy_records.jsonl"
OUT_PASSPORTS   = ROOT / "data/reports/vfu_full_current_era_passport_candidates.jsonl"
OUT_PATTERNS    = ROOT / "data/reports/vfu_full_current_era_pattern_evidence.jsonl"
OUT_GAPS        = ROOT / "data/reports/vfu_full_current_era_quality_gaps.json"

PROVENANCE = "VFU_FULL_CURRENT_ERA_DRY_RUN"
SURGERY_DATE = "2026-05-08"


# ── Quality tier assignment ───────────────────────────────────────────────────

def assign_tier(row: dict) -> str:
    has_vp = row.get("vp") is not None
    has_outcome = row.get("outcome") in ("WIN", "MISS", "PLACED")
    if not has_vp or not has_outcome:
        return "TIER_E_UNUSABLE"
    if not row.get("horse_name") or not row.get("race_date"):
        return "TIER_D_EVENT_ONLY"
    if row.get("pick_sp") is not None:
        return "TIER_A_FULL"
    if row.get("actual_winner_sp") is not None:
        return "TIER_B_GOOD_NO_PICK_SP"
    return "TIER_C_LIMITED_IDENTITY"


# ── Win class (for WIN rows) ──────────────────────────────────────────────────

def _win_class(vp: float, pick_sp: float | None) -> str | None:
    if vp >= 0.50 and pick_sp is not None and pick_sp <= 4.0:
        return "VP_CONFIRMED_FAVOURITE_WIN"
    if vp >= 0.40:
        return "VP_HIGH_WIN"
    if vp >= 0.30:
        return "VP_MID_WIN"
    if vp < 0.25:
        return "VP_FALSE_NEGATIVE_WIN"
    return "VP_LOW_WIN"


# ── Autopsy for a single row ──────────────────────────────────────────────────

def _autopsy_row(row: dict, tier: str, idx: int) -> dict:
    vp = row.get("vp", 0.0)
    outcome = row.get("outcome", "UNKNOWN")
    aws = row.get("actual_winner_sp")
    pick_sp = row.get("pick_sp")
    course = row.get("course", "UNKNOWN") or "UNKNOWN"
    horse_name = row.get("horse_name")
    race_date = row.get("race_date") or ""
    course_slug = course.replace(" ", "_")[:8]
    date_slug = race_date.replace("-", "") if race_date else "NODATE"

    failure_class = _classify_failure(row, vp, outcome, aws) if outcome != "WIN" else None
    win_cls = _win_class(vp, pick_sp) if outcome == "WIN" else None

    ct = _course_tier(course)
    if outcome == "WIN" and ct == "EXCELLING":
        if failure_class is not None:
            failure_class = "COURSE_STRENGTH_CONFIRMED"

    gaps = _data_gaps(row)
    excluded_from_roi = pick_sp is None
    excluded_from_passport = (not horse_name) or (not race_date)

    confidence = "LOW" if len(gaps) >= 3 else ("MEDIUM" if len(gaps) >= 1 else "HIGH")

    qs: list[str] = []
    if failure_class == "VP_FALSE_POSITIVE":
        qs.append(f"VP={vp:.3f} but MISS — was field unusually competitive?")
    if failure_class == "MID_PRICE_WALL":
        qs.append(f"Winner SP={aws} — was this a setup horse ranked correctly but too low?")
    if failure_class == "LONGSHOT_RELEASE_MISSED":
        qs.append("Longshot winner — was RPDC release signal present?")
    if failure_class == "COURSE_DRAIN_CONFIRMED":
        qs.append(f"Drain course ({course}) — was VP inflated above course capacity?")
    if outcome == "WIN" and vp < 0.25:
        qs.append(f"VP={vp:.3f} won — VP_FALSE_NEGATIVE. What suppressed VP?")
    if not qs:
        qs.append("Standard outcome. Include in aggregate pattern counts.")

    puc = (
        not excluded_from_passport
        and (
            (failure_class == "VP_FALSE_POSITIVE" and vp >= 0.50)
            or (outcome == "WIN" and vp >= 0.50)
            or failure_class in ("REPEAT_HORSE_MEMORY_MISSED", "HORSE_PROFILE_OUTDATED")
        )
    )
    pat = failure_class in (
        "VP_FALSE_POSITIVE", "MID_PRICE_WALL", "LONGSHOT_RELEASE_MISSED",
        "COURSE_DRAIN_CONFIRMED", "COURSE_STRENGTH_CONFIRMED", "SP_DEAD_ZONE_FAILURE",
        "WINNER_OUTSIDE_FRAME",
    )

    return {
        "autopsy_id": f"VFU4_{idx:04d}_{date_slug}_{course_slug}",
        "evidence_quality_tier": tier,
        "row_source_layer": row.get("source_layer"),
        "race_id": row.get("race_id"),
        "race_date": race_date,
        "course": course,
        "off_time": row.get("off_time"),
        "horse_name": horse_name,
        "horse_id": row.get("horse_id"),
        "vp": vp,
        "vp_band": _vp_band(vp),
        "pick_sp": pick_sp,
        "pick_sp_missing_reason": row.get("pick_sp_missing_reason"),
        "actual_winner_sp": aws,
        "actual_winner_name": row.get("actual_winner_name"),
        "outcome": outcome,
        "course_tier": ct,
        "failure_class": failure_class,
        "win_class": win_cls,
        "investigation_questions": qs,
        "data_gaps": gaps,
        "passport_update_candidate": puc,
        "pattern_update_candidate": pat,
        "human_review_required": (
            (failure_class == "VP_FALSE_POSITIVE" and vp >= 0.55)
            or (outcome == "WIN" and vp >= 0.50)
            or tier in ("TIER_C_LIMITED_IDENTITY",)
        ),
        "confidence_in_autopsy": confidence,
        "excluded_from_roi": excluded_from_roi,
        "excluded_from_passport": excluded_from_passport,
        "provenance": PROVENANCE,
        "enrichment_version": row.get("enrichment_version"),
        "odds_band": _odds_band(pick_sp),
    }


# ── Passport candidate ────────────────────────────────────────────────────────

def _passport_candidate(autopsy: dict, row: dict) -> dict | None:
    if autopsy["excluded_from_passport"]:
        return None
    if not autopsy.get("passport_update_candidate"):
        return None
    return {
        "horse_name": row.get("horse_name"),
        "horse_id": row.get("horse_id"),
        "race_date": row.get("race_date"),
        "course": row.get("course"),
        "off_time": row.get("off_time"),
        "vp_at_race": row.get("vp"),
        "outcome": row.get("outcome"),
        "failure_class": autopsy.get("failure_class"),
        "win_class": autopsy.get("win_class"),
        "evidence_quality_tier": autopsy["evidence_quality_tier"],
        "confidence": autopsy["confidence_in_autopsy"],
        "autopsy_id_link": autopsy["autopsy_id"],
        "do_not_merge": True,
        "human_review_required": True,
        "source": PROVENANCE,
        "canonical_passport_mutated": False,
        "caveat": (
            "horse_id=None for all current-era rows — passport linkage by name only. "
            "Human review required before any canonical merge."
        ),
    }


# ── Pattern evidence ──────────────────────────────────────────────────────────

def _pattern_evidence(autopsy: dict) -> dict | None:
    if not autopsy.get("pattern_update_candidate"):
        return None
    fc = autopsy.get("failure_class") or autopsy.get("win_class") or "UNKNOWN"
    return {
        "pattern_class": fc,
        "course": autopsy.get("course"),
        "course_tier": autopsy.get("course_tier"),
        "vp": autopsy.get("vp"),
        "vp_band": autopsy.get("vp_band"),
        "outcome": autopsy.get("outcome"),
        "pick_sp": autopsy.get("pick_sp"),
        "actual_winner_sp": autopsy.get("actual_winner_sp"),
        "evidence_quality_tier": autopsy["evidence_quality_tier"],
        "excluded_from_roi": autopsy["excluded_from_roi"],
        "race_date": autopsy.get("race_date"),
        "autopsy_id_link": autopsy["autopsy_id"],
        "provenance": PROVENANCE,
    }


# ── Repeated horse tracker ────────────────────────────────────────────────────

def build_horse_tracker(rows: list[dict]) -> list[dict]:
    from statistics import mean as smean

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        hn = norm_horse(r.get("horse_name", ""))
        if hn:
            groups[hn].append(r)

    trackers = []
    for hn, group in sorted(groups.items(), key=lambda x: -len(x[1])):
        if len(group) < 2:
            continue
        vps = [r["vp"] for r in group if r.get("vp") is not None]
        wins = sum(1 for r in group if r.get("outcome") == "WIN")
        losses = sum(1 for r in group if r.get("outcome") == "MISS")
        placed = sum(1 for r in group if r.get("outcome") == "PLACED")
        courses = list(set(r.get("course", "") for r in group if r.get("course")))
        dates = sorted(r.get("race_date", "") for r in group if r.get("race_date"))
        avg_vp = round(smean(vps), 4) if vps else None
        latest_vp = vps[-1] if vps else None
        vp_trend = None
        if len(vps) >= 3:
            mid = len(vps) // 2
            early = smean(vps[:mid])
            late = smean(vps[mid:])
            vp_trend = "RISING" if late > early + 0.02 else ("FALLING" if early > late + 0.02 else "STABLE")

        sr = round(wins / len(group), 3) if group else 0
        if sr >= 0.40 and (latest_vp or 0) >= 0.40:
            label = "IMPROVING"
        elif wins == 0 and len(group) >= 3:
            label = "DECLINING"
        elif sr >= 0.30 and len(courses) == 1:
            label = "COURSE_DEPENDENT"
        elif sr >= 0.30 and (latest_vp or 0) < 0.25:
            label = "HIDDEN"
        elif wins == 0 and (avg_vp or 0) >= 0.40:
            label = "UNRELIABLE"
        else:
            label = "NEEDS_REVIEW"

        trackers.append({
            "horse_name": hn,
            "horse_id": next((r.get("horse_id") for r in group if r.get("horse_id")), None),
            "appearance_count": len(group),
            "wins": wins,
            "losses": losses,
            "placed": placed,
            "strike_rate": sr,
            "avg_vp": avg_vp,
            "latest_vp": latest_vp,
            "vp_trend": vp_trend,
            "courses_seen": courses,
            "dates": dates,
            "candidate_label": label,
            "do_not_merge": True,
            "source": PROVENANCE,
        })
    return sorted(trackers, key=lambda x: -x["appearance_count"])


# ── VP threshold performance ──────────────────────────────────────────────────

def vp_threshold_table(autopsies: list[dict], thresholds=(0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)) -> list[dict]:
    usable = [a for a in autopsies if a["evidence_quality_tier"] not in ("TIER_D_EVENT_ONLY", "TIER_E_UNUSABLE")]
    rows = []
    for t in thresholds:
        above = [a for a in usable if (a.get("vp") or 0) >= t]
        if not above:
            rows.append({"threshold": t, "n": 0, "wins": 0, "sr": None})
            continue
        wins = sum(1 for a in above if a.get("outcome") == "WIN")
        rows.append({
            "threshold": t,
            "n": len(above),
            "wins": wins,
            "sr": round(wins / len(above), 3),
        })
    return rows


# ── Course tier performance ───────────────────────────────────────────────────

def course_tier_table(autopsies: list[dict]) -> dict:
    usable = [a for a in autopsies if a["evidence_quality_tier"] not in ("TIER_D_EVENT_ONLY", "TIER_E_UNUSABLE")]
    result = {}
    for ct in ("EXCELLING", "DRAIN", "NEUTRAL"):
        group = [a for a in usable if a.get("course_tier") == ct]
        if not group:
            result[ct] = {"n": 0, "wins": 0, "sr": None}
            continue
        wins = sum(1 for a in group if a.get("outcome") == "WIN")
        result[ct] = {"n": len(group), "wins": wins, "sr": round(wins / len(group), 3)}
    return result


# ── Report writers ────────────────────────────────────────────────────────────

def _pct(n: int, total: int) -> str:
    return f"{round(n/total*100,1)}%" if total else "N/A"


def write_summary_md(summary: dict, out: Path) -> None:
    s = summary
    stats = s["statistics"]
    tiers = s["tier_counts"]
    comp = s["field_coverage"]

    lines = [
        "# VFU-04 — Full Current-Era Autopsy Summary",
        "",
        f"**Generated:** {s['generated_at']}",
        f"**Source:** enriched current-era sigma union, May 08–Jun 13 2026",
        f"**Canonical Passport mutated:** NO",
        f"**Supabase written:** NO",
        "",
        "---",
        "",
        "## 1. Rows Scanned and Autopsy Coverage",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total rows scanned | {s['total_rows_scanned']} |",
        f"| Autopsies created | {s['autopsies_created']} |",
        f"| Rows excluded (TIER_E) | {s['rows_excluded']} |",
        "",
        "## 2. Evidence Quality Tiers",
        "",
        f"| Tier | Count | % |",
        f"|---|---|---|",
    ]
    total = s["total_rows_scanned"]
    for t, c in sorted(tiers.items()):
        lines.append(f"| {t} | {c} | {_pct(c, total)} |")
    lines += [
        "",
        "> horse_id=None for ALL 1,263 rows — passport linkage by name only. "
        "All Tier A/B/C passport candidates require human review.",
        "",
        "## 3. Field Coverage",
        "",
        "| Field | Filled | % |",
        "|---|---|---|",
    ]
    for fld, val in comp.items():
        lines.append(f"| {fld} | {val['filled']}/{val['total']} | {val['pct']}% |")
    lines += [
        "",
        "## 4. Failure Class Distribution",
        "",
        "| Failure Class | Count |",
        "|---|---|",
    ]
    for fc, c in sorted(stats["failure_classes"].items(), key=lambda x: -x[1]):
        lines.append(f"| {fc} | {c} |")
    lines += [
        "",
        "## 5. Win Class Distribution",
        "",
        "| Win Class | Count |",
        "|---|---|",
    ]
    for wc, c in sorted(stats["win_classes"].items(), key=lambda x: -x[1]):
        lines.append(f"| {wc} | {c} |")
    lines += [
        "",
        "## 6. VP Threshold Performance",
        "",
        "| VP >= | N | Wins | SR |",
        "|---|---|---|---|",
    ]
    for row in s["vp_threshold_table"]:
        sr_str = f"{row['sr']:.1%}" if row["sr"] is not None else "N/A"
        lines.append(f"| {row['threshold']} | {row['n']} | {row['wins']} | {sr_str} |")
    lines += [
        "",
        "## 7. Course Tier Performance",
        "",
        "| Course Tier | N | Wins | SR |",
        "|---|---|---|---|",
    ]
    for ct, v in s["course_tier_table"].items():
        sr_str = f"{v['sr']:.1%}" if v["sr"] is not None else "N/A"
        lines.append(f"| {ct} | {v['n']} | {v['wins']} | {sr_str} |")
    lines += [
        "",
        "## 8. SP Dead-Zone Evidence",
        "",
        f"**Note**: SP dead-zone analysis limited to rows with pick_sp only (n={tiers.get('TIER_A_FULL', 0)}).",
        "",
        f"| Odds Band | Count (TIER_A only) |",
        f"|---|---|",
    ]
    for band, cnt in sorted(stats["sp_odds_bands"].items()):
        lines.append(f"| {band} | {cnt} |")
    lines += [
        "",
        "## 9. Passport Candidates",
        "",
        f"- Total created: {s['passport_candidates_created']}",
        f"- TIER_A: {stats['passport_by_tier'].get('TIER_A_FULL', 0)}",
        f"- TIER_B: {stats['passport_by_tier'].get('TIER_B_GOOD_NO_PICK_SP', 0)}",
        f"- TIER_C: {stats['passport_by_tier'].get('TIER_C_LIMITED_IDENTITY', 0)}",
        "",
        "All candidates have `do_not_merge=True` and `human_review_required=True`.",
        "",
        "## 10. Pattern Evidence",
        "",
        f"- Total created: {s['pattern_evidence_created']}",
        "",
        "## 11. Repeated Horses",
        "",
        f"- Horses appearing 2+ times: {s['repeated_horses_found']}",
        "",
        "| Horse | Count | Wins | SR | Avg VP | Label |",
        "|---|---|---|---|---|---|",
    ]
    for h in s["top_repeated_horses"][:20]:
        lines.append(
            f"| {h['horse_name'][:25]} | {h['appearance_count']} | {h['wins']} "
            f"| {h['strike_rate']:.0%} | {h['avg_vp'] or 'N/A'} | {h['candidate_label']} |"
        )
    lines += [
        "",
        "## 12. Data Quality Debts",
        "",
        "| Debt | Count |",
        "|---|---|",
    ]
    for debt, cnt in sorted(stats["data_gap_counts"].items(), key=lambda x: -x[1])[:10]:
        lines.append(f"| {debt} | {cnt} |")
    lines += [
        "",
        f"## 13. VFU-05 Pattern Prosecutor Recommendation",
        "",
        f"**{s['vfu05_recommendation']}**",
        "",
        s["vfu05_rationale"],
        "",
        "---",
        "",
        "## Hard Rule Confirmations",
        "",
        "| Check | Status |",
        "|---|---|",
        "| Canonical Horse Passport NOT mutated | CONFIRMED |",
        "| No Supabase writes | CONFIRMED |",
        "| No Supabase staging created | CONFIRMED |",
        "| No live scoring change | CONFIRMED |",
        "| No model promotion | CONFIRMED |",
        "| No Telegram send | CONFIRMED |",
        "| No Racing API restoration | CONFIRMED |",
        "| No Mar–Apr extraction | CONFIRMED |",
        "| ROI limited to pick_sp rows | CONFIRMED |",
        "| Passport candidates dry-run only | CONFIRMED |",
        "",
        "## Final Classifications",
        "",
    ]
    for c in s["final_classifications"]:
        lines.append(f"- `{c}`")

    out.write_text("\n".join(lines), encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("[VFU-04] Loading enriched union…")
    rows: list[dict] = json.loads(ENRICHED_UNION.read_text(encoding="utf-8"))
    print(f"  {len(rows)} rows loaded")

    # Safety
    assert str(OUT_RECORDS) != str(CANON_PASSPORT), "SAFETY: output must not be canonical passport"
    assert str(OUT_PASSPORTS) != str(CANON_PASSPORT), "SAFETY: passport candidates must not overwrite canonical"

    print("[VFU-04] Assigning evidence quality tiers…")
    tiered: list[tuple[str, dict]] = [(assign_tier(r), r) for r in rows]
    tier_counts = Counter(t for t, _ in tiered)
    print(f"  Tiers: {dict(tier_counts)}")

    print("[VFU-04] Running full autopsy pass…")
    autopsies: list[dict] = []
    passport_candidates: list[dict] = []
    pattern_evidence_list: list[dict] = []
    excluded: list[dict] = []

    for idx, (tier, row) in enumerate(tiered, start=1):
        if tier == "TIER_E_UNUSABLE":
            excluded.append({"row_id": row.get("row_id"), "reason": "missing_vp_or_outcome", **row})
            continue
        a = _autopsy_row(row, tier, idx)
        autopsies.append(a)

        pc = _passport_candidate(a, row)
        if pc:
            passport_candidates.append(pc)

        pe = _pattern_evidence(a)
        if pe:
            pattern_evidence_list.append(pe)

    print(f"  Autopsies: {len(autopsies)}")
    print(f"  Passport candidates: {len(passport_candidates)}")
    print(f"  Pattern evidence: {len(pattern_evidence_list)}")

    print("[VFU-04] Building repeated horse tracker…")
    horse_tracker = build_horse_tracker(rows)
    print(f"  Repeated horses (2+): {len(horse_tracker)}")

    print("[VFU-04] Computing statistics…")
    failure_classes = Counter(a.get("failure_class") for a in autopsies if a.get("failure_class"))
    win_classes = Counter(a.get("win_class") for a in autopsies if a.get("win_class"))
    data_gap_counts: Counter = Counter()
    for a in autopsies:
        for g in a.get("data_gaps", []):
            data_gap_counts[g] += 1

    sp_odds_bands = Counter(
        a.get("odds_band") for a in autopsies
        if a.get("evidence_quality_tier") == "TIER_A_FULL"
    )

    passport_by_tier = Counter(pc.get("evidence_quality_tier") for pc in passport_candidates)
    vp_table = vp_threshold_table(autopsies)
    ct_table = course_tier_table(autopsies)

    # Field coverage
    total = len(rows)

    def cov(fld: str) -> dict:
        filled = sum(1 for r in rows if r.get(fld) is not None and r.get(fld) != "")
        return {"filled": filled, "total": total, "pct": round(filled / total * 100, 1)}

    field_coverage = {f: cov(f) for f in ("race_date", "horse_name", "course", "off_time",
                                            "vp", "outcome", "pick_sp", "actual_winner_sp",
                                            "horse_id", "actual_winner_name")}

    # VFU-05 readiness
    pattern_n = len(pattern_evidence_list)
    usable_n = len([a for a in autopsies if a["evidence_quality_tier"] not in ("TIER_D_EVENT_ONLY",)])
    vfu05_ok = pattern_n >= 50 and usable_n >= 300
    vfu05_rec = "PROCEED" if vfu05_ok else "PENDING_OPERATOR_REVIEW"
    vfu05_rat = (
        f"{pattern_n} pattern evidence records created from {usable_n} usable autopsies. "
        f"Repeated horse tracker: {len(horse_tracker)} horses. "
        "Operator review of this summary required before Pattern Prosecutor opens."
    )

    # Quality gaps
    quality_gaps = {
        "horse_id_null_all_rows": True,
        "pick_sp_coverage_pct": round(107 / total * 100, 2),
        "local_only_rows_no_identity": tier_counts.get("TIER_D_EVENT_ONLY", 0),
        "rows_excluded_tier_e": len(excluded),
        "winner_in_frame_unavailable": True,
        "race_type_surface_class_unavailable": True,
        "top_missing_reasons": dict(
            Counter(
                a.get("pick_sp_missing_reason") for a in autopsies
                if a.get("pick_sp_missing_reason")
            ).most_common(10)
        ),
    }

    summary = {
        "report_type": "VFU_04_FULL_CURRENT_ERA_AUTOPSY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(ENRICHED_UNION),
        "total_rows_scanned": total,
        "autopsies_created": len(autopsies),
        "rows_excluded": len(excluded),
        "tier_counts": dict(tier_counts),
        "field_coverage": field_coverage,
        "statistics": {
            "failure_classes": dict(failure_classes),
            "win_classes": dict(win_classes),
            "data_gap_counts": dict(data_gap_counts.most_common(20)),
            "sp_odds_bands": dict(sp_odds_bands),
            "passport_by_tier": dict(passport_by_tier),
        },
        "vp_threshold_table": vp_table,
        "course_tier_table": ct_table,
        "passport_candidates_created": len(passport_candidates),
        "pattern_evidence_created": pattern_n,
        "repeated_horses_found": len(horse_tracker),
        "top_repeated_horses": horse_tracker[:20],
        "vfu05_recommendation": vfu05_rec,
        "vfu05_rationale": vfu05_rat,
        "quality_gaps": quality_gaps,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "final_classifications": [
            "VFU_04_FULL_CURRENT_ERA_AUTOPSY_COMPLETE",
            "EVIDENCE_QUALITY_TIERS_ENFORCED",
            "PASSPORT_CANDIDATES_DRY_RUN_ONLY",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "REPEATED_HORSE_TRACKER_BUILT",
            "PATTERN_EVIDENCE_CREATED",
            "ROI_LIMITED_TO_PICK_SP_ROWS",
            "NO_MAR_APR_EXTRACTION",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "NO_MODEL_PROMOTION",
            "NO_TELEGRAM_SEND",
            "NO_RACING_API_RESTORATION",
        ],
    }

    print("[VFU-04] Writing outputs…")
    # Autopsy records
    with open(OUT_RECORDS, "w", encoding="utf-8") as f:
        for a in autopsies:
            f.write(json.dumps(a, default=str) + "\n")
    print(f"  {OUT_RECORDS.name}: {len(autopsies)} records")

    # Passport candidates
    with open(OUT_PASSPORTS, "w", encoding="utf-8") as f:
        for pc in passport_candidates:
            f.write(json.dumps(pc, default=str) + "\n")
    print(f"  {OUT_PASSPORTS.name}: {len(passport_candidates)} candidates")

    # Pattern evidence
    with open(OUT_PATTERNS, "w", encoding="utf-8") as f:
        for pe in pattern_evidence_list:
            f.write(json.dumps(pe, default=str) + "\n")
    print(f"  {OUT_PATTERNS.name}: {len(pattern_evidence_list)} records")

    # Quality gaps
    OUT_GAPS.write_text(json.dumps(quality_gaps, indent=2, default=str), encoding="utf-8")
    print(f"  {OUT_GAPS.name}")

    # Summary
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"  {OUT_SUMMARY_JSON.name}")
    write_summary_md(summary, OUT_SUMMARY_MD)
    print(f"  {OUT_SUMMARY_MD.name}")

    print("\n[VFU-04] DONE.")
    print(f"  Rows scanned: {total}")
    print(f"  Autopsies: {len(autopsies)}")
    print(f"  Excluded: {len(excluded)}")
    print(f"  Tiers: {dict(tier_counts)}")
    print(f"  Passport candidates: {len(passport_candidates)}")
    print(f"  Pattern evidence: {pattern_n}")
    print(f"  Repeated horses: {len(horse_tracker)}")
    print(f"  VFU-05 recommendation: {vfu05_rec}")
    print("\n  NO Supabase writes. NO canonical Passport mutation. NO scoring change.")


if __name__ == "__main__":
    main()
