#!/usr/bin/env python3
"""
VFU-21: pick_sp Backfill

Recovers the SP (starting price) for VÉLØ's top selection across the full
VFU-20 repaired ledger wherever pick_sp is null, 0.0, or 10.0 (the artificial
pre-fix default). Source: local RP results files (data/results/).

Recovery provenance:
  RECOVERED_FROM_RP_RESULTS    — found sp_dec in results runners
  UNRECOVERABLE_NO_RESULTS_FILE — no rp_results file for that date
  UNRECOVERABLE_SP_NOT_IN_FILE  — file exists but runners have no sp_dec
  UNRECOVERABLE_HORSE_NOT_FOUND — file + SP present but horse name not matched
  ORIGINAL_PRESENT              — pick_sp was already a real value, not touched

Evidence quality tier upgrade:
  TIER_B_GOOD_NO_PICK_SP → TIER_B_GOOD  (SP recovered, horse_id still absent)
  TIER_B_GOOD_NO_PICK_SP → TIER_A_FULL  (SP recovered + horse_id present)

Usage:
    python scripts/ops/vfu_pick_sp_backfill.py
    python scripts/ops/vfu_pick_sp_backfill.py --ledger path/to/ledger.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

INPUT_LEDGER   = DATA / "reports" / "vfu_20_field_size_repaired_ledger.jsonl"
OUTPUT_LEDGER  = DATA / "reports" / "vfu_21_pick_sp_backfill_ledger.jsonl"
OUTPUT_SUMMARY = DATA / "reports" / "vfu_21_pick_sp_backfill_summary.json"
OUTPUT_BRIEF   = DATA / "reports" / "vfu_21_pick_sp_backfill_summary.md"

RECOVERY_DONE      = "RECOVERED_FROM_RP_RESULTS"
NO_FILE            = "UNRECOVERABLE_NO_RESULTS_FILE"
NO_SP_IN_FILE      = "UNRECOVERABLE_SP_NOT_IN_FILE"
HORSE_NOT_FOUND    = "UNRECOVERABLE_HORSE_NOT_FOUND"
ORIGINAL_PRESENT   = "ORIGINAL_PRESENT"

VFU_VERSION = "VFU_21_PICK_SP_BACKFILL_V1"


# ------------------------------------------------------------------
# Name normalization
# ------------------------------------------------------------------

def normalize_name(name: str) -> str:
    return (name or "").lower().strip().replace("'", "").replace("-", " ").replace("  ", " ")


# ------------------------------------------------------------------
# Results file SP index builder — handles all 3 observed schemas
# ------------------------------------------------------------------

def _build_sp_index(date_tag: str) -> tuple[dict[str, float], str]:
    """
    Return ({normalized_name: sp_dec}, status) where status is one of:
      'ok'              — index built with at least one runner having SP
      'no_file'         — rp_results file not present
      'no_sp_in_file'   — file present but all runners have sp_dec == 0 / missing
    """
    path = DATA / "results" / f"rp_results_{date_tag}.json"
    if not path.exists():
        return {}, "no_file"

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, "no_file"

    # Determine races list
    if isinstance(raw, list):
        races = raw
    elif isinstance(raw, dict):
        races = raw.get("results", [])
    else:
        return {}, "no_sp_in_file"

    sp_index: dict[str, float] = {}
    for race in races:
        # Try standard 'runners' key first, then 'full_runners'
        runners = race.get("runners") or race.get("full_runners") or []
        for runner in runners:
            name_raw = runner.get("horse") or runner.get("horse_name") or ""
            sp_val   = runner.get("sp_dec")
            try:
                sp_float = float(sp_val)
            except (TypeError, ValueError):
                sp_float = 0.0
            if name_raw and sp_float > 0.0:
                sp_index[normalize_name(name_raw)] = sp_float

    status = "ok" if sp_index else "no_sp_in_file"
    return sp_index, status


# ------------------------------------------------------------------
# Is this row a backfill candidate?
# ------------------------------------------------------------------

def _needs_backfill(row: dict) -> bool:
    sp = row.get("pick_sp")
    return sp is None or sp == 0.0 or sp == 10.0


# ------------------------------------------------------------------
# Process single row
# ------------------------------------------------------------------

def process_row(row: dict, sp_indexes: dict[str, tuple[dict, str]]) -> dict:
    """Augment a ledger row with VFU-21 pick_sp recovery fields."""
    out = dict(row)

    if not _needs_backfill(row):
        out["pick_sp_recovery_method"]   = ORIGINAL_PRESENT
        out["pick_sp_confidence"]        = "HIGH"
        out["pick_sp_pre_backfill"]      = row.get("pick_sp")
        out["vfu21_validation_version"]  = VFU_VERSION
        return out

    date_tag  = row["race_date"].replace("-", "_")
    pre_value = row.get("pick_sp")

    if date_tag not in sp_indexes:
        # Build lazily and cache
        sp_indexes[date_tag] = _build_sp_index(date_tag)

    sp_index, file_status = sp_indexes[date_tag]

    if file_status == "no_file":
        out["pick_sp_recovery_method"]  = NO_FILE
        out["pick_sp_confidence"]       = "NONE"
        out["pick_sp_pre_backfill"]     = pre_value
        out["vfu21_validation_version"] = VFU_VERSION
        return out

    if file_status == "no_sp_in_file":
        out["pick_sp_recovery_method"]  = NO_SP_IN_FILE
        out["pick_sp_confidence"]       = "NONE"
        out["pick_sp_pre_backfill"]     = pre_value
        out["vfu21_validation_version"] = VFU_VERSION
        return out

    # File has SP — try to find the horse
    norm_name = normalize_name(row.get("horse_name") or "")
    recovered_sp = sp_index.get(norm_name)

    if recovered_sp is None:
        out["pick_sp_recovery_method"]  = HORSE_NOT_FOUND
        out["pick_sp_confidence"]       = "NONE"
        out["pick_sp_pre_backfill"]     = pre_value
        out["vfu21_validation_version"] = VFU_VERSION
        return out

    # Recovered
    out["pick_sp"]                  = recovered_sp
    out["pick_sp_recovery_method"]  = RECOVERY_DONE
    out["pick_sp_confidence"]       = "HIGH"
    out["pick_sp_pre_backfill"]     = pre_value
    out["vfu21_validation_version"] = VFU_VERSION

    # Evidence tier upgrade
    old_tier = row.get("evidence_quality_tier")
    if old_tier == "TIER_B_GOOD_NO_PICK_SP":
        has_horse_id = bool(row.get("horse_id"))
        out["evidence_quality_tier"] = "TIER_A_FULL" if has_horse_id else "TIER_B_GOOD"

    return out


# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------

def build_summary(rows_in: list[dict], rows_out: list[dict]) -> dict:
    from collections import Counter
    methods = Counter(r["pick_sp_recovery_method"] for r in rows_out)
    tier_before = Counter(r.get("evidence_quality_tier") for r in rows_in)
    tier_after  = Counter(r.get("evidence_quality_tier") for r in rows_out)

    candidates  = sum(1 for r in rows_in if _needs_backfill(r))
    recovered   = methods.get(RECOVERY_DONE, 0)
    unrecov     = candidates - recovered
    total       = len(rows_out)
    real_sp_after = sum(1 for r in rows_out
                        if r.get("pick_sp") and r["pick_sp"] not in (0.0,))

    return {
        "vfu21_validation_version": VFU_VERSION,
        "total_rows":               total,
        "backfill_candidates":      candidates,
        "recovered":                recovered,
        "recovery_rate":            round(recovered / candidates, 4) if candidates else 0,
        "unrecoverable":            unrecov,
        "method_breakdown":         dict(methods),
        "real_sp_coverage_before":  sum(1 for r in rows_in
                                        if r.get("pick_sp") and r["pick_sp"] not in (0.0,)),
        "real_sp_coverage_after":   real_sp_after,
        "real_sp_pct_after":        round(real_sp_after / total, 4) if total else 0,
        "evidence_tier_before":     dict(tier_before),
        "evidence_tier_after":      dict(tier_after),
        "classification_codes": [
            "VFU_21_PICK_SP_BACKFILL_COMPLETE",
            "SP_RECOVERED_FROM_RP_RESULTS",
            "UNRECOVERABLE_CLASSIFIED_BY_REASON",
            "EVIDENCE_TIER_UPGRADED_WHERE_POSSIBLE",
            "NO_VP_THRESHOLD_CHANGE",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }


def build_brief(summary: dict) -> str:
    total    = summary["total_rows"]
    cands    = summary["backfill_candidates"]
    rec      = summary["recovered"]
    unrecov  = summary["unrecoverable"]
    pct_rec  = summary["recovery_rate"] * 100
    after    = summary["real_sp_coverage_after"]
    pct_aft  = summary["real_sp_pct_after"] * 100
    methods  = summary["method_breakdown"]

    lines = [
        "# VFU-21 — pick_sp Backfill — Operator Brief",
        "",
        "## Summary",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total ledger rows | {total} |",
        f"| Backfill candidates (null / 0.0 / 10.0) | {cands} |",
        f"| Recovered | {rec} ({pct_rec:.1f}% of candidates with results files) |",
        f"| Unrecoverable | {unrecov} |",
        f"| Real pick_sp coverage after backfill | {after}/{total} ({pct_aft:.1f}%) |",
        "",
        "## Method Breakdown",
        f"| Method | Count |",
        f"|---|---|",
    ]
    for method, count in sorted(methods.items(), key=lambda x: -x[1]):
        lines.append(f"| {method} | {count} |")

    lines += [
        "",
        "## Evidence Tier Changes",
        "| Tier | Before | After |",
        "|---|---|---|",
    ]
    all_tiers = set(summary["evidence_tier_before"]) | set(summary["evidence_tier_after"])
    for tier in sorted(t for t in all_tiers if t):
        b = summary["evidence_tier_before"].get(tier, 0)
        a = summary["evidence_tier_after"].get(tier, 0)
        if b != a:
            lines.append(f"| {tier} | {b} | **{a}** |")
        else:
            lines.append(f"| {tier} | {b} | {a} |")

    lines += [
        "",
        "## Classifications",
        *[f"- {c}" for c in summary["classification_codes"]],
        "",
        "## Operating Lock (unchanged)",
        "- NO Passport mutation",
        "- NO Supabase writes",
        "- NO live scoring change",
        "- NO model promotion",
        f"- Validated by: {VFU_VERSION}",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main(ledger_path: Path = INPUT_LEDGER) -> dict:
    rows_in = [json.loads(l) for l in ledger_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    sp_indexes: dict[str, tuple[dict, str]] = {}
    rows_out: list[dict] = []

    for row in rows_in:
        rows_out.append(process_row(row, sp_indexes))

    # Write output
    OUTPUT_LEDGER.write_text(
        "\n".join(json.dumps(r) for r in rows_out) + "\n",
        encoding="utf-8",
    )

    summary = build_summary(rows_in, rows_out)
    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_BRIEF.write_text(build_brief(summary), encoding="utf-8")

    print(f"VFU-21 complete: {summary['recovered']}/{summary['backfill_candidates']} rows recovered")
    print(f"  Real pick_sp coverage: {summary['real_sp_coverage_after']}/{summary['total_rows']}"
          f" ({summary['real_sp_pct_after']*100:.1f}%)")
    print(f"  Method breakdown: {summary['method_breakdown']}")
    print(f"  Ledger:  {OUTPUT_LEDGER}")
    print(f"  Summary: {OUTPUT_SUMMARY}")
    print(f"  Brief:   {OUTPUT_BRIEF}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFU-21: pick_sp backfill from RP results files")
    parser.add_argument("--ledger", default=str(INPUT_LEDGER),
                        help="Input ledger JSONL path")
    args = parser.parse_args()
    main(Path(args.ledger))
