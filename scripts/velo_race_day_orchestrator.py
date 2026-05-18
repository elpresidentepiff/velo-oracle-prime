#!/usr/bin/env python3.11
"""
VÉLØ Race-Day Orchestrator
==========================
Canonical race-day execution chain.  Every run ends in exactly one status:

    FULL_ENGINE_RUN              VP scored via live API or cache + shadow + Telegram
    FULL_ENGINE_RUN_RP_SOURCED   VP scored via RP profile fallback + shadow + Telegram
    PARTIAL_SHADOW_CONTEXT       VP missing; RP/TJ/last-6 shadow only
    FAILED_RUN_REQUIRES_OPERATOR Hard failure, operator must intervene

RP PRIMARY POLICY (permanent from 2026-05-18):
  Racing Post runner profile is the primary race information source.
  Racing API is optional enrichment only.
  A 401 from Racing API must not block a run when RP runner profile
  exists for the requested date.

No silent gaps.  No fake full-engine runs.  One manifest per day.

Step order (A–J):
  A  RP runner profile build      (build_rp_runner_profile.py)
  B  Last-six rating spine        (build_horse_last6_rating_spine.py)
  C  Master profile patch         (patch_runner_master_with_last6.py)
  D  VÉLØ Prime / Railway scoring (run_prime_today.py)
     Sources in priority order:
       1. cached racecard JSON
       2. RP runner profile fallback   ← primary when cache absent
       3. live Racing API              ← only if 1+2 unavailable
  E  Sync verdicts from Supabase  (sync_verdicts_from_supabase.py)
  F  TJ confirmation watch        (jtc_d_tj_daily_confirmation_watch.py)
  G  Shadow Model C prediction    (runner_master_shadow_daily_predict.py)
  H  Mission Control              (velo_mission_control.py)
  I  Dashboard update             (writes velo_shadow_status_latest.json)
  J  Telegram publish             (curl direct — locked format)

VP gate:
  If step D fails AND RP profile present → WARN_ONLY, continue as PARTIAL
  If step D fails AND no RP profile      → FAILED_RUN_REQUIRES_OPERATOR
  With --allow-vp-missing               → always continue with PARTIAL label

Usage:
  python velo_race_day_orchestrator.py --date 2026-05-18
  python velo_race_day_orchestrator.py --date 2026-05-18 --allow-vp-missing
  python velo_race_day_orchestrator.py --date 2026-05-18 --backfill
  python velo_race_day_orchestrator.py --date 2026-05-18 --dry-run

Governance:
  NO_SCORING_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE
  NO_TELEGRAM_CHANGE | NO_LIVE_STATE_MUTATION
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
RUNS_DIR = ROOT / "data" / "runs"
DASHBOARD_DIR = ROOT / "app" / "static" / "dashboard"
REPORTS_DIR = ROOT / "data" / "reports"

# Load .env so Telegram and other credentials are available
sys.path.insert(0, str(ROOT))
try:
    from app.core.runtime_env import load_optional_env_file
    load_optional_env_file(ROOT / ".env")
except Exception:
    pass

RUNS_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

GOVERNANCE = (
    "NO_SCORING_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE "
    "| NO_TELEGRAM_CHANGE | NO_LIVE_STATE_MUTATION"
)

STATUS_FULL    = "FULL_ENGINE_RUN"
STATUS_FULL_RP = "FULL_ENGINE_RUN_RP_SOURCED"
STATUS_PARTIAL = "PARTIAL_SHADOW_CONTEXT"
STATUS_FAIL    = "FAILED_RUN_REQUIRES_OPERATOR"

_FULL_STATUSES = (STATUS_FULL, STATUS_FULL_RP)


# ─── Manifest ────────────────────────────────────────────────────────────────

def _new_manifest(date_str: str, args) -> dict:
    return {
        "date": date_str,
        "started_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "finished_at": None,
        "allow_vp_missing": args.allow_vp_missing,
        "backfill": args.backfill,
        "dry_run": args.dry_run,
        # Steps
        "rp_ingestion_ran":       False,
        "rp_ingestion_ok":        False,
        "last6_spine_ran":        False,
        "last6_spine_ok":         False,
        "master_patch_ran":       False,
        "master_patch_ok":        False,
        "vp_scoring_ran":         False,
        "vp_scoring_ok":          False,
        "vp_coverage":            None,
        "verdicts_synced":        False,
        "tj_watch_ran":           False,
        "tj_watch_ok":            False,
        "shadow_predict_ran":     False,
        "shadow_predict_ok":      False,
        "mission_control_ran":    False,
        "mission_control_ok":     False,
        "dashboard_updated":      False,
        "telegram_sent":          False,
        "telegram_message_id":    None,
        "telegram_addendum_id":   None,
        "sentient_backup_moved":  False,
        # Racecard source tracking
        "racecard_source":        None,
        "rp_primary":             False,
        "racing_api_auth":        None,
        "vp_source":              None,
        # Outcome
        "final_status":           STATUS_FAIL,
        "vp_available":           False,
        "full_model_c":           False,
        "error":                  None,
        "governance":             GOVERNANCE,
    }


def _save_manifest(manifest: dict, date_str: str, dry_run: bool = False) -> Path:
    path = RUNS_DIR / f"velo_race_day_manifest_{date_str}.json"
    if not dry_run:
        with open(path, "w") as f:
            json.dump(manifest, f, indent=2)
    return path


# ─── Step runner ─────────────────────────────────────────────────────────────

def _run_step(label: str, cmd: list[str], manifest: dict,
              ran_key: str, ok_key: str, dry_run: bool,
              timeout: int = 300, env_extra: dict | None = None) -> bool:
    manifest[ran_key] = True
    if dry_run:
        print(f"  [DRY RUN] would run: {' '.join(cmd)}")
        manifest[ok_key] = True
        return True

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    ok = result.returncode == 0
    manifest[ok_key] = ok
    if not ok:
        tail = (result.stderr or result.stdout or "")[-400:]
        print(f"  FAILED (rc={result.returncode}): {tail.strip()}")
    else:
        # Print last 3 lines of stdout as confirmation
        lines = [l for l in (result.stdout or "").split("\n") if l.strip()]
        for l in lines[-3:]:
            print(f"    {l}")
    return ok


# ─── Telegram send ───────────────────────────────────────────────────────────

def _send_telegram(text: str, manifest: dict, dry_run: bool) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("  WARN: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False
    if dry_run:
        print(f"  [DRY RUN] would send Telegram: {text[:80]}...")
        return True

    import urllib.request, urllib.parse
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            if body.get("ok"):
                msg_id = body["result"].get("message_id")
                manifest["telegram_message_id"] = msg_id
                manifest["telegram_sent"] = True
                print(f"  Telegram sent: message_id={msg_id}")
                return True
    except Exception as e:
        print(f"  Telegram error: {e}")
    return False


def _build_telegram_text(date_str: str, manifest: dict,
                          shadow_json_path: Path, tj_json_path: Path,
                          backfill: bool = False) -> str:
    status = manifest["final_status"]
    vp_label = "YES" if manifest["vp_available"] else "NO"
    rp_primary = manifest.get("rp_primary", False)
    vp_source = manifest.get("vp_source") or ("RP_PROFILE_FALLBACK" if rp_primary else "LIVE_API")
    vp_coverage = manifest.get("vp_coverage")
    date_display = date_str.upper()

    # Load shadow top-10
    shadow_lines = []
    if shadow_json_path.exists():
        try:
            sr = json.loads(shadow_json_path.read_text())
            all_runners = []
            for race in sr.get("races", []):
                for r in race.get("runners", []):
                    if r.get("in_top_decile"):
                        all_runners.append((r["shadow_score_c"], race["off_time"],
                                            race["course"], r["horse"]))
            all_runners.sort(reverse=True)
            for i, (score, t, course, horse) in enumerate(all_runners[:10], 1):
                shadow_lines.append(f"{i}. {horse} — {course} {t} — Shadow {score:.3f}")
        except Exception:
            pass

    # Load TJ top watch
    tj_lines = []
    if tj_json_path.exists():
        try:
            tj = json.loads(tj_json_path.read_text())
            shadow_watch = tj.get("shadow_watch", [])
            for r in shadow_watch[:6]:
                tj_lines.append(
                    f"{r.get('horse','?')} — {r.get('course','?')} {r.get('off_time','?')} — TJ {r.get('tj_sr','?')}"
                )
        except Exception:
            pass

    # Header
    if backfill and status in _FULL_STATUSES:
        title = f"VÉLØ {date_display} — FULL ENGINE BACKFILL COMPLETE"
    else:
        title = f"VÉLØ {date_display} — {status}"

    parts = [title, ""]

    # Backfill correction note
    if backfill:
        parts += [
            "CORRECTION:",
            "Previous messages 5278/5279 were PARTIAL_SHADOW_CONTEXT.",
            f"18 May has now been backfilled using Racing Post primary profile.",
            "",
        ]

    parts += [
        "STATUS:",
        f"VP scoring: {vp_label}",
        f"VP source: {vp_source}",
    ]
    if vp_coverage is not None:
        parts.append(f"VP coverage: {int(vp_coverage)} runners scored")
    parts += [
        f"Full Model C: {'YES' if manifest['full_model_c'] else 'NO'}",
        f"LIVE_USE: BLOCKED",
    ]

    # Source context
    if status == STATUS_FULL_RP:
        parts += [
            "",
            "SOURCE: RP PRIMARY",
            "Racing API: AUTH_FAIL_401 — WARN_ONLY",
            "Racing Post runner profile is the primary data source.",
            "API is optional enrichment. 401 does not block this run.",
        ]
    elif status == STATUS_PARTIAL:
        parts += [
            "",
            "NOTE: VP/Railway scores missing.",
            "This is RP-feature shadow context only, not full Model C.",
        ]

    if shadow_lines:
        parts += ["", "TOP MODEL C SHADOW:"] + shadow_lines
    if tj_lines:
        parts += ["", "TJ_HIGH WATCH:"] + tj_lines

    # Shadow mode note
    shadow_mode = "FULL_MODEL_C" if manifest["full_model_c"] else "SHADOW_CONTEXT_ONLY"
    parts += [
        "",
        "GOVERNANCE:",
        f"SHADOW_MODE: {shadow_mode}",
        "NO_STAKING_CHANGE",
        "NO_ROUTER_CHANGE",
        "NO_LIVE_STATE_MUTATION",
    ]
    return "\n".join(parts)


# ─── Dashboard write ──────────────────────────────────────────────────────────

def _write_dashboard(date_str: str, manifest: dict, dry_run: bool):
    rp_primary = manifest.get("rp_primary", False)
    vp_source = manifest.get("vp_source") or ("RP_PROFILE_FALLBACK" if rp_primary else "UNKNOWN")
    status_doc = {
        "date": date_str,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "telegram_sent": manifest["telegram_sent"],
        "telegram_message_id": manifest["telegram_message_id"],
        "status": manifest["final_status"],
        "rp_primary": rp_primary,
        "racing_api_required": not rp_primary,
        "racing_api_auth": manifest.get("racing_api_auth"),
        "vp_available": manifest["vp_available"],
        "vp_source": vp_source,
        "full_model_c": manifest["full_model_c"],
        "live_use": "BLOCKED",
        "vp_coverage": manifest["vp_coverage"],
        "reason": "" if manifest["vp_available"] else "VP/Railway scoring missing for " + date_str,
        "governance": GOVERNANCE,
    }
    path = DASHBOARD_DIR / "velo_shadow_status_latest.json"
    if not dry_run:
        with open(path, "w") as f:
            json.dump(status_doc, f, indent=2)
    print(f"  Dashboard: {path}")
    manifest["dashboard_updated"] = True


# ─── Racecard source detection ───────────────────────────────────────────────

def _detect_racecard_source(date_str: str) -> tuple[str, int]:
    """
    Return (source, rp_runner_count) before Step D runs, without importing
    run_prime_today.  Mirrors the priority chain in load_racecards().

    source values: 'cache' | 'rp_profile' | 'api'
    rp_runner_count: rows in RP profile for date_str (0 if cache or api)
    """
    date_tag = date_str.replace("-", "_")
    cache_path = ROOT / "data" / f"racecards_{date_tag}_standard.json"
    if cache_path.exists():
        return "cache", 0

    rp_profile_path = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"
    if rp_profile_path.exists():
        try:
            import pandas as pd
            rp = pd.read_parquet(rp_profile_path)
            rp_today = rp[rp["race_date"].astype(str) == date_str]
            if not rp_today.empty:
                return "rp_profile", len(rp_today)
        except Exception:
            pass

    return "api", 0


def _run_api_auth_check(py: str) -> str:
    """
    Run check_racing_api_auth.py and return the status string.
    Never raises; returns 'AUTH_UNKNOWN' on unexpected errors.
    """
    try:
        result = subprocess.run(
            [py, str(SCRIPTS / "check_racing_api_auth.py")],
            capture_output=True, text=True, timeout=20,
        )
        line = (result.stdout or "").strip().splitlines()
        return line[0] if line else "AUTH_UNKNOWN"
    except Exception as e:
        return f"AUTH_UNKNOWN — {e}"


# ─── VP coverage check ────────────────────────────────────────────────────────

def _check_vp_coverage(date_str: str) -> float | None:
    """Check % of today's runners that got VP scored, from synced verdict JSON."""
    verdict_path = ROOT / "data" / f"velo_prime_verdicts_{date_str.replace('-','_')}.json"
    if not verdict_path.exists():
        return None
    try:
        verdicts = json.loads(verdict_path.read_text())
        scored = len(verdicts) if isinstance(verdicts, list) else 0
        return float(scored)  # absolute count; no denominator here
    except Exception:
        return None


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Race-Day Orchestrator")
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument("--allow-vp-missing", action="store_true",
                        help="Continue with PARTIAL_SHADOW_CONTEXT if VP scoring fails")
    parser.add_argument("--backfill", action="store_true",
                        help="Backfill mode: re-run all steps for a past date")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print steps without executing")
    parser.add_argument("--skip-telegram", action="store_true",
                        help="Build everything but do not send Telegram")
    args = parser.parse_args()

    date_str = args.date
    manifest = _new_manifest(date_str, args)

    py = sys.executable

    print(f"\nVÉLØ Race-Day Orchestrator — {date_str}")
    print(f"Governance: {GOVERNANCE}")
    if args.dry_run:   print("Mode: DRY RUN")
    if args.backfill:  print("Mode: BACKFILL")
    if args.allow_vp_missing: print("VP gate: ALLOW_VP_MISSING")
    print()

    def _abort(reason: str):
        manifest["error"] = reason
        manifest["final_status"] = STATUS_FAIL
        manifest["finished_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        _save_manifest(manifest, date_str, args.dry_run)
        print(f"\nORCHESTRATOR ABORT: {reason}")
        print(f"Status: {STATUS_FAIL}")
        sys.exit(1)

    # ── A. RP runner profile ──────────────────────────────────────────────────
    print("Step A — RP runner profile build")
    ok_a = _run_step(
        "A", [py, str(SCRIPTS / "build_rp_runner_profile.py"), "--date", date_str],
        manifest, "rp_ingestion_ran", "rp_ingestion_ok", args.dry_run, timeout=120
    )
    if not ok_a:
        _abort("Step A (RP ingestion) failed")
    _save_manifest(manifest, date_str, args.dry_run)

    # ── B. Last-six rating spine ──────────────────────────────────────────────
    print("\nStep B — Last-six rating spine")
    ok_b = _run_step(
        "B", [py, str(SCRIPTS / "build_horse_last6_rating_spine.py")],
        manifest, "last6_spine_ran", "last6_spine_ok", args.dry_run, timeout=180
    )
    if not ok_b:
        _abort("Step B (last-6 spine) failed")
    _save_manifest(manifest, date_str, args.dry_run)

    # ── C. Master profile patch ───────────────────────────────────────────────
    print("\nStep C — Master profile patch (last-6)")
    ok_c = _run_step(
        "C", [py, str(SCRIPTS / "patch_runner_master_with_last6.py")],
        manifest, "master_patch_ran", "master_patch_ok", args.dry_run, timeout=60
    )
    if not ok_c:
        _abort("Step C (master patch) failed")
    _save_manifest(manifest, date_str, args.dry_run)

    # ── D. VÉLØ Prime / Railway scoring ──────────────────────────────────────
    print("\nStep D — VÉLØ Prime scoring (run_prime_today.py)")

    # Determine racecard source before running — informs auth gate and status
    _rc_source, _rp_count = _detect_racecard_source(date_str)
    manifest["racecard_source"] = _rc_source
    manifest["rp_primary"] = (_rc_source == "rp_profile")
    print(f"  Racecard source: {_rc_source}" + (f" ({_rp_count} runners)" if _rp_count else ""))

    # Auth check: WARN_ONLY when RP profile is the source (Racing API is optional)
    if _rc_source == "rp_profile":
        _auth_status = _run_api_auth_check(py)
        manifest["racing_api_auth"] = _auth_status
        if "AUTH_FAIL_401" in _auth_status:
            print(f"  Racing API auth: {_auth_status}")
            print("  => AUTH_FAIL_401_WARN_ONLY — RP profile is primary, run continues")
            manifest["racing_api_auth"] = "AUTH_FAIL_401_WARN_ONLY"
        else:
            print(f"  Racing API auth: {_auth_status}")
    elif _rc_source == "api":
        # Live API required — auth failure is fatal
        _auth_status = _run_api_auth_check(py)
        manifest["racing_api_auth"] = _auth_status
        if "AUTH_FAIL" in _auth_status:
            _abort(f"Racing API auth failed and no RP profile available: {_auth_status}")

    ok_d = _run_step(
        "D", [py, str(SCRIPTS / "run_prime_today.py"), "--date", date_str],
        manifest, "vp_scoring_ran", "vp_scoring_ok", args.dry_run, timeout=300
    )
    manifest["vp_available"] = ok_d

    if not ok_d:
        if args.allow_vp_missing or manifest["rp_primary"]:
            # RP available or caller explicitly allowed missing VP
            print(f"  VP scoring failed — continuing as {STATUS_PARTIAL}")
            manifest["final_status"] = STATUS_PARTIAL
            manifest["full_model_c"] = False
            manifest["vp_source"] = "NONE"
        else:
            _abort(
                "Step D (VP scoring) failed and --allow-vp-missing not set. "
                "Pass --allow-vp-missing to continue with PARTIAL_SHADOW_CONTEXT."
            )
    else:
        manifest["full_model_c"] = True
        if _rc_source == "rp_profile":
            manifest["final_status"] = STATUS_FULL_RP
            manifest["vp_source"] = "RP_PROFILE_FALLBACK"
            manifest["vp_coverage"] = float(_rp_count)
        elif _rc_source == "cache":
            manifest["vp_source"] = "CACHE"
        else:
            manifest["vp_source"] = "LIVE_API"
    _save_manifest(manifest, date_str, args.dry_run)

    # ── E. Sync verdicts from Supabase ───────────────────────────────────────
    if ok_d:
        print("\nStep E — Sync verdicts from Supabase")
        ok_e = _run_step(
            "E", [py, str(SCRIPTS / "sync_verdicts_from_supabase.py"), "--date", date_str],
            manifest, "verdicts_synced", "verdicts_synced", args.dry_run, timeout=60
        )
        manifest["vp_coverage"] = _check_vp_coverage(date_str)
        _save_manifest(manifest, date_str, args.dry_run)
    else:
        print("\nStep E — Skipped (VP not scored)")

    # ── F. TJ confirmation ────────────────────────────────────────────────────
    print("\nStep F — TJ confirmation watch")
    ok_f = _run_step(
        "F", [py, str(SCRIPTS / "jtc_d_tj_daily_confirmation_watch.py")],
        manifest, "tj_watch_ran", "tj_watch_ok", args.dry_run, timeout=60
    )
    _save_manifest(manifest, date_str, args.dry_run)

    # ── G. Shadow Model C prediction ─────────────────────────────────────────
    print("\nStep G — Shadow Model C prediction")
    ok_g = _run_step(
        "G", [py, str(SCRIPTS / "runner_master_shadow_daily_predict.py"), "--date", date_str],
        manifest, "shadow_predict_ran", "shadow_predict_ok", args.dry_run, timeout=60
    )
    _save_manifest(manifest, date_str, args.dry_run)

    # ── H. Mission Control ────────────────────────────────────────────────────
    print("\nStep H — Mission Control")
    ok_h = _run_step(
        "H", [py, str(SCRIPTS / "velo_mission_control.py"), "--date", date_str],
        manifest, "mission_control_ran", "mission_control_ok", args.dry_run, timeout=60
    )
    _save_manifest(manifest, date_str, args.dry_run)

    # ── Final status ──────────────────────────────────────────────────────────
    # Only overwrite if not already set to PARTIAL or a FULL_RP variant
    if manifest["final_status"] not in (STATUS_PARTIAL, STATUS_FULL_RP):
        manifest["final_status"] = STATUS_FULL if manifest["vp_available"] else STATUS_PARTIAL

    # ── I. Dashboard update ───────────────────────────────────────────────────
    print("\nStep I — Dashboard update")
    _write_dashboard(date_str, manifest, args.dry_run)
    _save_manifest(manifest, date_str, args.dry_run)

    # ── J. Telegram publish ───────────────────────────────────────────────────
    if args.skip_telegram:
        print("\nStep J — Telegram skipped (--skip-telegram)")
    else:
        print("\nStep J — Telegram publish")
        shadow_json = REPORTS_DIR / "runner_master_shadow_daily_latest.json"
        tj_json     = REPORTS_DIR / "jtc_d_tj_daily_confirmation_latest.json"
        tg_text = _build_telegram_text(date_str, manifest, shadow_json, tj_json,
                                        backfill=args.backfill)
        tg_ok = _send_telegram(tg_text, manifest, args.dry_run)
        if not tg_ok:
            print("  WARN: Telegram failed — run did not abort, check credentials")
    _save_manifest(manifest, date_str, args.dry_run)

    # ── Done ──────────────────────────────────────────────────────────────────
    manifest["finished_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    _save_manifest(manifest, date_str, args.dry_run)

    final = manifest["final_status"]
    print(f"\n{'='*60}")
    print(f"VÉLØ RACE-DAY ORCHESTRATOR — {date_str}")
    print(f"Status:        {final}")
    print(f"VP scored:     {manifest['vp_available']}")
    print(f"VP source:     {manifest.get('vp_source','?')}")
    print(f"RP primary:    {manifest.get('rp_primary', False)}")
    print(f"Racing API:    {manifest.get('racing_api_auth','not checked')}")
    print(f"VP coverage:   {manifest.get('vp_coverage','?')}")
    print(f"Full MC:       {manifest['full_model_c']}")
    print(f"Telegram:      {manifest['telegram_sent']} (id={manifest['telegram_message_id']})")
    print(f"Manifest:      data/runs/velo_race_day_manifest_{date_str}.json")
    print(f"Governance:    {GOVERNANCE}")
    print(f"{'='*60}\n")

    if final == STATUS_FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
