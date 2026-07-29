#!/usr/bin/env python3
"""
run_full_raceday_eod.py — THE ONE EOD COMMAND

Companion to run_full_raceday.py, which covers the morning half (Steps
1-9.6: capture, RPDC, live scoring, paper intelligence overlays). This
script covers the evening half: capture race results, reconcile
predictions against them (sigma), and run the full learning loop.

This is not a new/competing orchestrator -- it codifies the exact command
sequence that was run BY HAND, successfully, twice this week
(2026-07-24), reusing every existing proven component unchanged. See
THE_ONE_TRUTH.md Steps 10A-20 and docs/current/ONE_TRUTH.md's Step 12B
(run_multimodel_sigma.py) for the documented reference sequence this
mirrors.

SAFETY NOTE (learned the hard way, 2026-07-24): unlike the morning
overlays in run_full_raceday.py (which silently degrade if rerun after
results exist), every step in THIS script is naturally post-results and
proven idempotent-safe to rerun on the same date -- sigma/ledger writes
dedupe by (date, race_id) or equivalent keys, and
nightly_eod_learning_runner.py explicitly reports PASS_IDEMPOTENT on a
second run. Still: no step here should be assumed safe against a NEW,
unfamiliar date without checking its own idempotence story first.

Usage:
    PYTHONPATH=. python scripts/ops/run_full_raceday_eod.py --date 2026-07-24 --execute
    PYTHONPATH=. python scripts/ops/run_full_raceday_eod.py --date 2026-07-24 --execute --skip-results-capture
        (use --skip-results-capture if data/results/rp_results_{date}.json already exists
        and only the sigma/learning chain needs to run)

No live staking. No model training. No promotion.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
FIREFOX_PROFILE = ROOT / "data" / "browser_profiles" / "racing_post_account_firefox"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(label: str, cmd: list[str], *, critical: bool, results: list[dict]) -> bool:
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    print("  $ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT), env={"PYTHONPATH": "."} | os.environ.copy())
    ok = proc.returncode == 0
    results.append({"step": label, "cmd": cmd, "returncode": proc.returncode, "ok": ok, "critical": critical})
    if not ok:
        print(f"  [{'CRITICAL FAIL' if critical else 'NON-CRITICAL FAIL'}] {label} exited {proc.returncode}")
        if critical:
            print("\nSTOPPING — critical step failed. Fix and rerun (safe to resume with --skip-results-capture if results are already captured).")
    return ok


def run_capture_stdout(label: str, cmd: list[str], out_path: Path, *, critical: bool, results: list[dict]) -> bool:
    """Same as run(), but for steps that only print to stdout and need their
    output redirected to a file (vp30_operator_card.py does not write its
    own output file -- this matches the manual `> file.md` redirect used
    when this sequence was run by hand this week)."""
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    print("  $ " + " ".join(cmd) + f" > {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, cwd=str(ROOT), env={"PYTHONPATH": "."} | os.environ.copy(), stdout=f, stderr=subprocess.STDOUT)
    ok = proc.returncode == 0
    results.append({"step": label, "cmd": cmd, "returncode": proc.returncode, "ok": ok, "critical": critical})
    if not ok:
        print(f"  [{'CRITICAL FAIL' if critical else 'NON-CRITICAL FAIL'}] {label} exited {proc.returncode}")
        if critical:
            print("\nSTOPPING — critical step failed.")
    return ok


def rp_session_healthy() -> bool:
    try:
        sys.path.insert(0, str(ROOT))
        from scripts.ops.check_rp_session_health import probe
        result = probe(FIREFOX_PROFILE, timeout_s=15)
        return result["status"] == "PASS"
    except Exception as e:
        print(f"  [WARN] Session health probe itself failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--execute", action="store_true", required=True, help="Required — this runs real captures, sigma, and learning writes.")
    parser.add_argument("--skip-results-capture", action="store_true", help="Skip results capture (assumes data/results/rp_results_{date}.json already exists)")
    args = parser.parse_args()

    date = args.date
    date_tag = date.replace("-", "_")
    results: list[dict] = []

    print(f"RUN_FULL_RACEDAY_EOD — {date} — started {_utc_now()}")

    results_path = ROOT / "data" / "results" / f"rp_results_{date_tag}.json"

    # ── Steps 10A-11: capture and parse race results ─────────────────────
    if args.skip_results_capture or results_path.exists():
        print(f"\n[SKIP] Results capture — {results_path} already exists.")
    else:
        print("\nPre-flight: RP session health check...")
        if not rp_session_healthy():
            print(
                "\n[BLOCKED] RP browser session is not logged in. Live capture will fail.\n"
                "Fix: interactively run\n"
                f"  python scripts/ops/racing_post_account_collector.py init-login "
                f"--profile-dir {FIREFOX_PROFILE} --execute --wait-seconds 90\n"
                "then rerun this script. Aborting before wasting a capture attempt."
            )
            return 1
        print("  [OK] Session logged in.")

        if not run(
            "Step 10A: Build RP results URL list",
            [PY, "scripts/ops/build_rp_results_url_list.py", "--date", date, "--execute"],
            critical=True, results=results,
        ):
            return 1

        url_list = ROOT / "data" / "racing_post_url_lists" / f"rp_results_{date}.txt"
        if not run(
            "Step 10B: Capture race result pages",
            [PY, "scripts/ops/racing_post_account_collector.py", "capture",
             "--url-list", str(url_list), "--date", f"rp-results-{date}",
             "--profile-dir", str(FIREFOX_PROFILE), "--execute"],
            critical=True, results=results,
        ):
            return 1

        if not run(
            "Step 11: Parse race result captures",
            [PY, "scripts/ops/parse_rp_results_capture.py",
             "--date", date, "--capture-date", f"rp-results-{date}", "--execute"],
            critical=True, results=results,
        ):
            return 1

    # ── Step 12: reconcile predictions vs results (sigma) ────────────────
    if not run(
        "Step 12: Results + sigma reconciliation",
        [PY, "scripts/ops/run_results_sigma.py", "--date", date, "--source", "cache"],
        critical=True, results=results,
    ):
        return 1

    # ── Step 12B: multi-model sigma (Old VELO / No-RPR / New Build / Champion) ──
    run(
        "Step 12B: Multi-model sigma",
        [PY, "scripts/ops/run_multimodel_sigma.py", "--date", date, "--execute"],
        critical=False, results=results,
    )

    # ── Step 13: write run history (feeds tomorrow's RPDC) ───────────────
    run(
        "Step 13: Ingest results to horse runs",
        [PY, "scripts/ops/ingest_results_to_horse_runs.py", "--date", date],
        critical=False, results=results,
    )

    # ── Step 14: rebuild sigma retrieval corpus ───────────────────────────
    # dump_sigma_audits.py refreshes data/sigma_audits_dump.json from
    # Supabase first -- build_sigma_retrieval_corpus.py's freshness gate
    # rejects a stale dump (root-caused 2026-07-24: the corpus builder
    # silently used a 6-day-stale local dump and failed its own
    # --require-through-date check until this was run first).
    run(
        "Step 14a: Refresh sigma audits dump",
        [PY, "scripts/ops/dump_sigma_audits.py"],
        critical=False, results=results,
    )
    run(
        "Step 14b: Rebuild sigma retrieval corpus",
        [PY, "scripts/ops/build_sigma_retrieval_corpus.py", "--require-through-date", date],
        critical=False, results=results,
    )

    # ── Step 15: refresh Mission Control gate status ──────────────────────
    run(
        "Step 15: Update Mission Control",
        [PY, "scripts/ops/update_mission_control.py", "--date", date],
        critical=False, results=results,
    )

    # ── Step 16a: VP30 operator card ──────────────────────────────────────
    run_capture_stdout(
        "Step 16a: VP30 operator card",
        [PY, "scripts/audit/vp30_operator_card.py", "--date", date],
        ROOT / "data" / f"vp30_operator_card_{date}.md",
        critical=False, results=results,
    )

    # ── Step 16b: LLM Council tribunal ────────────────────────────────────
    run(
        "Step 16b: VELO Council",
        [PY, "scripts/audit/run_velo_council.py", "--date", date],
        critical=False, results=results,
    )

    # ── Step 16c: LLM end-of-day report (2026-07-29) ─────────────────────
    # DeepSeek-powered, ARCHIVE_CONTEXT_ONLY. Reads sigma + ledger + council
    # + trainer-intent + mission control. Skips cleanly (exit 0) when
    # DEEPSEEK_API_KEY is not set in .env; non-critical either way.
    run(
        "Step 16c: LLM End-of-Day Report",
        [PY, "scripts/ops/run_llm_intel_brief.py", "--date", date, "--mode", "eod"],
        critical=False, results=results,
    )

    # ── Step 16d: Mission Control FINAL refresh (2026-07-29) ─────────────
    # Step 15 runs before the council (16b), so its MC write carries
    # YESTERDAY'S council verdict — on 2026-07-29 this made Step 20's gate
    # pre-flight read a stale BLOCKED while tonight's council said
    # PASS_TO_LEARNING. ONE_TRUTH's DAY COMPLETE definition requires a
    # final Council + Mission Control refresh; this is it.
    run(
        "Step 16d: Mission Control final refresh (post-council)",
        [PY, "scripts/ops/update_mission_control.py", "--date", date],
        critical=False, results=results,
    )

    # ── Step 17: paper execution bridge close (SIM only) ──────────────────
    run(
        "Step 17: Execution bridge shadow (paper close)",
        [PY, "scripts/ops/run_execution_bridge_shadow.py", "--date", date, "--mode", "SIM", "--audit-results"],
        critical=False, results=results,
    )

    # ── Step 18: verdict-result dedup for router dataset ──────────────────
    run(
        "Step 18: Build innovation protocol",
        [PY, "scripts/ops/build_innovation_protocol.py", "--date", date],
        critical=False, results=results,
    )

    # ── Step 19: router lane evidence accumulation ─────────────────────────
    run(
        "Step 19: Router shadow audit",
        [PY, "scripts/ops/router_shadow_audit.py", "--prev-csv", "data/router_shadow_audit_latest.csv"],
        critical=False, results=results,
    )

    # ── Step 20: Playbook G sentient loopback ──────────────────────────────
    run(
        "Step 20: Nightly EOD learning runner",
        [PY, "scripts/ops/nightly_eod_learning_runner.py", "--date", date],
        critical=False, results=results,
    )

    # ── Step 20B: VCP-03 coherence burn-in log ─────────────────────────────
    # Wired 2026-07-28 — was never in daily pipeline, causing 26 missed days
    # (stuck at 2/10 since 2026-07-01). Script is idempotent: skips if today
    # already logged. Reads velo_heartbeat_latest.json + velo_living_state.json.
    run(
        "Step 20B: VCP-03 coherence burn-in log",
        [PY, "scripts/ops/build_vcp03_burn_in_log.py"],
        critical=False, results=results,
    )

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*70}\nRUN_FULL_RACEDAY_EOD SUMMARY — {date}\n{'='*70}")
    n_ok = sum(1 for r in results if r["ok"])
    n_fail = sum(1 for r in results if not r["ok"])
    for r in results:
        status = "PASS" if r["ok"] else ("FAIL(critical)" if r["critical"] else "FAIL(non-critical)")
        print(f"  [{status:>18}] {r['step']}")
    print(f"\n  {n_ok} passed, {n_fail} failed out of {len(results)} steps.")

    report_path = ROOT / "data" / "reports" / f"run_full_raceday_eod_{date_tag}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"date": date, "generated_at": _utc_now(), "results": results}, indent=2), encoding="utf-8")
    print(f"  Report: {report_path}")

    return 0 if all(r["ok"] or not r["critical"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
