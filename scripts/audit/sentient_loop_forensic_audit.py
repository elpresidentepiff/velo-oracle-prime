"""
sentient_loop_forensic_audit.py

VÉLØ SENTIENT LOOP FORENSIC AUDIT — Priority 1 diagnostic.

Verifies end-to-end loop integrity for each race day:
  Step 1: PREDICTION CREATED  — sigma study exists, races scored
  Step 2: RESULT RECONCILED   — sigma winners found, verdict present
  Step 3: OUTCOME INGESTED    — EOD bridge ran, events in shadow ledger
  Step 4: STATE MUTATED       — live sentient state races_observed incremented
  Step 5: BACKUP PERSISTED    — dated backup file exists
  Step 6: STATE LOADED OK     — next day's run loaded correct races_observed

Cross-cutting checks:
  HFS TRUTH: MPI and chaos_bloom populated in shadow events (not null/zero)
  GATE STATUS: HFS_TRAINING_SAFE, learning_allowed, live_state_touched
  TRAINING ARTIFACT: exists at different race count than live state?
  LIVE LEARNING PATH: connected or disconnected?

Outputs:
  data/sentient_loop_forensic_audit_latest.json
  data/sentient_loop_forensic_audit_latest.md

Hard rules:
  - Read-only. No scoring changes. No model changes. No Telegram. No staking.
  - No live state writes. No Supabase writes.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT  = Path(__file__).resolve().parents[1]
DATA  = ROOT / "data"
OUT_JSON = DATA / "sentient_loop_forensic_audit_latest.json"
OUT_MD   = DATA / "sentient_loop_forensic_audit_latest.md"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except Exception:
                pass
    return events


def _check(value: bool, label: str) -> dict:
    return {"label": label, "pass": value}


# ─── Data loaders ─────────────────────────────────────────────────────────────

def _load_sigma_studies() -> dict[str, dict]:
    """Load all eod_sigma_study_YYYYMMDD.json files."""
    out = {}
    for f in DATA.glob("eod_sigma_study_*.json"):
        m = re.search(r"(\d{8})", f.name)
        if m:
            date_str = m.group(1)  # YYYYMMDD
            iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            d = _load_json(f)
            if d:
                out[iso] = d
    return out


def _load_nightly_audits() -> dict[str, dict]:
    """Load all playbook_g_nightly_audit_YYYY_MM_DD.json files."""
    out = {}
    for f in DATA.glob("playbook_g_nightly_audit_*.json"):
        m = re.search(r"(\d{4}[-_]\d{2}[-_]\d{2})", f.name)
        if m:
            iso = m.group(1).replace("_", "-")
            d = _load_json(f)
            if d:
                out[iso] = d
    return out


def _load_shadow_critiques() -> dict[str, dict]:
    """Load all eod_playbook_g_shadow_critique_YYYYMMDD.json files."""
    out = {}
    for f in DATA.glob("eod_playbook_g_shadow_critique_*.json"):
        m = re.search(r"(\d{8})", f.name)
        if m:
            date_str = m.group(1)
            iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            d = _load_json(f)
            if d:
                out[iso] = d
    return out


def _load_sentient_backups() -> dict[str, dict]:
    """Load all sentient_state_backup_YYYYMMDD.json files (not training artifact)."""
    out = {}
    for f in DATA.glob("sentient_state_backup_????????.json"):
        m = re.search(r"backup_(\d{8})", f.name)
        if m:
            date_str = m.group(1)
            iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            d = _load_json(f)
            if d:
                out[iso] = d
    return out


# ─── Step audits ──────────────────────────────────────────────────────────────

def audit_step1_prediction(date: str, sigma: dict | None) -> dict:
    """Step 1: Were predictions created and scored?"""
    if sigma is None:
        return {
            "pass": False,
            "detail": "NO_SIGMA_STUDY — sigma study file missing for this date",
            "races_studied": 0,
            "predictions_matched": 0,
        }
    races = sigma.get("races_studied", 0)
    preds = sigma.get("predictions_matched", 0)
    ok = races > 0 and preds > 0
    return {
        "pass": ok,
        "detail": "OK" if ok else f"WEAK — races_studied={races} predictions_matched={preds}",
        "races_studied": races,
        "predictions_matched": preds,
    }


def audit_step2_reconcile(date: str, sigma: dict | None) -> dict:
    """Step 2: Were results matched and a sigma verdict issued?"""
    if sigma is None:
        return {"pass": False, "detail": "NO_SIGMA_STUDY", "winners_found": 0, "verdict": None}
    winners = sigma.get("winners_found", 0)
    verdict = sigma.get("sigma_verdict")
    ok = winners is not None and verdict is not None
    return {
        "pass": ok,
        "detail": "OK" if ok else f"MISSING — winners_found={winners} verdict={verdict}",
        "winners_found": winners,
        "verdict": verdict,
        "strike_rate": sigma.get("strike_rate"),
        "calibration_error": sigma.get("calibration_error"),
    }


def audit_step3_ingestion(date: str, nightly: dict | None, shadow_critique: dict | None) -> dict:
    """Step 3: Were outcomes ingested into the EOD shadow bridge?"""
    if nightly is None and shadow_critique is None:
        return {
            "pass": False,
            "detail": "NO_NIGHTLY_AUDIT — EOD bridge not run for this date",
            "events_read": 0,
            "events_learning_allowed": 0,
            "duplicates_skipped": 0,
            "live_state_touched": False,
        }

    # Prefer nightly audit (more detailed) over shadow critique
    src = nightly if nightly else shadow_critique
    events_read = src.get("events_read", src.get("events_studied", 0))
    learning_true = src.get("events_learning_allowed_true", 0)
    duplicates = src.get("events_skipped_duplicate", src.get("duplicates_skipped", 0))
    live_touched = src.get("live_state_touched", False)

    all_dupes = events_read > 0 and duplicates == events_read
    bridge_ran = events_read > 0

    detail = []
    if not bridge_ran:
        detail.append(f"BRIDGE_NOT_RUN — events_read={events_read}")
    elif all_dupes:
        detail.append(f"ALL_DUPLICATES — {duplicates}/{events_read} events already processed")
    else:
        detail.append(f"events_read={events_read} learning_allowed={learning_true} dupes={duplicates}")

    if live_touched:
        detail.append("live_state_touched=TRUE (unexpected)")
    else:
        detail.append("live_state_protected=OK")

    return {
        "pass": bridge_ran,
        "detail": " | ".join(detail),
        "events_read": events_read,
        "events_learning_allowed": learning_true,
        "duplicates_skipped": duplicates,
        "live_state_touched": live_touched,
        "all_duplicates": all_dupes,
    }


def audit_step4_mutation(
    date: str,
    backups: dict[str, dict],
    live_state: dict,
    live_state_date: str,
) -> dict:
    """Step 4: Did the live sentient state actually mutate (races_observed increment)?"""
    backup = backups.get(date)
    live_races = live_state.get("total_races_observed", 0)
    live_updated = live_state.get("last_updated", "")[:10]

    if backup is None:
        # No backup for this date — check if live state was updated on this date
        if live_updated == date:
            return {
                "pass": True,
                "detail": f"LIVE_STATE_UPDATED — last_updated matches {date}, backup not separately found",
                "races_at_date": live_races,
                "races_delta": None,
            }
        return {
            "pass": False,
            "detail": f"NO_BACKUP — no sentient_state_backup_{date.replace('-','')} found",
            "races_at_date": None,
            "races_delta": None,
        }

    backup_races = backup.get("total_races_observed", 0)
    backup_updated = backup.get("last_updated", "")[:10]

    # Find the previous backup for delta
    all_dates = sorted(backups.keys())
    idx = all_dates.index(date) if date in all_dates else -1
    prev_races = None
    if idx > 0:
        prev_date = all_dates[idx - 1]
        prev_races = backups[prev_date].get("total_races_observed", 0)

    delta = (backup_races - prev_races) if prev_races is not None else None
    mutated = delta is not None and delta > 0

    return {
        "pass": mutated,
        "detail": (
            f"races={backup_races} Δ={delta:+d} vs prev_backup"
            if delta is not None
            else f"races={backup_races} (no previous backup to delta against)"
        ),
        "races_at_date": backup_races,
        "races_delta": delta,
        "backup_last_updated": backup_updated,
    }


def audit_step5_backup(date: str, backups: dict[str, dict]) -> dict:
    """Step 5: Was a dated backup file written?"""
    key = date
    exists = key in backups
    path = DATA / f"sentient_state_backup_{date.replace('-','')}.json"
    return {
        "pass": exists,
        "detail": f"BACKUP_EXISTS — {path.name}" if exists else f"MISSING — {path.name} not found",
        "backup_path": str(path) if exists else None,
    }


def audit_step6_load(date: str, backups: dict[str, dict], nightly_audits: dict[str, dict]) -> dict:
    """Step 6: Did the next day's scoring run load the correct state?"""
    # The next day should show the same or more races than this day's backup
    all_dates = sorted(backups.keys())
    idx = all_dates.index(date) if date in all_dates else -1
    if idx < 0 or idx >= len(all_dates) - 1:
        # No next backup to verify against — check server log instead
        return {
            "pass": None,  # None = UNKNOWN (no evidence either way)
            "detail": "UNKNOWN — no subsequent backup to verify load against",
            "next_date": None,
            "next_races": None,
        }

    next_date = all_dates[idx + 1]
    next_backup = backups[next_date]
    this_backup = backups[date]
    next_races = next_backup.get("total_races_observed", 0)
    this_races = this_backup.get("total_races_observed", 0)

    # Next backup must have >= this backup's count (state carries forward)
    loaded_ok = next_races >= this_races
    return {
        "pass": loaded_ok,
        "detail": (
            f"CONTINUITY_OK — {date} races={this_races} → {next_date} races={next_races}"
            if loaded_ok
            else f"CONTINUITY_BREAK — {date} races={this_races} → {next_date} races={next_races} (REGRESSION)"
        ),
        "next_date": next_date,
        "next_races": next_races,
    }


# ─── HFS truth audit ──────────────────────────────────────────────────────────

def audit_hfs_truth(shadow_events: list[dict], live_state: dict) -> dict:
    """Check whether MPI and chaos_bloom are populated in shadow events."""
    total = len(shadow_events)
    mpi_populated    = sum(1 for e in shadow_events if e.get("mpi") not in (None, 0, ""))
    chaos_populated  = sum(1 for e in shadow_events if e.get("chaos_bloom") not in (None, 0, ""))
    learning_allowed = sum(1 for e in shadow_events if e.get("learning_allowed") is True)

    # Check live state HFS fields (if they exist)
    live_aggression = live_state.get("appetite_state", {}).get("aggression_level", "?")
    live_races      = live_state.get("total_races_observed", 0)
    live_updated    = live_state.get("last_updated", "?")[:10]

    mpi_ok   = mpi_populated > 0
    chaos_ok = chaos_populated > 0

    issues = []
    if not mpi_ok:
        issues.append("MPI_NULL — mpi not being passed to shadow events (Playbook G learning blind)")
    if not chaos_ok:
        issues.append("CHAOS_NULL — chaos_bloom not being passed to shadow events")
    if learning_allowed == 0 and total > 0:
        issues.append("LEARNING_NEVER_ALLOWED — learning_allowed=False on all shadow events (gate locked)")

    return {
        "total_shadow_events":     total,
        "mpi_populated":           mpi_populated,
        "mpi_pct":                 round(mpi_populated / total * 100, 1) if total else 0,
        "mpi_ok":                  mpi_ok,
        "chaos_populated":         chaos_populated,
        "chaos_pct":               round(chaos_populated / total * 100, 1) if total else 0,
        "chaos_ok":                chaos_ok,
        "learning_allowed_events": learning_allowed,
        "live_state_last_updated": live_updated,
        "live_state_races":        live_races,
        "live_state_aggression":   live_aggression,
        "issues":                  issues,
        "verdict":                 "FAIL" if issues else "PASS",
    }


# ─── Live learning path audit ─────────────────────────────────────────────────

def audit_live_learning_path() -> dict:
    """Verify whether live learning is connected or disconnected."""
    loop_status = _load_json(DATA / "velo_learning_loop_status_v1.json") or {}
    real_report = _load_json(DATA / "real_velo_loop_shadow_report_v1.json") or {}

    components  = loop_status.get("components", {})
    blockers    = loop_status.get("blockers", [])
    gates       = loop_status.get("safety_gates", {})

    live_connected = components.get("adapter_to_live_state") == "CONNECTED"
    hfs_training_safe = gates.get("hfs_training_safe", False)
    learning_allowed  = gates.get("learning_allowed_default", False)

    # From real loop report
    real_live_unchanged = real_report.get("live_sentient_state_unchanged", None)
    real_learning_true  = real_report.get("real_events_learning_allowed_true_count", 0)

    # Training artifact vs live state divergence
    live_state = _load_json(DATA / "sentient_state.json") or {}
    training_artifact = _load_json(DATA / "sentient_state_training_artifact_20260502.json") or {}

    live_races     = live_state.get("total_races_observed", 0)
    artifact_races = training_artifact.get("total_races_observed", 0)
    artifact_diverged = artifact_races > live_races

    findings = []
    if not live_connected:
        findings.append("LIVE_LEARNING_DISCONNECTED — adapter_to_live_state not CONNECTED")
    if not hfs_training_safe:
        findings.append("HFS_TRAINING_SAFE=False — gate blocking all live learning promotion")
    if not learning_allowed:
        findings.append("LEARNING_ALLOWED_DEFAULT=False — all events arrive with learning_allowed=False")
    if real_live_unchanged is True:
        findings.append("REAL_LOOP_REPORT confirms live_sentient_state_unchanged=True")
    if real_learning_true == 0:
        findings.append("REAL_LOOP_REPORT: real_events_learning_allowed_true_count=0")
    if artifact_diverged:
        findings.append(
            f"TRAINING_ARTIFACT_UNPROMOTED — artifact races={artifact_races} vs live races={live_races} "
            f"(delta={artifact_races - live_races:+d})"
        )

    verdict = "DISCONNECTED" if not live_connected else (
        "GATED_BLOCKED" if not hfs_training_safe else "CONNECTED"
    )

    return {
        "live_learning_verdict":      verdict,
        "adapter_to_live_state":      components.get("adapter_to_live_state", "UNKNOWN"),
        "hfs_training_safe":          hfs_training_safe,
        "learning_allowed_default":   learning_allowed,
        "live_races":                 live_races,
        "live_state_last_updated":    live_state.get("last_updated", "?")[:10],
        "training_artifact_races":    artifact_races,
        "training_artifact_diverged": artifact_diverged,
        "blockers":                   blockers,
        "findings":                   findings,
    }


# ─── Per-day audit ────────────────────────────────────────────────────────────

def audit_day(
    date: str,
    sigma_studies: dict,
    nightly_audits: dict,
    shadow_critiques: dict,
    backups: dict,
    live_state: dict,
    live_state_date: str,
) -> dict:
    sigma    = sigma_studies.get(date)
    nightly  = nightly_audits.get(date)
    critique = shadow_critiques.get(date)

    s1 = audit_step1_prediction(date, sigma)
    s2 = audit_step2_reconcile(date, sigma)
    s3 = audit_step3_ingestion(date, nightly, critique)
    s4 = audit_step4_mutation(date, backups, live_state, live_state_date)
    s5 = audit_step5_backup(date, backups)
    s6 = audit_step6_load(date, backups, nightly_audits)

    steps = [s1, s2, s3, s4, s5, s6]
    # Count definitive passes/fails (None = unknown)
    fails = [s for s in steps if s["pass"] is False]
    unknowns = [s for s in steps if s["pass"] is None]

    if fails:
        day_verdict = "FAIL"
    elif unknowns:
        day_verdict = "PARTIAL"
    else:
        day_verdict = "PASS"

    failure_modes = []
    if not s1["pass"]:
        failure_modes.append("NO_PREDICTIONS")
    if not s2["pass"]:
        failure_modes.append("NO_RESULTS")
    if s3["pass"] and s3.get("all_duplicates"):
        failure_modes.append("ALL_INGESTION_DUPLICATES")
    elif not s3["pass"]:
        failure_modes.append("INGESTION_MISSING")
    if not s4["pass"]:
        failure_modes.append("STATE_NOT_MUTATED")
    if not s5["pass"]:
        failure_modes.append("BACKUP_MISSING")
    if s6["pass"] is False:
        failure_modes.append("STATE_CONTINUITY_BREAK")

    return {
        "date":          date,
        "verdict":       day_verdict,
        "failure_modes": failure_modes,
        "steps": {
            "step1_prediction": s1,
            "step2_reconcile":  s2,
            "step3_ingestion":  s3,
            "step4_mutation":   s4,
            "step5_backup":     s5,
            "step6_load":       s6,
        },
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("VÉLØ SENTIENT LOOP FORENSIC AUDIT")
    print("=" * 60)

    # Load all data sources
    sigma_studies   = _load_sigma_studies()
    nightly_audits  = _load_nightly_audits()
    shadow_critiques= _load_shadow_critiques()
    backups         = _load_sentient_backups()
    live_state      = _load_json(DATA / "sentient_state.json") or {}
    shadow_events   = _load_jsonl(DATA / "playbook_g_outcome_events_shadow.jsonl")

    live_state_date = (live_state.get("last_updated") or "")[:10]

    print(f"Sigma studies:     {len(sigma_studies)} days")
    print(f"Nightly audits:    {len(nightly_audits)} days")
    print(f"Shadow critiques:  {len(shadow_critiques)} days")
    print(f"State backups:     {len(backups)} dated files")
    print(f"Shadow events:     {len(shadow_events)} entries in JSONL")
    print(f"Live state:        races={live_state.get('total_races_observed','?')} last_updated={live_state_date}")

    # All known dates = union of all sources
    all_dates = sorted(
        set(sigma_studies) | set(nightly_audits) | set(shadow_critiques) | set(backups)
    )
    print(f"Known dates:       {len(all_dates)} total ({all_dates[0]} to {all_dates[-1]})")
    print()

    # Per-day audits
    day_results = []
    for date in all_dates:
        result = audit_day(
            date, sigma_studies, nightly_audits, shadow_critiques,
            backups, live_state, live_state_date,
        )
        day_results.append(result)
        verdict_sym = {"PASS": "✓", "FAIL": "✗", "PARTIAL": "~"}.get(result["verdict"], "?")
        modes = " | ".join(result["failure_modes"]) if result["failure_modes"] else "—"
        print(f"  {verdict_sym} {date}  {result['verdict']}  {modes}")

    # HFS truth audit
    print()
    print("HFS TRUTH AUDIT")
    hfs_result = audit_hfs_truth(shadow_events, live_state)
    print(f"  Shadow events: {hfs_result['total_shadow_events']}")
    print(f"  MPI populated: {hfs_result['mpi_populated']} ({hfs_result['mpi_pct']}%) → {'OK' if hfs_result['mpi_ok'] else 'FAIL'}")
    print(f"  Chaos populated: {hfs_result['chaos_populated']} ({hfs_result['chaos_pct']}%) → {'OK' if hfs_result['chaos_ok'] else 'FAIL'}")
    print(f"  Learning allowed events: {hfs_result['learning_allowed_events']}")
    for issue in hfs_result["issues"]:
        print(f"  ⚠  {issue}")

    # Live learning path audit
    print()
    print("LIVE LEARNING PATH AUDIT")
    live_result = audit_live_learning_path()
    print(f"  Verdict: {live_result['live_learning_verdict']}")
    for f in live_result["findings"]:
        print(f"  ⚠  {f}")

    # Summary stats
    pass_days    = sum(1 for r in day_results if r["verdict"] == "PASS")
    fail_days    = sum(1 for r in day_results if r["verdict"] == "FAIL")
    partial_days = sum(1 for r in day_results if r["verdict"] == "PARTIAL")
    total_days   = len(day_results)

    # Most common failure modes
    all_modes: dict[str, int] = {}
    for r in day_results:
        for m in r["failure_modes"]:
            all_modes[m] = all_modes.get(m, 0) + 1

    # Overall verdict
    if hfs_result["verdict"] == "FAIL" or live_result["live_learning_verdict"] == "DISCONNECTED":
        overall = "LOOP_BROKEN"
    elif fail_days > total_days * 0.5:
        overall = "LOOP_DEGRADED"
    elif fail_days > 0 or hfs_result["verdict"] == "FAIL":
        overall = "LOOP_PARTIAL"
    else:
        overall = "LOOP_HEALTHY"

    print()
    print(f"OVERALL: {overall}")
    print(f"  Days: {pass_days} PASS | {partial_days} PARTIAL | {fail_days} FAIL / {total_days} total")
    print(f"  Common failure modes: {all_modes}")

    # ── Build JSON payload ─────────────────────────────────────────────────────
    payload = {
        "generated_at":    datetime.utcnow().isoformat() + "Z",
        "overall_verdict": overall,
        "summary": {
            "total_days":   total_days,
            "pass_days":    pass_days,
            "partial_days": partial_days,
            "fail_days":    fail_days,
            "date_range": {
                "first": all_dates[0] if all_dates else None,
                "last":  all_dates[-1] if all_dates else None,
            },
            "common_failure_modes": all_modes,
        },
        "hfs_truth":          hfs_result,
        "live_learning_path": live_result,
        "days":               day_results,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    # ── Build Markdown ─────────────────────────────────────────────────────────
    lines: list[str] = [
        "# VÉLØ SENTIENT LOOP FORENSIC AUDIT",
        "",
        f"Generated: {payload['generated_at']}",
        f"**Overall verdict: {overall}**",
        "",
        "## Summary",
        "",
        f"- Days audited: {total_days} ({all_dates[0]} → {all_dates[-1]})",
        f"- PASS: {pass_days} | PARTIAL: {partial_days} | FAIL: {fail_days}",
        "",
        "## Live Learning Path",
        "",
        f"**Verdict: {live_result['live_learning_verdict']}**",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| adapter_to_live_state | {live_result['adapter_to_live_state']} |",
        f"| HFS_TRAINING_SAFE | {live_result['hfs_training_safe']} |",
        f"| learning_allowed_default | {live_result['learning_allowed_default']} |",
        f"| Live state races | {live_result['live_races']} |",
        f"| Live state last updated | {live_result['live_state_last_updated']} |",
        f"| Training artifact races | {live_result['training_artifact_races']} |",
        f"| Training artifact diverged | {live_result['training_artifact_diverged']} |",
        "",
        "**Findings:**",
        "",
    ]
    for f in live_result["findings"]:
        lines.append(f"- ⚠ {f}")

    if live_result["blockers"]:
        lines += ["", "**Blockers from loop_status:**", ""]
        for b in live_result["blockers"]:
            lines.append(f"- {b}")

    lines += [
        "",
        "## HFS Signal Truth Audit",
        "",
        f"**Verdict: {hfs_result['verdict']}**",
        "",
        f"| Signal | Events | Populated | % | Status |",
        f"|---|---|---|---|---|",
        f"| MPI | {hfs_result['total_shadow_events']} | {hfs_result['mpi_populated']} | {hfs_result['mpi_pct']}% | {'PASS' if hfs_result['mpi_ok'] else '**FAIL**'} |",
        f"| chaos_bloom | {hfs_result['total_shadow_events']} | {hfs_result['chaos_populated']} | {hfs_result['chaos_pct']}% | {'PASS' if hfs_result['chaos_ok'] else '**FAIL**'} |",
        f"| learning_allowed | {hfs_result['total_shadow_events']} | {hfs_result['learning_allowed_events']} | {round(hfs_result['learning_allowed_events']/hfs_result['total_shadow_events']*100,1) if hfs_result['total_shadow_events'] else 0}% | {'PASS' if hfs_result['learning_allowed_events']>0 else '**FAIL**'} |",
        "",
        "**Issues:**",
        "",
    ]
    for issue in hfs_result["issues"]:
        lines.append(f"- ⚠ {issue}")

    lines += [
        "",
        "## Per-Day Loop Verification",
        "",
        "| Date | Verdict | Pred | Recon | Ingest | Mutate | Backup | Load | Failure Modes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    def _sym(v) -> str:
        if v is True:
            return "✓"
        if v is False:
            return "✗"
        return "~"

    for r in day_results:
        s = r["steps"]
        modes = " / ".join(r["failure_modes"]) if r["failure_modes"] else "—"
        lines.append(
            f"| {r['date']} "
            f"| **{r['verdict']}** "
            f"| {_sym(s['step1_prediction']['pass'])} "
            f"| {_sym(s['step2_reconcile']['pass'])} "
            f"| {_sym(s['step3_ingestion']['pass'])} "
            f"| {_sym(s['step4_mutation']['pass'])} "
            f"| {_sym(s['step5_backup']['pass'])} "
            f"| {_sym(s['step6_load']['pass'])} "
            f"| {modes} |"
        )

    lines += [
        "",
        "## Common Failure Mode Counts",
        "",
        "| Failure Mode | Days |",
        "|---|---|",
    ]
    for mode, count in sorted(all_modes.items(), key=lambda x: -x[1]):
        lines.append(f"| {mode} | {count} |")

    lines += [
        "",
        "## What the Audit Proves",
        "",
        "- **PREDICTION → SIGMA**: Connected if sigma studies exist per day",
        "- **SIGMA → EOD BRIDGE**: Connected if nightly audits show events_read > 0",
        "- **EOD BRIDGE → LIVE STATE**: DISCONNECTED — bridge is shadow-only by design",
        "- **HFS SIGNALS (MPI / chaos_bloom)**: Must be non-null in shadow events for real learning",
        "- **Training artifact unpromoted**: Training state exists at different race count than live",
        "",
        "## Hard Rules",
        "",
        "- No live code changed.",
        "- No model changed.",
        "- No Supabase writes.",
        "- No staking.",
        "- No Telegram betting alert.",
        "- Output is diagnostic evidence only.",
        "- Live learning must not be enabled until: HFS_TRAINING_SAFE=True + 7-day shadow loop validated + command authority sign-off.",
    ]

    OUT_MD.write_text("\n".join(lines))

    print(f"\nWritten: {OUT_JSON.name}")
    print(f"Written: {OUT_MD.name}")


if __name__ == "__main__":
    main()
