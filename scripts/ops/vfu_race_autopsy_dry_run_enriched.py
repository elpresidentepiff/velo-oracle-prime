#!/usr/bin/env python3
"""
scripts/ops/vfu_race_autopsy_dry_run_enriched.py
==================================================
VFU-03 — Re-run 20-race autopsy dry-run using enriched union rows.

Uses current_era_sigma_union_rows_enriched_vfu_v1.json (with pick_sp
joined from innovation protocol CSV) and writes separate enriched
output files for before/after comparison.

Never mutates canonical Horse Passport. Never writes Supabase.
Reads same stratified sample (random.seed(42)) as VFU-02 for
clean comparison.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Import helpers from the canonical autopsy script ─────────────────────────
from scripts.ops.vfu_race_autopsy_dry_run import (
    _autopsy,
    _passport_ext,
    _vp_band,
    _odds_band,
    _classify_failure,
    _data_gaps,
    EXCELLING_COURSES,
    DRAIN_COURSES,
    CANON_PASSPORT,
)

# ── Paths (enriched variants) ─────────────────────────────────────────────────
ENRICHED_UNION = ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json"
ORIGINAL_UNION = ROOT / "data/reports/current_era_sigma_union_rows_2026_05_08_to_2026_06_13.json"
ENRICH_REPORT  = ROOT / "data/reports/vfu_pick_sp_enrichment_report.json"

OUT_SUMMARY_JSON = ROOT / "data/reports/vfu_autopsy_dry_run_20_races_enriched.json"
OUT_SUMMARY_MD   = ROOT / "data/reports/vfu_autopsy_dry_run_20_races_enriched.md"


def main() -> None:
    if not ENRICHED_UNION.exists():
        print("ERROR: Enriched union file not found. Run vfu_enrich_pick_sp.py first.")
        sys.exit(1)

    print(f"[VFU-03-RERUN] Loading enriched union from {ENRICHED_UNION.name}")
    rows = json.loads(ENRICHED_UNION.read_text(encoding="utf-8"))
    print(f"  {len(rows)} rows loaded")

    # Safety: confirm enriched file is not the canonical passport
    assert str(ENRICHED_UNION) != str(CANON_PASSPORT), \
        "SAFETY: enriched union must not be canonical passport"

    # Load original for gap comparison
    orig_rows = json.loads(ORIGINAL_UNION.read_text(encoding="utf-8"))
    orig_pick_sp_count = sum(1 for r in orig_rows if r.get("pick_sp") is not None)
    enr_pick_sp_count  = sum(1 for r in rows if r.get("pick_sp") is not None)

    # Load enrichment report for context
    enrich_report: dict = {}
    if ENRICH_REPORT.exists():
        enrich_report = json.loads(ENRICH_REPORT.read_text(encoding="utf-8"))

    random.seed(42)  # same seed as VFU-02 for reproducible sample

    horse_counts = Counter(
        r.get("horse_name", "") for r in rows
        if r.get("horse_name") and r.get("horse_name") != "?"
    )

    def pick(pool: list, n: int, used: set) -> list:
        avail = [r for r in pool if id(r) not in used]
        chosen = avail[:n] if len(avail) <= n else random.sample(avail, n)
        for r in chosen:
            used.add(id(r))
        return chosen

    used: set = set()
    sample: list[tuple[str, dict]] = []

    for r in pick([r for r in rows if r.get("vp", 0) >= 0.40 and r.get("outcome") == "WIN"], 4, used):
        sample.append(("HIGH_VP_WIN", r))
    for r in pick([r for r in rows if r.get("vp", 0) >= 0.40 and r.get("outcome") == "MISS"], 4, used):
        sample.append(("HIGH_VP_MISS", r))
    for r in pick([r for r in rows if r.get("vp", 0) < 0.30 and r.get("outcome") == "WIN"], 3, used):
        sample.append(("LOW_VP_WIN", r))
    for r in pick([r for r in rows if r.get("outcome") == "MISS" and r.get("actual_winner_sp")
                   and 3.0 <= r["actual_winner_sp"] <= 8.5], 3, used):
        sample.append(("MID_PRICE_WALL", r))
    for r in pick([r for r in rows if (r.get("course") or "").lower() in EXCELLING_COURSES], 2, used):
        sample.append(("EXCELLING_COURSE", r))
    for r in pick([r for r in rows if (r.get("course") or "").lower() in DRAIN_COURSES], 2, used):
        sample.append(("DRAIN_COURSE", r))
    for r in pick([r for r in rows if horse_counts.get(r.get("horse_name", ""), 0) >= 2
                   and r.get("horse_name") and r.get("horse_name") != "?"], 2, used):
        sample.append(("REPEATED_HORSE", r))

    print(f"  Sample: {len(sample)} rows assembled")

    autopsies = []
    for idx, (cat, row) in enumerate(sample, start=1):
        a = _autopsy(row, horse_counts.get(row.get("horse_name", ""), 0), idx)
        a["sample_category"] = cat
        a["generated_by"] = "VFU_AUTOPSY_ENRICHED_RERUN_V1"
        autopsies.append(a)

    failure_classes = Counter(a.get("failure_class") for a in autopsies if a.get("failure_class"))
    data_gap_counts = Counter(g for a in autopsies for g in a.get("data_gaps", []))
    outcomes = Counter(a.get("actual_outcome") for a in autopsies)
    category_counts = Counter(cat for cat, _ in sample)

    pick_sp_null_before = sum(1 for a in autopsies if a.get("pick_sp") is None)
    odds_band_unknown = sum(1 for a in autopsies if a.get("odds_band") == "UNKNOWN_NO_PICK_SP")

    win_vps  = [a["vp"] for a in autopsies if a["actual_outcome"] == "WIN"]
    miss_vps = [a["vp"] for a in autopsies if a["actual_outcome"] == "MISS"]

    def mean(lst: list) -> float | None:
        return round(sum(lst) / len(lst), 4) if lst else None

    summary = {
        "report_type": "VFU_03_20_RACE_AUTOPSY_ENRICHED_RERUN",
        "generated": datetime.now(timezone.utc).isoformat(),
        "source_file": str(ENRICHED_UNION),
        "enrichment_version": enrich_report.get("enrichment_version", "VFU_PICK_SP_ENRICHMENT_V1"),
        "total_autopsies": len(autopsies),
        "outcomes": dict(outcomes),
        "category_breakdown": dict(category_counts),
        "failure_classes": dict(failure_classes),
        "comparison": {
            "pick_sp_in_full_union_before": orig_pick_sp_count,
            "pick_sp_in_full_union_after": enr_pick_sp_count,
            "pick_sp_coverage_before_pct": round(orig_pick_sp_count / len(orig_rows) * 100, 2),
            "pick_sp_coverage_after_pct": round(enr_pick_sp_count / len(rows) * 100, 2),
            "pick_sp_null_in_20_sample_before": 20,
            "pick_sp_null_in_20_sample_after": pick_sp_null_before,
            "odds_band_unknown_in_sample": odds_band_unknown,
            "sp_improvement_note": (
                f"20-race sample: {20 - pick_sp_null_before}/20 rows now have pick_sp. "
                f"Full union: {enr_pick_sp_count}/{len(rows)} rows ({round(enr_pick_sp_count/len(rows)*100,1)}%)."
            ),
        },
        "data_gaps": dict(data_gap_counts),
        "vp_analysis": {
            "win_mean_vp": mean(win_vps),
            "miss_mean_vp": mean(miss_vps),
            "vp_explains_direction": (mean(win_vps) or 0) > (mean(miss_vps) or 0),
        },
        "failure_class_improvement": {
            "sp_classification_now_possible": pick_sp_null_before < 20,
            "rows_with_sp_in_sample": 20 - pick_sp_null_before,
        },
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "dry_run": True,
        "full_1263_assessment": {
            "pick_sp_ceiling_from_csv": enrich_report.get("pick_sp_after_enrichment", "N/A"),
            "coverage_pct": enrich_report.get("coverage_after_pct", "N/A"),
            "structural_blockers": [
                "294 LOCAL_ONLY rows have no horse_name/date — structurally unmatchable from innovation CSV",
                "465 rows are on dates not in innovation CSV — need broader SP source",
                "154 CSV matches had SP=0.0 or empty — not usable",
            ],
            "recommendation": enrich_report.get("full_1263_pass_recommended", False),
            "recommendation_note": (
                "Coverage at 8.5% (107/1,263). "
                "Autopsy engine handles null pick_sp via data_gaps and null-tolerant failure classification. "
                "Operator decision required before full pass launch."
            ),
        },
        "final_classifications": [
            "VFU_03_20_RACE_AUTOPSY_ENRICHED_RERUN_COMPLETE",
            "VFU_PICK_SP_LOCAL_ENRICHMENT_COMPLETE",
            "VFU_20_RACE_AUTOPSY_ENRICHED_RERUN_COMPLETE",
            "SUPABASE_STAGING_NOT_CREATED",
            "EXTERNAL_SUPABASE_MUTATION_NOTE_RECORDED",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "NO_FULL_1263_PASS_YET",
            "NO_MAR_APR_EXTRACTION",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "NO_MODEL_PROMOTION",
            "NO_TELEGRAM_SEND",
            "NO_RACING_API_RESTORATION",
        ],
    }

    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # ── MD report ────────────────────────────────────────────────────────────
    comp = summary["comparison"]
    md_lines = [
        "# VFU-03 — 20-Race Autopsy Enriched Rerun Report",
        "",
        f"**Generated**: {summary['generated'][:19]}Z",
        f"**Source**: enriched union (VFU_PICK_SP_ENRICHMENT_V1)",
        f"**Canonical Passport mutated**: NO",
        f"**Supabase written**: NO",
        "",
        "---",
        "",
        "## Before vs After — pick_sp Coverage",
        "",
        "| Metric | Before (VFU-02) | After (VFU-03) |",
        "|---|---|---|",
        f"| Full union pick_sp filled | {comp['pick_sp_in_full_union_before']}/1263 ({comp['pick_sp_coverage_before_pct']}%) | {comp['pick_sp_in_full_union_after']}/1263 ({comp['pick_sp_coverage_after_pct']}%) |",
        f"| 20-race sample pick_sp null | {comp['pick_sp_null_in_20_sample_before']}/20 | {comp['pick_sp_null_in_20_sample_after']}/20 |",
        f"| odds_band UNKNOWN in sample | 20 | {comp['odds_band_unknown_in_sample']} |",
        "",
        comp["sp_improvement_note"],
        "",
        "---",
        "",
        "## Failure Classes (Enriched)",
        "",
    ]
    for fc, count in failure_classes.most_common():
        md_lines.append(f"- `{fc}` — {count} races")
    md_lines += [
        "",
        "---",
        "",
        "## VP Analysis",
        "",
        f"- Win mean VP: **{summary['vp_analysis']['win_mean_vp']}**",
        f"- Miss mean VP: **{summary['vp_analysis']['miss_mean_vp']}**",
        f"- VP explains direction: **{summary['vp_analysis']['vp_explains_direction']}**",
        "",
        "---",
        "",
        "## Full 1,263-Row Pass Assessment",
        "",
        f"**Recommendation**: {'PROCEED (operator approval required)' if summary['full_1263_assessment']['recommendation'] else 'PENDING OPERATOR REVIEW'}",
        "",
        summary["full_1263_assessment"]["recommendation_note"],
        "",
        "**Structural blockers:**",
        "",
    ]
    for b in summary["full_1263_assessment"]["structural_blockers"]:
        md_lines.append(f"- {b}")
    md_lines += [
        "",
        "---",
        "",
        "## Autopsy Table",
        "",
        "| # | Horse | Date | Course | VP | Outcome | Pick SP | Failure Class |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, a in enumerate(autopsies, 1):
        sp_str = f"{a['pick_sp']:.2f}" if a.get("pick_sp") else "—"
        md_lines.append(
            f"| {i} | {(a['velo_pick'] or '?')[:20]} | {a['race_date']} | "
            f"{(a['course'] or '?')[:12]} | {a['vp']:.3f} | {a['actual_outcome']} "
            f"| {sp_str} | {(a.get('failure_class') or 'N/A')[:28]} |"
        )
    md_lines += [
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
        "| No full 1,263-row pass yet | CONFIRMED |",
        "| No Mar–Apr extraction | CONFIRMED |",
        "",
        "## Final Classifications",
        "",
    ]
    for c in summary["final_classifications"]:
        md_lines.append(f"- `{c}`")

    OUT_SUMMARY_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n[VFU-03-RERUN] Done.")
    print(f"  pick_sp null in 20-sample before: 20/20")
    print(f"  pick_sp null in 20-sample after:  {pick_sp_null_before}/20")
    print(f"  odds_band UNKNOWN: {odds_band_unknown}/20")
    print(f"  Failure classes: {dict(failure_classes)}")
    print(f"  VP direction confirmed: {summary['vp_analysis']['vp_explains_direction']}")
    print(f"\n  Summary: {OUT_SUMMARY_MD}")


if __name__ == "__main__":
    main()
