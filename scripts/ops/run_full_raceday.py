#!/usr/bin/env python3
"""
run_full_raceday.py — THE ONE COMMAND

Runs THE_ONE_TRUTH.md Steps 1-9.6 in sequence: live RP racecard capture,
parse/validate, RPDC, live scoring, then every Steps 9.1-9.6 paper
intelligence overlay, New Build, and Champion Intent Shadow. This is the
standing daily contract, codified into one script instead of an operator
(or Claude) manually invoking 15 separate commands and often skipping most
of them -- which is why New Build/Champion Intent/RPDC sat empty on
2026-07-08 despite Old VELO scoring cleanly.

Run this FIRST THING in the morning, before racing starts. RP's live
racecards index drops a course from the listing once its whole card has
finished (confirmed 2026-07-08: Catterick/Yarmouth vanished from the index
by mid-afternoon), so running this late in the day permanently loses
New Build/Champion Intent/RPDC coverage for any course that's already
finished -- there is no way to recover it after the fact.

Idempotent on Step 9: if today's velo_verdicts already exist in Supabase,
scoring is skipped (never overwrites/rescoring a live day) and only the
paper-intelligence/New Build/Champion Intent layers are (re)built.

Usage:
    PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py --date 2026-07-08 --execute
    PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py --date 2026-07-08 --execute --skip-capture

USE venv/bin/python, NOT bare `python` (corrected 2026-08-02). Steps are spawned
with sys.executable, so the launching interpreter is the one the capture steps
get. The venv's Playwright bundles firefox-1532, which owns the RP browser
profile; the system python's bundles firefox-1522, which refuses that profile
("last used with a newer version of this application"). The session probe
surfaces that as a plain FAIL, so a wrong-interpreter launch is indistinguishable
from a logged-out session.
        (use --skip-capture if a racecard/injection already exists for the date
        and only the downstream chain needs to run)

No Telegram send from this script itself (each sub-step uses --no-notify
where it exists). No live staking. No model training. No promotion.
"""
from __future__ import annotations

import argparse
import json
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
    proc = subprocess.run(cmd, cwd=str(ROOT), env={"PYTHONPATH": "."} | __import__("os").environ.copy())
    ok = proc.returncode == 0
    results.append({"step": label, "cmd": cmd, "returncode": proc.returncode, "ok": ok, "critical": critical})
    if not ok:
        print(f"  [{'CRITICAL FAIL' if critical else 'NON-CRITICAL FAIL'}] {label} exited {proc.returncode}")
        if critical:
            print("\nSTOPPING — critical step failed. Fix and rerun (safe to resume with --skip-capture if capture already succeeded).")
    return ok


class IdempotenceCheckError(RuntimeError):
    """The already-scored check could not be completed and must block the run."""


def verdicts_already_persisted(date: str) -> bool:
    """True if a completed, PASS-status "velo-prime-scoring" pipeline_runs row already
    exists for this date -- i.e. today has already been scored and must not be rescored.

    Queries pipeline_runs (source_date/run_state/status), not velo_verdicts.race_id --
    real RP race_ids are plain numeric (e.g. 924613) and do not encode the date, so the
    previous `race_id LIKE '%YYYYMMDD%'` check almost never matched real data (confirmed
    mechanism behind the 2026-07-15 double-scoring overwrite; salvaged 2026-07-29 from
    fix/canonical-daily-run-p0-gaps bb35c69). pipeline_runs is the same table
    run_prime_today.py's own _open_pipeline_run()/_close_pipeline_run() already write to
    for this exact service_name, so this reuses existing, proven state.

    Raises IdempotenceCheckError instead of returning a guess when the check cannot be
    completed. A broken idempotence check must block the run, not silently permit a
    second scoring pass for a date that may already be scored.
    """
    from dotenv import load_dotenv
    load_dotenv(str(ROOT / ".env"))
    import os
    from supabase import create_client

    try:
        sb = create_client(
            os.environ["SUPABASE_URL"],
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY"),
        )
    except Exception as e:
        raise IdempotenceCheckError(
            f"Could not connect to Supabase to check prior scoring state for {date}: {e}"
        ) from e

    try:
        r = (
            sb.table("pipeline_runs")
            .select("id", count="exact")
            .eq("service_name", "velo-prime-scoring")
            .eq("source_date", date)
            .eq("run_state", "completed")
            .eq("status", "PASS")
            .execute()
        )
    except Exception as e:
        raise IdempotenceCheckError(
            f"Could not query pipeline_runs to check prior scoring state for {date}: {e}"
        ) from e

    return (r.count or 0) > 0


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--execute", action="store_true", required=True, help="Required — this runs real captures and scoring.")
    parser.add_argument("--skip-capture", action="store_true", help="Skip Steps 1-3 (assumes racecard_injection.json already exists for --date)")
    parser.add_argument(
        "--allow-missing-pdfs",
        action="store_true",
        help="Bypass the PDF-ingestion half of the scoring readiness gate (passport check is never overridable).",
    )
    args = parser.parse_args()

    date = args.date
    results: list[dict] = []

    print(f"RUN_FULL_RACEDAY — {date} — started {_utc_now()}")

    # ── Pre-flight: RP session health ────────────────────────────────────
    if not args.skip_capture:
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

    # ── Steps 1-3: live racecard capture ─────────────────────────────────
    if not args.skip_capture:
        if not run(
            "Step 1: Capture racecard index (headless — gets ALL UK venues)",
            [PY, "scripts/ops/capture_index_headless.py", "--date", date],
            critical=True, results=results,
        ):
            return 1

        if not run(
            "Step 2: Build racecard URL list",
            [PY, "scripts/ops/build_racing_post_racecard_url_list.py",
             "--date", date, "--target-date", date, "--execute"],
            critical=True, results=results,
        ):
            return 1

        url_list = ROOT / "data" / "racing_post_url_lists" / f"rp_racecards_{date}.txt"
        n_urls = len([l for l in url_list.read_text().splitlines() if l.strip()]) if url_list.exists() else 0
        print(f"\n  {n_urls} racecard URLs to capture.")
        if n_urls == 0:
            print("  [WARN] 0 URLs found — either no UK/IRE racing today or the index capture was empty. Stopping.")
            return 1

        if not run(
            "Step 3: Capture individual racecard pages",
            [PY, "scripts/ops/racing_post_account_collector.py", "capture",
             "--date", date, "--url-list", str(url_list), "--profile-dir", str(FIREFOX_PROFILE),
             "--delay-seconds", "1.5", "--execute", "--batch-size", "0"],
            critical=True, results=results,
        ):
            return 1

        # ── Step 3.5: supplementary capture of the "_intl" URL list ──────
        # build_racing_post_racecard_url_list.py classifies each venue slug
        # into UK/IRE vs international via a hand-maintained allowlist
        # (UK_IRE_VENUES). That allowlist has twice been caught missing a
        # genuine UK/IRE course (Dundalk-AW on 2026-07-12, Newton Abbot on
        # 2026-07-13), silently dropping the entire course from the day's
        # card until an operator noticed and manually recovered it.
        #
        # The permanent fix is architectural, not just patching the
        # allowlist: capture every race RP shows for the date regardless
        # of that classification, and let the real per-race jurisdiction
        # data (parsed from each race's own RP page payload, resolved by
        # normalize_race()/_resolve_jurisdiction() in
        # workers/racing_api_normalizer.py at Step 2b of
        # run_prime_today.py) decide inclusion. That check is independent
        # of the venue-name allowlist and already correctly excludes
        # genuinely non-UK/IRE cards (e.g. Deauville, Sha Tin) using each
        # race's actual country field, so capturing the intl list here
        # costs a handful of extra page fetches for races that get
        # correctly filtered out downstream, in exchange for never again
        # silently losing a genuine UK/IRE course to an incomplete list.
        intl_url_list = ROOT / "data" / "racing_post_url_lists" / f"rp_racecards_{date}_intl.txt"
        n_intl_urls = (
            len([l for l in intl_url_list.read_text().splitlines() if l.strip()])
            if intl_url_list.exists() else 0
        )
        if n_intl_urls:
            print(f"\n  {n_intl_urls} supplementary (intl-classified) racecard URLs to capture.")
            run(
                "Step 3.5: Capture supplementary intl-classified racecard pages",
                [PY, "scripts/ops/racing_post_account_collector.py", "capture",
                 "--date", date, "--url-list", str(intl_url_list), "--profile-dir", str(FIREFOX_PROFILE),
                 "--delay-seconds", "1.5", "--execute", "--batch-size", "0"],
                critical=False, results=results,
            )
        else:
            print("\n  0 supplementary intl-classified racecard URLs — nothing to capture.")

    # ── Step 4-5: parse + validate ───────────────────────────────────────
    if not run(
        "Step 4: Parse racecard captures",
        [PY, "scripts/ops/parse_racing_post_racecard_capture.py",
         "--date", date, "--capture-label", date, "--write-standard-cache", "--execute"],
        critical=True, results=results,
    ):
        return 1

    injection_path = ROOT / "data" / "racing_post_account_parsed" / date / "racecard_injection.json"
    if not run(
        "Step 5: Validate injection",
        [PY, "scripts/ops/validate_rp_injection.py", "--injection-path", str(injection_path)],
        critical=True, results=results,
    ):
        return 1

    # ── Step 5.1: Backfill Supabase races metadata table ──────────────────
    # `races` (course/time/race_name) was only ever written by the old
    # Racing API ingestion worker, decommissioned 2026-05-14. Nothing
    # replaced it for the RP pipeline, so the table silently stopped
    # getting new rows on 2026-05-06 -- every dashboard publish since then
    # joined verdicts to `races` by race_id and got nothing back, showing
    # blank course/time/race_name for every runner, every day, undetected
    # until 2026-07-26. This step closes that gap permanently.
    run(
        "Step 5.1: Backfill races metadata table",
        [PY, "scripts/ops/backfill_races_table.py", "--date", date, "--execute"],
        critical=False, results=results,
    )

    # ── Step 5.5: Build racecard_merged from injection ───────────────────
    # Required before Step 9 -- run_prime_today.py --source rp reads
    # data/racecard_merged/racecard_*_{date}.json. This step was missing
    # from the chain, which caused Step 9 to fail with "no RP merged files
    # found" on every unattended run (root-caused 2026-07-10 -- Step 9 ran
    # at 09:26 UTC and crashed; the merged files weren't written until
    # 09:27-09:28 by a manual rerun of this exact command).
    if not run(
        "Step 5.5: Build racecard_merged from injection",
        [PY, "scripts/ops/build_racecard_merged_from_injection.py",
         "--date", date, "--injection-path", str(injection_path)],
        critical=True, results=results,
    ):
        return 1

    # ── Step 6: New Build current-card feed ──────────────────────────────
    standard_cache = ROOT / "data" / f"racecards_{date.replace('-', '_')}_standard.json"
    run(
        "Step 6: New Build current-card feed",
        [PY, "scripts/ops/new_build_current_card_feed.py",
         "--racecard-path", str(standard_cache), "--execute"],
        critical=False, results=results,
    )

    # ── Step 8.5: RPDC ────────────────────────────────────────────────────
    run(
        "Step 8.5: RPDC daily",
        [PY, "scripts/ops/build_rpdc_daily.py", "--date", date],
        critical=False, results=results,
    )

    # ── Auto-ingest RP ratings-sheet PDFs from the inbox (2026-07-30) ─────
    # The 07:00 run self-blocked at the readiness gate every single automated
    # morning (2026-07-24/25/30) purely because the six sheets per venue were
    # copied and ingested by hand. This discovers them by venue+date from the
    # operator's inbox folder and ingests them. Non-critical by design: if the
    # sheets are not downloaded yet, the gate below still blocks — this step
    # only removes the manual copy/ingest work, it does not weaken the gate.
    run("Auto-ingest RP PDFs from inbox",
        [PY, "scripts/ops/auto_ingest_pdf_inbox.py", "--date", date, "--execute"],
        critical=False, results=results)

    # ── SCORING READINESS GATE — hard law, added 2026-07-18 ──────────────
    # Nothing past this point runs until (1) the New Build passport feed
    # exists for this date and (2) every GB/IRE venue racing today has RP
    # PDF ratings-sheet enrichment merged into its racecard_merged file.
    # Origin: this exact daily failure repeated -- scoring and the full
    # downstream report chain ran before PDFs landed, forcing a manual
    # re-run of 6+ reports every time PDFs arrived late, and repeatedly
    # opened the door to phantom-race/ID-mismatch bugs (2026-07-17 Hamilton
    # incident). --allow-missing-pdfs bypasses check (2) only, for venues
    # that genuinely never get RP PDFs; passport is never overridable.
    from scripts.ops.check_scoring_readiness_gate import (
        check_passport, check_passport_coverage, check_pdf_ingestion, format_coverage_line,
    )

    print(f"\n{'='*70}\nSCORING READINESS GATE\n{'='*70}")
    passport_ok, passport_msg = check_passport(date)
    print(f"  Passport:       {'OK   ' if passport_ok else 'FAIL '} {passport_msg}")
    # PHASE D (2026-08-02) — passport PRESENCE passed every day while real
    # coverage sat at 45-63%, because the feed emits a row per runner whether
    # or not a passport was found. Report the number every day, warn-only.
    _cov_ok, _cov_stats = check_passport_coverage(date)
    for _i, _line in enumerate(format_coverage_line(_cov_stats)):
        print(f"  Passport cover: {_line}" if _i == 0 else f"  {_line}")
    # PDF ingestion is a WARNING, not a blocker (operator ruling 2026-08-02).
    #
    # It blocked whole days that were otherwise complete. On 2026-08-02 live
    # capture succeeded (27 races, 267 runners, all PASS) and the passport feed
    # built fine at 548K, but zero PDFs had been dropped in the inbox, so the
    # gate stopped the day entirely -- no verdicts, no reports, nothing. Same on
    # 07-24, 07-25, 07-30, 07-31.
    #
    # The ordering argument is what settles it. Of the three inputs, only live
    # capture is perishable -- RP drops a course from its index once that course
    # finishes racing. The passport feed is DERIVED from that capture (Step 6
    # reads racecards_{date}_standard.json), so it cannot precede it. PDFs are
    # the one input that is not perishable at all: the same six sheets ingest
    # identically at 07:00 or at midnight. Blocking the perishable-critical path
    # on the one non-perishable input is backwards -- late PDFs are recoverable
    # by re-ingesting and re-running the merge; a missed capture never is.
    #
    # Per this file's own model/data-source table, PDF sheets are "optional,
    # additive context only" for Old VELO and No-RPR, and New Build / Champion
    # Intent / RPDC need the live capture rather than the sheets. So a PDF-less
    # day still scores every model; it loses postdata_score and
    # or_compression_score, which thins the High-Conviction PDF panel and Deep
    # Race Agent.
    #
    # The passport check below stays HARD and non-overridable: it is what stops
    # New Build, Champion Intent and RPDC scoring against an empty passport bank
    # and silently emitting garbage lanes.
    if args.allow_missing_pdfs:
        pdf_ok, ok_venues, missing_venues = True, [], []
        print("  PDF ingestion:  SKIP  --allow-missing-pdfs set")
    else:
        pdf_ok, ok_venues, missing_venues = check_pdf_ingestion(date)
        print(f"  PDF ingestion:  {'OK   ' if pdf_ok else 'WARN '} ingested={ok_venues or []} missing={missing_venues or []}")
        if not pdf_ok:
            print(
                "  [WARN] Scoring proceeds without PDF enrichment for the venues above.\n"
                "         Old VELO/No-RPR lose postdata_score + or_compression_score;\n"
                "         New Build / Champion Intent / RPDC are unaffected (they need\n"
                "         live capture, not sheets). Drop the sheets in and re-run\n"
                "         auto_ingest_pdf_inbox.py + the merge to enrich this date later."
            )
    if not passport_ok:
        print(
            "\n[BLOCKED] Passport feed missing or empty — no scoring, no downstream reports.\n"
            "  This check is not overridable: New Build, Champion Intent and RPDC would\n"
            "  otherwise score against an empty passport bank and emit silent garbage."
        )
        return 1

    # ── Step 9: live scoring (idempotent — never overwrite an already-scored day) ──
    try:
        already_scored = verdicts_already_persisted(date)
    except IdempotenceCheckError as e:
        print(f"\n[CRITICAL] Idempotence check failed — refusing to risk a double scoring pass: {e}")
        return 1
    if already_scored:
        print(f"\n[SKIP] Step 9: {date} already scored (completed PASS pipeline_runs row) — not re-scoring/overwriting.")
    else:
        if not run(
            "Step 9: Live scoring (run_prime_today.py)",
            [PY, "scripts/ops/run_prime_today.py", "--date", date, "--source", "rp", "--no-notify"]
            + (["--allow-missing-pdfs"] if args.allow_missing_pdfs else []),
            critical=True, results=results,
        ):
            return 1

    # ── Steps 9.1-9.6: paper intelligence overlays ───────────────────────
    # The four core models (Old VELO, New Build, No-RPR/SQPE Shadow, Champion
    # Intent Shadow) are critical=True: they must score every day without
    # fail, together, as one atomic run. A silent failure in any of these is
    # a FAILED day, not a partial pass (hard law, added 2026-07-18).
    if not run("Step 9.1: Radical Shadow (No-RPR)",
        [PY, "scripts/ops/run_radical_shadow_today.py", "--date", date], critical=True, results=results):
        return 1
    # Mid-Price Specialist shadow lane (2026-07-29): paper-only, non-critical —
    # a new lane must never block the day. Feeds mp_* ledger columns via Step 12B.
    run("Step 9.1b: Mid-Price Specialist Shadow",
        [PY, "scripts/ops/run_midprice_shadow_today.py", "--date", date], critical=False, results=results)
    run("Step 9.2: Tri-Lane Stress Test",
        [PY, "scripts/ops/run_tri_lane_stress_test.py", "--date", date, "--ruleset", "v2"], critical=False, results=results)
    tri_lane_json = ROOT / "data" / "reports" / f"tri_lane_stress_test_{date.replace('-', '_')}_v2.json"
    run("Step 9.3: Tri-Lane Agent Review",
        [PY, "scripts/ops/build_tri_lane_agent_review.py", "--packet", str(tri_lane_json)], critical=False, results=results)
    pdf_dir = ROOT / "data" / "incoming_pdfs" / date
    run("Step 9.4: Deep Race Agent V1",
        [PY, "scripts/ops/build_deep_race_agent_v1.py", "--date", date, "--downloads", str(pdf_dir)], critical=False, results=results)
    run("Step 9.5: Course Master",
        [PY, "scripts/ops/build_course_master.py", "--date", date], critical=False, results=results)
    if not run("Step 9.6: Old VELO Three-Option Card",
        [PY, "scripts/ops/build_old_velo_three_option_card.py", "--date", date], critical=True, results=results):
        return 1

    # ── New Build two-lane + Champion Intent Shadow ──────────────────────
    if not run("New Build: Two-Lane Score",
        [PY, "scripts/ops/new_build_two_lane_score.py", "--date", date, "--execute"], critical=True, results=results):
        return 1
    run("Champion Intent: Features",
        [PY, "scripts/ops/build_current_card_intent_features.py",
         "--standard-cache", str(standard_cache), "--date", date, "--execute"], critical=False, results=results)
    if not run("Champion Intent: Shadow Scorecard",
        [PY, "scripts/ops/build_intent_shadow_scorecard.py", "--date", date, "--execute"], critical=True, results=results):
        return 1

    # ── New Build Policy V1 (paper scorer + decision policy) ──────────────
    # Was entirely manual before 2026-07-26: paper_scorer.py called
    # model.predict_proba() on a raw lightgbm.basic.Booster (no such method,
    # crashed every time) and never wrote the per-date file
    # new_build_decision_policy_run.py needs, so NEW_BUILD_POLICY_V1 had no
    # input for any date. Both fixed same day; wiring in so it runs with
    # everything else instead of needing a manual run each day.
    run("New Build: Paper Score Today",
        [PY, "scripts/ops/new_build_paper_score_today.py", "--execute",
         "--racecard-path", str(standard_cache)], critical=False, results=results)
    run("New Build: Decision Policy V1",
        [PY, "scripts/ops/new_build_decision_policy_run.py", "--date", date], critical=False, results=results)

    # ── Canonical model scorecard: build + persist (all four models measured
    # every day -- New Build and Champion Intent were previously producing
    # real predictions that were never persisted to the canonical join Sigma
    # reads from, showing as n/a forever. Added 2026-07-16. ──────────────────
    canonical_csv = ROOT / "data" / "reports" / f"canonical_model_scorecard_{date.replace('-', '_')}.csv"
    run("Canonical Model Scorecard: Build",
        [PY, "scripts/ops/build_canonical_model_scorecard.py", "--date", date], critical=False, results=results)
    run("Canonical Model Scorecard: Persist",
        [PY, "scripts/ops/persist_canonical_model_scorecard.py", "--date", date, "--csv", str(canonical_csv), "--execute"],
        critical=False, results=results)

    # ── Sidecar Stack Operator Card ──────────────────────────────────────
    # Added 2026-07-18: this was only ever run via the separate
    # velo_daily_harness.py orchestrator, not run_full_raceday.py, so the
    # dashboard's sidecar_stack_latest.json silently went 11 days stale
    # (last generated 2026-07-07) while every other panel refreshed daily.
    run("Sidecar Stack Operator Card",
        [PY, "scripts/audit/sidecar_stack_operator_card.py", "--date", date], critical=False, results=results)

    # ── LLM morning suggestions brief (2026-07-29) ───────────────────────
    # DeepSeek-powered, ARCHIVE_CONTEXT_ONLY. Skips cleanly (exit 0) when
    # DEEPSEEK_API_KEY is not set in .env; non-critical either way.
    run("LLM Morning Suggestions Brief",
        [PY, "scripts/ops/run_llm_intel_brief.py", "--date", date, "--mode", "suggestions"],
        critical=False, results=results)

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*70}\nRUN_FULL_RACEDAY SUMMARY — {date}\n{'='*70}")
    n_ok = sum(1 for r in results if r["ok"])
    n_fail = sum(1 for r in results if not r["ok"])
    for r in results:
        status = "PASS" if r["ok"] else ("FAIL(critical)" if r["critical"] else "FAIL(non-critical)")
        print(f"  [{status:>18}] {r['step']}")
    print(f"\n  {n_ok} passed, {n_fail} failed out of {len(results)} steps.")

    report_path = ROOT / "data" / "reports" / f"run_full_raceday_{date.replace('-', '_')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"date": date, "generated_at": _utc_now(), "results": results}, indent=2), encoding="utf-8")
    print(f"  Report: {report_path}")

    return 0 if all(r["ok"] or not r["critical"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
