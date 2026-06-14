#!/usr/bin/env python3
"""
Backfill Sigma VP Fields
========================
Repairs sigma_results_YYYY_MM_DD.json files that are missing velo_prime_prob
in their per-race rows[] arrays, by cross-referencing same-day verdict artifacts
(data/velo_prime_verdicts_YYYY_MM_DD.json).

Safety: dry-run by default. Pass --execute to write.

Usage:
    python scripts/ops/backfill_sigma_vp.py --start-date 2026-06-07 --end-date 2026-06-13 --dry-run
    python scripts/ops/backfill_sigma_vp.py --start-date 2026-06-07 --end-date 2026-06-13 --execute

Provenance fields written per row:
    velo_prime_prob    : float | null
    vp_source          : source artifact filename | null
    vp_provenance      : LOCAL_VERDICT_JSON | SUPABASE_VELO_VERDICTS | UNRECOVERABLE
    vp_recovered       : true/false
    vp_missing_reason  : null | explicit reason string

HARD RULES — enforced by this script:
    - Never writes to Supabase
    - Never changes sigma aggregate stats (sr, frame_rate, etc.)
    - Always creates backup before writing
    - Never overwrites files without --execute flag
    - Dry-run default
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIGMA_DIR = ROOT / "data" / "sigma_results"
VERDICTS_DIR = ROOT / "data"
BACKUPS_DIR = ROOT / "data" / "sigma_results" / "_backfill_backups"


def _iter_dates(start: str, end: str):
    d = date.fromisoformat(start)
    e = date.fromisoformat(end)
    while d <= e:
        yield d.isoformat()
        d += timedelta(days=1)


def _load_verdict_vp_index(verdict_date: str) -> dict[str, float | None]:
    """
    Load local verdict JSON and return race_id -> velo_prime_prob mapping.
    VP is always in the 'top' sub-object of each verdict row.
    Returns empty dict if file not found.
    """
    key = verdict_date.replace("-", "_")
    path = VERDICTS_DIR / f"velo_prime_verdicts_{key}.json"
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [WARN] Could not read verdict file {path.name}: {exc}")
        return {}
    index: dict[str, float | None] = {}
    for r in rows:
        rid = str(r.get("race_id", ""))
        if not rid:
            continue
        top = r.get("top") or {}
        vpp = top.get("velo_prime_prob")
        if vpp is not None:
            try:
                vpp = float(vpp)
            except (ValueError, TypeError):
                vpp = None
        index[rid] = vpp
    return index


def _verdict_source_name(verdict_date: str) -> str:
    key = verdict_date.replace("-", "_")
    return f"velo_prime_verdicts_{key}.json"


def process_date(sigma_date: str, dry_run: bool) -> dict:
    """
    Process one sigma date. Returns a report dict.
    """
    key = sigma_date.replace("-", "_")
    sigma_path = SIGMA_DIR / f"sigma_results_{key}.json"
    verdict_source = _verdict_source_name(sigma_date)

    report = {
        "date": sigma_date,
        "sigma_file": str(sigma_path),
        "sigma_file_exists": sigma_path.exists(),
        "verdict_source": verdict_source,
        "verdict_source_exists": (VERDICTS_DIR / verdict_source).exists(),
        "rows_scanned": 0,
        "rows_missing_vp": 0,
        "rows_recoverable": 0,
        "rows_unrecoverable": 0,
        "rows_already_have_vp": 0,
        "rows_written": 0,
        "backup_path": None,
        "action": "SKIP_NO_SIGMA_FILE",
        "dry_run": dry_run,
    }

    if not sigma_path.exists():
        return report

    try:
        sigma_data = json.loads(sigma_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report["action"] = f"SKIP_UNREADABLE: {exc}"
        return report

    rows = sigma_data.get("rows", [])

    # If no rows array at all, the artifact is aggregate-only (old format pre-fix).
    # We cannot synthesise rows from aggregate stats alone - those are UNRECOVERABLE
    # unless we can reconstruct from learning events or verdict JSON.
    if not rows:
        # Attempt reconstruction from nightly learning events
        learning_path = ROOT / "data" / f"nightly_eod_learning_events_{key}.jsonl"
        reconstructed = []
        if learning_path.exists():
            try:
                for line in learning_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    evt = json.loads(line)
                    rid = str(evt.get("race_id", ""))
                    snap = evt.get("prediction_snapshot") or {}
                    vpp = snap.get("velo_prime_prob")
                    outcome = "WIN" if evt.get("prediction_result") == "WIN" else (
                        "PLACED" if evt.get("prediction_result") == "PLACED" else "MISS"
                    )
                    miss_class = "n/a" if outcome != "MISS" else "unknown"
                    horse = snap.get("horse", "?")
                    course = ""
                    off = ""
                    actual_name = (evt.get("result_snapshot") or {}).get("winner_id", "?")
                    winner_sp = 0.0
                    try:
                        winner_sp = float((evt.get("result_snapshot") or {}).get("winner_sp") or 0)
                    except (ValueError, TypeError):
                        pass
                    vp_present = vpp is not None
                    reconstructed.append(
                        {
                            "race_id": rid,
                            "course": course,
                            "off": off,
                            "predicted": horse,
                            "actual_name": actual_name,
                            "winner_sp": winner_sp,
                            "velo_prime_prob": float(vpp) if vp_present else None,
                            "vp_source": f"nightly_eod_learning_events_{key}.jsonl" if vp_present else None,
                            "vp_provenance": "NIGHTLY_EOD_LEARNING_EVENTS" if vp_present else "UNRECOVERABLE",
                            "vp_recovered": vp_present,
                            "vp_missing_reason": None if vp_present else "vp_not_in_learning_event",
                            "outcome": outcome,
                            "miss_class": miss_class,
                        }
                    )
            except Exception as exc:
                print(f"  [WARN] Could not parse learning events {learning_path.name}: {exc}")

        if reconstructed:
            report["rows_scanned"] = len(reconstructed)
            report["rows_recoverable"] = sum(1 for r in reconstructed if r["velo_prime_prob"] is not None)
            report["rows_unrecoverable"] = sum(1 for r in reconstructed if r["velo_prime_prob"] is None)
            report["rows_missing_vp"] = report["rows_recoverable"] + report["rows_unrecoverable"]
            report["action"] = "RECONSTRUCT_FROM_LEARNING_EVENTS"

            # Add vp_coverage block
            sigma_data["rows"] = reconstructed
            sigma_data["vp_coverage"] = {
                "total_rows": len(reconstructed),
                "rows_with_vp": report["rows_recoverable"],
                "rows_missing_vp": report["rows_unrecoverable"],
                "vp_source": "nightly_eod_learning_events",
                "backfill_applied": True,
            }

            if not dry_run:
                BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
                backup_path = BACKUPS_DIR / f"sigma_results_{key}_pre_backfill.json"
                shutil.copy2(sigma_path, backup_path)
                report["backup_path"] = str(backup_path)
                sigma_path.write_text(json.dumps(sigma_data, indent=2), encoding="utf-8")
                report["rows_written"] = len(reconstructed)
            else:
                report["rows_written"] = 0
        else:
            # No learning events — try reconstructing from verdict JSON + rp_results
            verdict_index = _load_verdict_vp_index(sigma_date)
            results_path = ROOT / "data" / "results" / f"rp_results_{key}.json"
            verdict_source = _verdict_source_name(sigma_date)

            if verdict_index and results_path.exists():
                # Build race_id -> winner mapping from rp_results
                try:
                    rp_raw = json.loads(results_path.read_text(encoding="utf-8"))
                    result_list = rp_raw.get("results", rp_raw) if isinstance(rp_raw, dict) else rp_raw
                    winner_map: dict[str, dict] = {}
                    for res in result_list:
                        rid = str(res.get("race_id", ""))
                        if rid:
                            winner_map[rid] = {
                                "winner_horse": res.get("winner_horse", ""),
                                "winner_sp": float(res.get("winner_sp") or 0),
                                "course": res.get("course", ""),
                                "off": res.get("off", res.get("race_time_raw", "")),
                            }
                except Exception as exc:
                    print(f"  [WARN] Could not parse rp_results {results_path.name}: {exc}")
                    winner_map = {}

                # Load verdict rows to get horse names
                verd_path = VERDICTS_DIR / verdict_source
                reconstructed = []
                try:
                    verd_rows = json.loads(verd_path.read_text(encoding="utf-8"))
                    for vr in verd_rows:
                        top = vr.get("top", {})
                        rid = str(top.get("race_id") or vr.get("race_id", ""))
                        horse = top.get("horse", "")
                        vpp = top.get("velo_prime_prob")
                        res_info = winner_map.get(rid, {})
                        winner = res_info.get("winner_horse", "")
                        outcome = "WIN" if winner and horse and winner.lower() == horse.lower() else "MISS"
                        miss_class = "n/a" if outcome == "WIN" else "unknown"
                        reconstructed.append({
                            "race_id": rid,
                            "course": res_info.get("course", ""),
                            "off": res_info.get("off", ""),
                            "predicted": horse,
                            "actual_name": winner,
                            "winner_sp": res_info.get("winner_sp", 0.0),
                            "velo_prime_prob": float(vpp) if vpp is not None else None,
                            "vp_source": verdict_source if vpp is not None else None,
                            "vp_provenance": "LOCAL_VERDICT_JSON" if vpp is not None else "UNRECOVERABLE",
                            "vp_recovered": vpp is not None,
                            "vp_missing_reason": None if vpp is not None else "vp_not_in_verdict_json",
                            "outcome": outcome,
                            "miss_class": miss_class,
                        })
                except Exception as exc:
                    print(f"  [WARN] Could not parse verdict file {verdict_source}: {exc}")
                    reconstructed = []

                if reconstructed:
                    report["rows_scanned"] = len(reconstructed)
                    report["rows_recoverable"] = sum(1 for r in reconstructed if r["velo_prime_prob"] is not None)
                    report["rows_unrecoverable"] = sum(1 for r in reconstructed if r["velo_prime_prob"] is None)
                    report["rows_missing_vp"] = len(reconstructed)
                    report["action"] = "RECONSTRUCT_FROM_VERDICT_JSON_AND_RESULTS"
                    sigma_data["rows"] = reconstructed
                    sigma_data["vp_coverage"] = {
                        "total_rows": len(reconstructed),
                        "rows_with_vp": report["rows_recoverable"],
                        "rows_missing_vp": report["rows_unrecoverable"],
                        "vp_source": verdict_source,
                        "backfill_applied": not dry_run,
                    }
                    if not dry_run:
                        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
                        backup_path = BACKUPS_DIR / f"sigma_results_{key}_pre_backfill.json"
                        shutil.copy2(sigma_path, backup_path)
                        report["backup_path"] = str(backup_path)
                        sigma_path.write_text(json.dumps(sigma_data, indent=2), encoding="utf-8")
                        report["rows_written"] = len(reconstructed)
                    else:
                        report["rows_written"] = 0
                    return report

            report["action"] = "UNRECOVERABLE_NO_ROWS_NO_LEARNING_EVENTS"
            report["rows_unrecoverable"] = sigma_data.get("evaluated_count", 0)

        return report

    # We have rows — check VP coverage
    verdict_index = _load_verdict_vp_index(sigma_date)
    modified = False
    rows_already = 0
    rows_missing = 0
    rows_recovered = 0
    rows_unrec = 0

    for row in rows:
        existing_vpp = row.get("velo_prime_prob")
        has_vp = existing_vpp is not None
        has_provenance = "vp_provenance" in row

        if has_vp and has_provenance:
            rows_already += 1
            continue

        if has_vp and not has_provenance:
            # VP present but no provenance fields — add them
            row["vp_source"] = verdict_source if (VERDICTS_DIR / verdict_source).exists() else None
            row["vp_provenance"] = "LOCAL_VERDICT_JSON"
            row["vp_recovered"] = False
            row["vp_missing_reason"] = None
            rows_already += 1
            modified = True
            continue

        rows_missing += 1

        # VP is missing — try to recover from local verdict JSON
        rid = str(row.get("race_id", ""))
        recovered_vpp = verdict_index.get(rid) if rid else None

        if recovered_vpp is not None:
            row["velo_prime_prob"] = recovered_vpp
            row["vp_source"] = verdict_source
            row["vp_provenance"] = "LOCAL_VERDICT_JSON"
            row["vp_recovered"] = True
            row["vp_missing_reason"] = None
            rows_recovered += 1
            modified = True
        else:
            # Not in verdict JSON - check if verdict file exists at all
            verdict_file_exists = (VERDICTS_DIR / verdict_source).exists()
            if not verdict_file_exists:
                reason = "verdict_json_not_found"
            elif rid not in verdict_index:
                reason = "race_id_not_in_verdict_json"
            else:
                reason = "velo_prime_prob_null_in_verdict_json"

            row["velo_prime_prob"] = None
            row["vp_source"] = None
            row["vp_provenance"] = "UNRECOVERABLE"
            row["vp_recovered"] = False
            row["vp_missing_reason"] = reason
            rows_unrec += 1
            modified = True

    report["rows_scanned"] = len(rows)
    report["rows_already_have_vp"] = rows_already
    report["rows_missing_vp"] = rows_missing
    report["rows_recoverable"] = rows_recovered
    report["rows_unrecoverable"] = rows_unrec

    if not modified:
        report["action"] = "NO_CHANGE_NEEDED"
        return report

    # Update vp_coverage block
    total_with_vp = sum(1 for r in rows if r.get("velo_prime_prob") is not None)
    sigma_data["vp_coverage"] = {
        "total_rows": len(rows),
        "rows_with_vp": total_with_vp,
        "rows_missing_vp": len(rows) - total_with_vp,
        "vp_source": verdict_source,
        "backfill_applied": True,
    }

    if dry_run:
        report["action"] = "DRY_RUN_WOULD_WRITE"
        report["rows_written"] = 0
    else:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUPS_DIR / f"sigma_results_{key}_pre_backfill.json"
        shutil.copy2(sigma_path, backup_path)
        report["backup_path"] = str(backup_path)
        sigma_path.write_text(json.dumps(sigma_data, indent=2), encoding="utf-8")
        report["rows_written"] = rows_recovered + rows_unrec
        report["action"] = "EXECUTED"

    return report


def main():
    parser = argparse.ArgumentParser(description="Backfill velo_prime_prob into sigma result artifacts")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report what would change without writing (DEFAULT)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually write repaired files (creates backups first)",
    )
    args = parser.parse_args()

    dry_run = not args.execute  # execute overrides dry_run default

    print(f"\nSIGMA VP BACKFILL {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print("=" * 60)
    print(f"  Date range: {args.start_date} to {args.end_date}")
    print(f"  Mode:       {'DRY-RUN (no files will be changed)' if dry_run else 'EXECUTE (backups will be created first)'}")
    print()

    all_reports = []
    total_scanned = total_missing = total_recoverable = total_unrecoverable = total_written = 0

    for d in _iter_dates(args.start_date, args.end_date):
        print(f"  [{d}] ", end="", flush=True)
        report = process_date(d, dry_run=dry_run)
        all_reports.append(report)

        total_scanned += report["rows_scanned"]
        total_missing += report["rows_missing_vp"]
        total_recoverable += report["rows_recoverable"]
        total_unrecoverable += report["rows_unrecoverable"]
        total_written += report["rows_written"]

        print(
            f"scanned={report['rows_scanned']} "
            f"missing={report['rows_missing_vp']} "
            f"recoverable={report['rows_recoverable']} "
            f"unrecoverable={report['rows_unrecoverable']} "
            f"action={report['action']}"
        )
        if report.get("backup_path"):
            print(f"    backup -> {report['backup_path']}")

    print()
    print("=" * 60)
    print("SUMMARY")
    print(f"  Total rows scanned:      {total_scanned}")
    print(f"  Rows missing VP:         {total_missing}")
    print(f"  Rows recoverable:        {total_recoverable}")
    print(f"  Rows unrecoverable:      {total_unrecoverable}")
    if not dry_run:
        print(f"  Rows written:            {total_written}")
    print()

    if dry_run:
        print("DRY-RUN COMPLETE — no files modified.")
        print("Re-run with --execute to apply repairs (backups created first).")
    else:
        print("EXECUTE COMPLETE — files repaired. Backups in:", str(BACKUPS_DIR))

    # Write machine-readable report
    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    suffix = "dry_run" if dry_run else "executed"
    report_path = report_dir / f"backfill_sigma_vp_{args.start_date}_{args.end_date}_{suffix}.json"
    report_doc = {
        "dry_run": dry_run,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "total_rows_scanned": total_scanned,
        "total_missing_vp": total_missing,
        "total_recoverable": total_recoverable,
        "total_unrecoverable": total_unrecoverable,
        "total_written": total_written,
        "supabase_touched": False,
        "live_scoring_changed": False,
        "model_promotion": False,
        "dates": all_reports,
    }
    report_path.write_text(json.dumps(report_doc, indent=2), encoding="utf-8")
    print(f"\nReport: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
