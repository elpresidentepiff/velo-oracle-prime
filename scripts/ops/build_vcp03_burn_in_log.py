"""
VCP-03 — Daily burn-in log updater.

Reads data/reports/velo_heartbeat_latest.json and data/current/velo_living_state.json.
Checks pass criteria and appends a day record to the burn-in log.
REPORT_ONLY — no scoring, no Supabase, no model changes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_HEARTBEAT_JSON = _REPO_ROOT / "data" / "reports" / "velo_heartbeat_latest.json"
_LIVING_STATE = _REPO_ROOT / "data" / "current" / "velo_living_state.json"
_LOG_JSON = _REPO_ROOT / "data" / "reports" / "vcp_03_burn_in_log.json"
_LOG_MD = _REPO_ROOT / "data" / "reports" / "vcp_03_burn_in_log.md"
_BRIEF = _REPO_ROOT / "data" / "reports" / "vcp_03_operator_brief.md"
_TARGET_DAYS = 10


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _check_day(hb: dict | None, ls: dict | None) -> tuple[str, list[str], list[str]]:
    """Returns (PASS|FAIL, passed_checks, failed_checks)."""
    passed: list[str] = []
    failed: list[str] = []

    def ok(label: str) -> None:
        passed.append(label)

    def fail(label: str) -> None:
        failed.append(label)

    # Living state and heartbeat existence
    if ls is not None:
        ok("living_state_generated")
    else:
        fail("living_state_generated — file missing or unreadable")

    if hb is not None and hb.get("heartbeat_version") == "velo_heartbeat_v1":
        ok("heartbeat_generated")
    else:
        fail("heartbeat_generated — file missing or wrong version")

    if hb is None:
        return "FAIL", passed, failed

    s = hb.get("sections", {})
    sys_s = s.get("system_status", {})
    vfu = s.get("vfu_status", {})
    a3 = s.get("a3_going_code", {})
    lr = s.get("learning_routes", {})
    contra = s.get("contradictions", {})
    fa = s.get("forbidden_actions", [])

    # Truth lock
    if sys_s.get("truth_lock") == "LOCKED":
        ok("truth_lock=LOCKED")
    else:
        fail(f"truth_lock={sys_s.get('truth_lock', 'MISSING')} (need LOCKED)")

    # A-3
    if a3.get("status") == "FIXED":
        ok("a3_going_code=FIXED")
    else:
        fail(f"a3_going_code={a3.get('status', 'MISSING')} (need FIXED)")

    # VFU-20
    if vfu.get("signed_off") is True:
        ok("vfu_20_signed_off=True")
    else:
        fail("vfu_20_signed_off not True")

    # VFU-21
    if vfu.get("vfu_21_gate") == "CLOSED":
        ok("vfu_21_gate=CLOSED")
    else:
        fail(f"vfu_21_gate={vfu.get('vfu_21_gate', 'MISSING')} (need CLOSED)")

    # Learning routes
    if lr.get("memory_capture") == "OPEN":
        ok("memory_capture=OPEN")
    else:
        fail(f"memory_capture={lr.get('memory_capture', 'MISSING')} (need OPEN)")

    if lr.get("failure_learning") == "OPEN":
        ok("failure_learning=OPEN")
    else:
        fail(f"failure_learning={lr.get('failure_learning', 'MISSING')} (need OPEN)")

    promo = lr.get("promotion_learning", "")
    if promo in ("GATED", "ELIGIBLE"):
        ok(f"promotion_learning={promo} (labelled)")
    else:
        fail(f"promotion_learning={promo!r} (need GATED or ELIGIBLE)")

    # Contradictions counted
    if "count" in contra and isinstance(contra.get("items"), list):
        ok("contradictions_counted")
    else:
        fail("contradictions block malformed")

    # Forbidden actions present
    required_fa = {"NO_LIVE_SCORING_CHANGE", "NO_MODEL_PROMOTION", "NO_SUPABASE_WRITES", "NO_TELEGRAM_SEND", "NO_VFU_21_START"}
    if required_fa.issubset(set(fa)):
        ok("forbidden_actions_present")
    else:
        missing = required_fa - set(fa)
        fail(f"forbidden_actions missing: {missing}")

    verdict = "PASS" if not failed else "FAIL"
    return verdict, passed, failed


def _load_log() -> dict:
    existing = _read_json(_LOG_JSON)
    if existing and isinstance(existing.get("days"), list):
        return existing
    return {
        "burn_in_version": "vcp_03_v1",
        "target_days": _TARGET_DAYS,
        "started": "2026-06-29",
        "days": [],
    }


def _write_md(log: dict) -> None:
    days = log.get("days", [])
    passing = [d for d in days if d["verdict"] == "PASS"]
    total = len(days)
    target = log.get("target_days", _TARGET_DAYS)
    status = "COMPLETE" if len(passing) >= target else "IN PROGRESS"

    lines = [
        "# VCP-03 — Coherence Burn-In Log",
        f"**Status:** {status} | **Passing days:** {len(passing)}/{target} | **Days logged:** {total}",
        "",
        "| Day | Date | Verdict | Promotion | Contradictions | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for i, d in enumerate(days, 1):
        verdict = d["verdict"]
        badge = "✓" if verdict == "PASS" else "✗"
        fails = d.get("failed_checks", [])
        notes = "; ".join(fails) if fails else "—"
        promo = d.get("promotion_learning", "UNKNOWN")
        contra = d.get("contradictions_count", 0)
        lines.append(f"| {i} | {d['date']} | {badge} {verdict} | {promo} | {contra} | {notes} |")

    if not days:
        lines.append("| — | — | no days logged yet | — | — | — |")

    lines += [
        "",
        "---",
        "REPORT_ONLY — VCP-03 is burn-in discipline, not a scoring change.",
    ]
    _LOG_MD.write_text("\n".join(lines), encoding="utf-8")


def _write_brief(log: dict) -> None:
    days = log.get("days", [])
    passing = [d for d in days if d["verdict"] == "PASS"]
    target = log.get("target_days", _TARGET_DAYS)
    remaining = max(0, target - len(passing))

    lines = [
        "# VCP-03 — Coherence Burn-In — Operator Brief",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        f"- Passing days: **{len(passing)}/{target}**",
        f"- Days remaining: **{remaining}**",
        f"- Total days logged: {len(days)}",
        "",
        "## Final Classifications",
        "- VCP_03_BURN_IN_PROTOCOL_DOCUMENTED",
        "- TEN_DAY_COHERENCE_BURN_IN_STARTED",
        "- HEARTBEAT_DAILY_COMMAND_PAIR_LOCKED",
        "- LIVING_STATE_DAILY_COMMAND_PAIR_LOCKED",
        "- PROMOTION_LEARNING_CAN_BE_GATED_AND_VALID",
        "- MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN",
        "- CONTRADICTIONS_RECORDED_NOT_SUPPRESSED",
        "- NO_VFU_21_START",
        "- NO_CASE_MEMORY_BUILD",
        "- NO_DEEPSEARCHER_BUILD",
        "- NO_MODEL_PROMOTION",
        "- NO_LIVE_SCORING_CHANGE",
        "- NO_SUPABASE_WRITES",
        "- NO_TELEGRAM_SEND",
        "- REPORT_ONLY",
        "",
        "---",
        "STOP — operator reviews burn-in log after 10 passing days before VCP-04.",
    ]
    _BRIEF.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"── VCP-03: Burn-In Log — {today} ──")

    hb = _read_json(_HEARTBEAT_JSON)
    ls = _read_json(_LIVING_STATE)
    verdict, passed, failed = _check_day(hb, ls)

    log = _load_log()

    # Avoid double-logging the same date
    existing_dates = {d["date"] for d in log["days"]}
    if today in existing_dates:
        print(f"  INFO  {today} already logged — skipping append")
    else:
        s = (hb or {}).get("sections", {})
        log["days"].append({
            "date": today,
            "verdict": verdict,
            "passed_checks": passed,
            "failed_checks": failed,
            "promotion_learning": s.get("learning_routes", {}).get("promotion_learning", "UNKNOWN"),
            "contradictions_count": s.get("contradictions", {}).get("count", 0),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        })

    _LOG_JSON.write_text(json.dumps(log, indent=2), encoding="utf-8")
    _write_md(log)
    _write_brief(log)

    passing = [d for d in log["days"] if d["verdict"] == "PASS"]
    total = len(log["days"])
    target = log["target_days"]

    print(f"  {verdict:4}  {today}")
    if failed:
        for f in failed:
            print(f"        ✗ {f}")
    print(f"  OK   data/reports/vcp_03_burn_in_log.json ({total} days, {len(passing)}/{target} passing)")
    print(f"  OK   data/reports/vcp_03_burn_in_log.md")
    print(f"  OK   data/reports/vcp_03_operator_brief.md")
    print()
    if len(passing) >= target:
        print("  ██  BURN-IN COMPLETE — 10 passing days reached. Operator review before VCP-04.")
    else:
        print(f"  ··  Burn-in progress: {len(passing)}/{target} passing days. {target - len(passing)} remaining.")
    print()
    print("── VCP-03 DONE ──")


if __name__ == "__main__":
    main()
