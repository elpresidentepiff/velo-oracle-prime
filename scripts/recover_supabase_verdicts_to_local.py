#!/usr/bin/env python3
"""
RECOVER_SUPABASE_VERDICTS_TO_LOCAL_V1

Attempts to close the Category A corpus gap by recovering Railway-only
verdict dates from Supabase into local JSON truth.

Two recovery phases:

  Phase A: Supabase velo_verdicts full-fidelity reconstruction
           — only for dates in velo_verdicts table but absent from local disk.
           — Full signal coverage: VP, MDS, improvement, place_prob.
           — Limitation: velo_verdicts only holds 2026-04-22+, so most Category A
             dates (pre-April 22) have no data here.

  Phase B: sigma_audits notes reconstruction (partial fidelity)
           — For dates where sigma_audits rows AND local results JSON exist
             but no local verdict JSON exists.
           — Signal coverage: velo_prime_prob only (parsed from notes summary).
             mds / improvement / place_prob = null.
           — These rows reach the corpus but most will be Category G
             (3+ signal fields missing) unless other sources fill the gap.

Safety rules (permanent — never violate):
  NO DB writes | NO scoring changes | NO staking | NO Telegram
  --dry-run (default): report only, zero file writes
  --execute: write verdict JSON files to data/

Outputs:
    data/reports/supabase_verdict_recovery_dry_run_latest.json
    data/reports/supabase_verdict_recovery_dry_run_latest.md

Usage:
    python scripts/recover_supabase_verdicts_to_local.py --dry-run
    python scripts/recover_supabase_verdicts_to_local.py --execute
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS_DIR = DATA / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def _load_sb():
    from dotenv import load_dotenv
    load_dotenv()
    sys.path.insert(0, str(ROOT))
    from src.data.supabase_client import get_supabase_client
    return get_supabase_client()


def _local_verdict_date_map():
    result = {}
    for p in sorted(DATA.glob("velo_prime_verdicts_2026_*.json")):
        m = re.search(r"(\d{4}_\d{2}_\d{2})", p.name)
        if m:
            result[m.group(1).replace("_", "-")] = p
    return result


def _local_result_date_map():
    result = {}
    for p in sorted(DATA.glob("results_2026_*.json")):
        m = re.search(r"(\d{4}_\d{2}_\d{2})", p.name)
        if m:
            result[m.group(1).replace("_", "-")] = p
    return result


def _fetch_velo_verdicts_dates(sb):
    """Return set of distinct dates present in Supabase velo_verdicts."""
    resp = sb.client.table("velo_verdicts").select("generated_at").execute()
    return sorted(set(r["generated_at"][:10] for r in (resp.data or [])))


def _fetch_sigma_all(sb):
    """Fetch all sigma_audits rows (paginated)."""
    rows = []
    offset = 0
    while True:
        resp = sb.client.table("sigma_audits").select(
            "id,race_id,date,track,off_time,horse_id,decision_tier,outcome,actual_winner_sp,notes"
        ).range(offset, offset + 999).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows


def _parse_notes_vp(notes_raw) -> tuple[float | None, str | None]:
    """Extract velo_prime_prob and predicted horse name from sigma_audits notes."""
    try:
        notes = json.loads(notes_raw) if notes_raw else {}
    except Exception:
        return None, None
    if not isinstance(notes, dict):
        return None, None
    summary = notes.get("summary", "")
    prob_m = re.search(r"prob=([0-9.]+)", summary)
    pred_m = re.search(r"pred=([^|]+)", summary)
    vp = float(prob_m.group(1)) if prob_m else None
    pred = pred_m.group(1).strip() if pred_m else None
    return vp, pred


# ── Phase A: Full-fidelity from velo_verdicts ────────────────────────────────

def _reconstruct_phase_a(sb, date: str) -> list[dict]:
    """Pull velo_verdicts rows for a date, reconstruct local verdict JSON list."""
    resp = sb.client.table("velo_verdicts").select(
        "race_id,decision_tier,velo_prime_prob,market_deception_score,"
        "improvement_score,place_prob,longshot_prob,release_day_prob,"
        "confidence_level_effective,full_analysis,generated_at"
    ).gte("generated_at", date + "T00:00:00").lt("generated_at", date + "T23:59:59").execute()

    rows = resp.data or []
    verdict_list = []
    for row in rows:
        full_analysis = row.get("full_analysis") or []
        # Find top horse: use top_rank from velo_verdicts flat VP score
        top_horse = {}
        if full_analysis:
            # Sort by velo_prime_prob to confirm top
            ranked = sorted(full_analysis, key=lambda x: float(x.get("velo_prime_prob") or 0), reverse=True)
            top_horse = ranked[0] if ranked else {}

        verdict_list.append({
            "race_id": row["race_id"],
            "course": top_horse.get("course", ""),
            "off_time": top_horse.get("off_time", ""),
            "race_name": "",
            "tier": row.get("decision_tier", ""),
            "scored": len(full_analysis),
            "top": {
                "horse": top_horse.get("horse", ""),
                "horse_id": top_horse.get("horse_id", ""),
                "race_id": row["race_id"],
                "velo_prime_prob": row.get("velo_prime_prob"),
                "market_deception_score": row.get("market_deception_score"),
                "improvement_score": row.get("improvement_score"),
                "place_prob": row.get("place_prob"),
                "longshot_prob": row.get("longshot_prob"),
                "release_day_prob": row.get("release_day_prob"),
                "comment_intel_score": None,
                "confidence_level": row.get("confidence_level_effective"),
                "decision_tier": row.get("decision_tier"),
            },
            "_recovery_meta": {
                "source": "phase_a_supabase_velo_verdicts",
                "recovered_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
                "signal_fidelity": "FULL",
                "course_off_time_available": bool(top_horse.get("off_time")),
            },
        })
    return verdict_list


# ── Phase B: Partial-fidelity from sigma_audits notes ────────────────────────

def _reconstruct_phase_b(sigma_rows: list[dict]) -> list[dict]:
    """Build verdict JSON list from sigma_audits rows (VP only from notes)."""
    verdict_list = []
    for row in sigma_rows:
        vp, pred_horse = _parse_notes_vp(row.get("notes"))
        if vp is None:
            continue
        verdict_list.append({
            "race_id": row["race_id"],
            "course": row.get("track", ""),
            "off_time": row.get("off_time", ""),
            "race_name": "",
            "tier": row.get("decision_tier", ""),
            "scored": 1,
            "top": {
                "horse": pred_horse or "",
                "horse_id": row.get("horse_id", ""),
                "race_id": row["race_id"],
                "velo_prime_prob": vp,
                "market_deception_score": None,
                "improvement_score": None,
                "place_prob": None,
                "longshot_prob": None,
                "release_day_prob": None,
                "comment_intel_score": None,
                "confidence_level": None,
                "decision_tier": row.get("decision_tier", ""),
            },
            "_recovery_meta": {
                "source": "phase_b_sigma_audits_notes",
                "recovered_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
                "signal_fidelity": "PARTIAL_VP_ONLY",
                "training_risk": "Category G (missing mds/improvement/place_prob)",
                "sigma_id": row.get("id"),
                "sigma_outcome": row.get("outcome"),
            },
        })
    return verdict_list


# ── Markdown report ───────────────────────────────────────────────────────────

def _build_md(report: dict) -> str:
    pa = report["phase_a"]
    pb = report["phase_b"]
    gap = report["gap_assessment"]
    lines = [
        "# SUPABASE VERDICT RECOVERY — DRY RUN REPORT",
        f"**Run:** {report['run_ts']}",
        f"**Mode:** {report['mode']}",
        "",
        "---",
        "",
        "## Context: What the Category A Gap Actually Is",
        "",
        "The exclusion audit identified ~620 rows / 30 dates in sigma_audits with no local",
        "verdict JSON. The assumption was that Supabase velo_verdicts holds these.",
        "",
        "**Reality:**",
        "",
        f"| Source | Dates available | Date range |",
        f"|---|---|---|",
        f"| Local verdict JSONs | {report['local_verdict_dates']} dates | 2026-03-17 to 2026-05-17 |",
        f"| Supabase velo_verdicts | {report['supabase_vv_dates']} dates | 2026-04-22 to 2026-05-17 |",
        f"| sigma_audits | 66 dates | 2026-01-09 to 2026-05-17 |",
        "",
        "Supabase velo_verdicts only holds recent data (April 22+). All April 22+ dates",
        "already have local verdict JSONs. The pre-April-22 Category A gap is not in velo_verdicts.",
        "",
        "---",
        "",
        "## Phase A — velo_verdicts Full-Fidelity Recovery",
        "",
        f"**Candidates** (in velo_verdicts, not in local): **{pa['candidate_dates']} dates**",
        "",
    ]
    if pa["details"]:
        lines += [
            "| Date | Races | Has Results | Signal Fidelity | Training Safe |",
            "|---|---|---|---|---|",
        ]
        for d in pa["details"]:
            lines.append(
                f"| {d['date']} | {d['races']} | {'Yes' if d['has_results'] else 'No'} | "
                f"FULL (VP+MDS+IMP+PP) | {'Yes' if d['has_results'] else 'No (no result file)'} |"
            )
    else:
        lines.append("No Phase A candidates found — all velo_verdicts dates already have local JSONs.")
    lines += [
        "",
        "**Phase A training impact:**",
        f"- Races: {pa['races']}",
        f"- Training-safe rows estimated: {pa['training_safe_estimate']} (requires results file)",
        "",
        "---",
        "",
        "## Phase B — sigma_audits Notes Reconstruction (Partial)",
        "",
        f"**Candidates** (sigma + results exist, no verdict JSON): **{pb['candidate_dates']} dates**",
        "",
        "| Date | Sigma rows | Parseable | VP extracted | Signal fidelity | Training risk |",
        "|---|---|---|---|---|---|",
    ]
    for d in pb["details"]:
        lines.append(
            f"| {d['date']} | {d['sigma_rows']} | {d['parseable']} | {d['vp_extracted']} | "
            f"PARTIAL (VP only) | Category G likely |"
        )
    lines += [
        "",
        f"**Phase B total:** {pb['vp_extracted_total']} races across {pb['candidate_dates']} dates",
        "",
        "⚠️ **Category G warning:** Phase B rows have VP but no MDS/improvement/place_prob.",
        "These rows will enter the corpus with result_matched=True but will be excluded from",
        "training by the Category G filter (missing 3+ of 4 key signal fields).",
        "",
        "They are still useful for date coverage audits and basic VP-only analysis.",
        "",
        "---",
        "",
        "## Honest Gap Assessment",
        "",
        f"| Category | Rows | Status |",
        f"|---|---|---|",
        f"| Full Category A (exclusion audit estimate) | {gap['category_a_estimated_rows']} rows / {gap['category_a_estimated_dates']} dates | Documented |",
        f"| Recoverable Phase A (full fidelity) | {pa['races']} | {'Available — execute to recover' if pa['races'] else 'Zero — all VV dates already local'} |",
        f"| Recoverable Phase B (VP only) | {pb['vp_extracted_total']} | Available — training value limited |",
        f"| Unrecoverable | {gap['unrecoverable_estimate']} rows | Pre-04-22 Railway data not in Supabase |",
        "",
        "**Recommendation:**",
        "The pre-April 22 Railway scoring data is not stored in Supabase velo_verdicts.",
        "The 1310-row SIGMA_2K_SAFE_TRAINING_SLICE_V1 is the correct corpus baseline.",
        "Growth path: daily scoring accumulation + Phase A/B recovery if applicable.",
        "",
        "---",
        "",
        "## Next Steps",
        "",
        "1. If Phase A races found: `--execute` to write verdict JSONs + rebuild corpus chain",
        "2. If Phase B only: decide whether partial VP-only rows are worth adding",
        "3. Accept the 1310-row baseline as-is — signals are stable and validated",
        "",
        "---",
        "",
        "## Governance",
        "",
        "No scoring / model / staking / router / Telegram changes.",
        "Recovery audit only. Classification: CORPUS_RECOVERY_AUDIT_ONLY",
        "",
        "*RECOVER_SUPABASE_VERDICTS_TO_LOCAL_V1 — recover_supabase_verdicts_to_local.py*",
    ]
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Recover missing local verdict JSONs from Supabase"
    )
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Report only — no file writes (default when neither flag set)")
    parser.add_argument("--execute", action="store_true", default=False,
                        help="Write verdict JSON files to data/")
    args = parser.parse_args()

    write_files = args.execute and not args.dry_run
    # If neither flag set, default to dry-run
    if not args.execute and not args.dry_run:
        write_files = False

    mode = "EXECUTE" if write_files else "DRY_RUN"
    print(f"RECOVER SUPABASE VERDICTS TO LOCAL — {mode}")
    print("=" * 60)

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    sb = _load_sb()
    local_verdict_map = _local_verdict_date_map()
    local_result_map = _local_result_date_map()
    local_verdict_set = set(local_verdict_map.keys())
    local_result_set = set(local_result_map.keys())

    print(f"\nLocal verdict JSONs: {len(local_verdict_map)} dates")
    print(f"Local result  JSONs: {len(local_result_map)} dates")

    # ── Phase A ───────────────────────────────────────────────────────────────
    print("\n── Phase A: Supabase velo_verdicts recovery ──")
    vv_dates = _fetch_velo_verdicts_dates(sb)
    vv_dates_set = set(vv_dates)
    overlap = vv_dates_set & local_verdict_set
    phase_a_candidates = sorted(vv_dates_set - local_verdict_set)

    print(f"  velo_verdicts dates in Supabase: {len(vv_dates)}")
    print(f"  Already have local JSON: {len(overlap)}")
    print(f"  Phase A candidates (missing locally): {len(phase_a_candidates)}")

    phase_a_details = []
    phase_a_verdict_map: dict[str, list[dict]] = {}
    total_phase_a_races = 0

    for date in phase_a_candidates:
        vlist = _reconstruct_phase_a(sb, date)
        has_results = date in local_result_set
        phase_a_details.append({
            "date": date,
            "races": len(vlist),
            "has_results": has_results,
            "training_safe_estimate": len(vlist) if has_results else 0,
        })
        phase_a_verdict_map[date] = vlist
        total_phase_a_races += len(vlist)
        print(f"  {date}: {len(vlist)} races  results={'YES' if has_results else 'NO'}")

    # ── Phase B ───────────────────────────────────────────────────────────────
    print("\n── Phase B: sigma_audits notes reconstruction ──")
    sigma_all = _fetch_sigma_all(sb)
    sigma_by_date: dict[str, list[dict]] = {}
    for row in sigma_all:
        d = (row.get("date") or "")[:10]
        if d:
            sigma_by_date.setdefault(d, []).append(row)

    sigma_dates_set = set(sigma_by_date.keys())
    # Phase B = sigma date, results exist, NO local verdict JSON
    phase_b_candidates = sorted(
        (sigma_dates_set - local_verdict_set) & local_result_set
    )
    print(f"  sigma dates total: {len(sigma_dates_set)}")
    print(f"  Phase B candidates: {len(phase_b_candidates)}")

    phase_b_details = []
    phase_b_verdict_map: dict[str, list[dict]] = {}
    total_phase_b_extracted = 0

    for date in phase_b_candidates:
        rows = sigma_by_date.get(date, [])
        vlist = _reconstruct_phase_b(rows)
        parseable = sum(1 for r in rows if _parse_notes_vp(r.get("notes"))[0] is not None)
        phase_b_details.append({
            "date": date,
            "sigma_rows": len(rows),
            "parseable": parseable,
            "vp_extracted": len(vlist),
        })
        phase_b_verdict_map[date] = vlist
        total_phase_b_extracted += len(vlist)
        print(f"  {date}: {len(rows)} sigma rows | {parseable} parseable | {len(vlist)} VP extracted")

    # ── Summary ───────────────────────────────────────────────────────────────
    phase_a_training_safe = sum(d["training_safe_estimate"] for d in phase_a_details)
    print(f"\n{'='*60}")
    print(f"RECOVERY SUMMARY ({mode})")
    print(f"  Phase A (full fidelity):   {total_phase_a_races} races / {len(phase_a_candidates)} dates")
    print(f"    → training-safe estimate: {phase_a_training_safe} (requires results file)")
    print(f"  Phase B (VP-only partial): {total_phase_b_extracted} races / {len(phase_b_candidates)} dates")
    print(f"    → WARNING: mds/improvement/place_prob=null → likely Category G")
    print(f"  Unrecoverable: pre-2026-04-22 Railway data not in Supabase velo_verdicts")

    # ── Write files (--execute only) ──────────────────────────────────────────
    files_written = []
    if write_files:
        all_to_write = list(phase_a_verdict_map.items()) + list(phase_b_verdict_map.items())
        for date, vlist in all_to_write:
            if not vlist:
                continue
            date_str = date.replace("-", "_")
            out_path = DATA / f"velo_prime_verdicts_{date_str}.json"
            out_path.write_text(json.dumps(vlist, indent=2, default=str))
            files_written.append(str(out_path))
            print(f"  Written: {out_path}")
        if files_written:
            print(f"\nFiles written: {len(files_written)}")
            print("Next step: python scripts/build_unified_evidence_corpus.py")
        else:
            print("\nNo files written (no recoverable data found).")
    else:
        total_writable = sum(len(v) for v in phase_a_verdict_map.values()) + \
                         sum(len(v) for v in phase_b_verdict_map.values())
        print(f"\nDRY RUN: {total_writable} verdict records would be written across "
              f"{len(phase_a_candidates) + len(phase_b_candidates)} files.")
        print("Run with --execute to write files.")

    # ── Output report ─────────────────────────────────────────────────────────
    report = {
        "run_ts": run_ts,
        "mode": mode,
        "local_verdict_dates": len(local_verdict_map),
        "local_result_dates": len(local_result_map),
        "supabase_vv_dates": len(vv_dates),
        "phase_a": {
            "candidate_dates": len(phase_a_candidates),
            "races": total_phase_a_races,
            "training_safe_estimate": phase_a_training_safe,
            "fidelity": "FULL",
            "details": phase_a_details,
        },
        "phase_b": {
            "candidate_dates": len(phase_b_candidates),
            "vp_extracted_total": total_phase_b_extracted,
            "fidelity": "PARTIAL_VP_ONLY",
            "signal_warning": "mds/improvement/place_prob=null → likely Category G in corpus",
            "details": phase_b_details,
        },
        "files_written": files_written,
        "gap_assessment": {
            "category_a_estimated_rows": 620,
            "category_a_estimated_dates": 30,
            "recoverable_phase_a_full_fidelity": total_phase_a_races,
            "recoverable_phase_b_partial": total_phase_b_extracted,
            "unrecoverable_estimate": 620 - phase_a_training_safe - total_phase_b_extracted,
            "root_cause": "Pre-2026-04-22 Railway scoring did not write to Supabase velo_verdicts. "
                          "Supabase velo_verdicts only available from 2026-04-22 onwards. "
                          "sigma_audits notes contain VP text only, no sidecar signals.",
            "recommendation": "Accept SIGMA_2K_SAFE_TRAINING_SLICE_V1 (1310 rows) as the "
                              "current baseline. Daily scoring accumulation is the growth path. "
                              "Phase B reconstruction adds date coverage but limited training value.",
        },
        "governance": {
            "db_mutation": False,
            "scoring_change": False,
            "model_change": False,
            "staking_change": False,
            "telegram": False,
            "classification": "CORPUS_RECOVERY_AUDIT_ONLY",
        },
    }

    json_path = REPORTS_DIR / "supabase_verdict_recovery_dry_run_latest.json"
    json_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md = _build_md(report)
    md_path = REPORTS_DIR / "supabase_verdict_recovery_dry_run_latest.md"
    md_path.write_text(md)
    print(f"Written: {md_path}")

    return report


if __name__ == "__main__":
    main()
