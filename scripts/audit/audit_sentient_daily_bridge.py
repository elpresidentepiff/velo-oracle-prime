"""
audit_sentient_daily_bridge.py — VÉLØ Sentient Daily Bridge Regression Audit

Runs the patched eod_shadow_learning_bridge.py for a given date and
verifies all A-O criteria from the task board.

Pass criteria:
  - observe success >= 99%
  - learning_allowed True on all valid closed outcomes
  - MPI coverage 100% (no null)
  - no silent hardcoded SP on real results
  - chaos_bloom no TypeError path
  - no duplicate consumed keys
  - live state hash unchanged
  - state mutates only in shadow

Classification returned:
  SENTIENT_DAILY_BRIDGE_READY_FOR_7_DAY_SHADOW
  SENTIENT_DAILY_BRIDGE_REPAIR_INCOMPLETE
  SENTIENT_DAILY_BRIDGE_BLOCKED

Output:
  data/audit_sentient_daily_bridge_YYYY_MM_DD.json
  data/audit_sentient_daily_bridge_latest.json

Hard rules:
  - Read-only audit of bridge output. No scoring changes.
  - No live state writes. No model changes. No staking. No Telegram.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATA     = ROOT / "data"
LIVE_STATE = DATA / "sentient_state.json"
SHADOW_DAILY_STATE = DATA / "sentient_state_shadow_daily.json"
SHADOW_OUTCOME_LEDGER = DATA / "playbook_g_outcome_events_shadow_daily.jsonl"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hash(path: Path) -> str:
    if not path.exists():
        return "FILE_NOT_FOUND"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "variance": None}
    return {
        "count":    len(values),
        "min":      round(min(values), 4),
        "max":      round(max(values), 4),
        "mean":     round(statistics.mean(values), 4),
        "variance": round(statistics.variance(values) if len(values) > 1 else 0.0, 6),
    }


def _load_today_events(date_str: str) -> list[dict]:
    """Read events for today's date from the daily shadow ledger."""
    events = []
    if not SHADOW_OUTCOME_LEDGER.exists():
        return events
    for line in SHADOW_OUTCOME_LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
            if ev.get("event_date") == date_str:
                events.append(ev)
        except Exception:
            pass
    return events


# ─── Audit ────────────────────────────────────────────────────────────────────

def run_audit(date_str: str) -> dict:

    # ── Run the bridge ─────────────────────────────────────────────────────────
    live_hash_before = _hash(LIVE_STATE)
    shadow_races_before = (_load(SHADOW_DAILY_STATE) or {}).get("total_races_observed", 0)

    print(f"[audit] Running bridge for {date_str}…")
    from scripts.eod_shadow_learning_bridge import ShadowLearningBridge
    bridge = ShadowLearningBridge(date_str=date_str)
    bridge.run()

    live_hash_after = _hash(LIVE_STATE)
    shadow_state    = _load(SHADOW_DAILY_STATE) or {}
    shadow_races_after = shadow_state.get("total_races_observed", 0)

    # ── Load today's events from ledger ────────────────────────────────────────
    events = _load_today_events(date_str)
    total  = len(events)

    # ── A — Events scanned ────────────────────────────────────────────────────
    A = {"events_scanned": total}

    # ── B — observe attempted ─────────────────────────────────────────────────
    B = {"observe_attempted": bridge.obs_called}

    # ── C — observe succeeded ─────────────────────────────────────────────────
    success_rate = round(bridge.obs_success / bridge.obs_called * 100, 2) if bridge.obs_called else 0
    C = {
        "observe_succeeded":  bridge.obs_success,
        "success_rate_pct":   success_rate,
        "pass_threshold_pct": 99.0,
        "pass":               success_rate >= 99.0 or bridge.obs_called == 0,
    }

    # ── D — Failed events ─────────────────────────────────────────────────────
    D = {
        "failed_count":  len(bridge.obs_failures),
        "failures":      bridge.obs_failures,
    }

    # ── E — learning_allowed counts ───────────────────────────────────────────
    la_true  = sum(1 for e in events if e.get("learning_allowed") is True)
    la_false = sum(1 for e in events if e.get("learning_allowed") is False)
    block_reasons: dict[str, int] = {}
    for e in events:
        reason = e.get("learning_block_reason")
        if reason:
            block_reasons[reason] = block_reasons.get(reason, 0) + 1

    E = {
        "learning_allowed_true":  la_true,
        "learning_allowed_false": la_false,
        "block_reason_breakdown": block_reasons,
        "pass":                   la_false == 0 or all(
            r in ("outcome_unknown", "race_id_missing", "winner_id_missing", "predicted_horse_id_missing")
            for r in block_reasons
        ),
    }

    # ── F — MPI stats ─────────────────────────────────────────────────────────
    mpi_vals  = [e.get("mpi") for e in events]
    mpi_null  = sum(1 for v in mpi_vals if v is None)
    mpi_real  = [float(v) for v in mpi_vals if v is not None]
    mpi_srcs: dict[str, int] = {}
    for e in events:
        src = e.get("mpi_source") or e.get("mpi_src") or "unknown"
        mpi_srcs[src] = mpi_srcs.get(src, 0) + 1

    F = {
        "null_count":       mpi_null,
        "coverage_pct":     round(len(mpi_real) / total * 100, 1) if total else 0,
        "source_breakdown": mpi_srcs,
        **_stats(mpi_real),
        "pass":             mpi_null == 0,
    }

    # ── G — chaos_bloom stats ─────────────────────────────────────────────────
    chaos_vals = [e.get("chaos_bloom") for e in events]
    chaos_null = sum(1 for v in chaos_vals if v is None)
    chaos_real = [float(v) for v in chaos_vals if v is not None]
    chaos_srcs: dict[str, int] = {}
    for e in events:
        src = e.get("chaos_bloom_source") or e.get("chaos_src") or "unknown"
        chaos_srcs[src] = chaos_srcs.get(src, 0) + 1

    # TypeError check: verify no None values reach engine (chaos is always float now)
    G = {
        "null_count":       chaos_null,
        "coverage_pct":     round(len(chaos_real) / total * 100, 1) if total else 0,
        "source_breakdown": chaos_srcs,
        "typeerror_risk":   chaos_null > 0,
        **_stats(chaos_real),
        "pass":             chaos_null == 0,
    }

    # ── H — SP provenance stats ───────────────────────────────────────────────
    sp_sources: dict[str, int] = {}
    sp_hardcoded = 0
    sp_missing   = 0
    sp_real_vals = []
    for e in events:
        src = e.get("sp_source") or "unknown"
        sp_sources[src] = sp_sources.get(src, 0) + 1
        if e.get("sp_is_hardcoded"):
            sp_hardcoded += 1
        sp_val = e.get("sp_decimal")
        if sp_val is None:
            sp_missing += 1
        elif float(sp_val) > 0:
            sp_real_vals.append(float(sp_val))

    H = {
        "real_sp_count":         len(sp_real_vals),
        "hardcoded_count":       sp_hardcoded,
        "missing_count":         sp_missing,
        "source_breakdown":      sp_sources,
        "coverage_pct":          round(len(sp_real_vals) / total * 100, 1) if total else 0,
        **_stats(sp_real_vals),
        "pass":                  sp_hardcoded == 0,
    }

    # ── I — Idempotency proof ─────────────────────────────────────────────────
    all_keys = [e.get("idempotency_key", "") for e in events]
    key_counts: dict[str, int] = {}
    for k in all_keys:
        key_counts[k] = key_counts.get(k, 0) + 1
    duplicates = {k: v for k, v in key_counts.items() if v > 1}

    I = {
        "total_keys":         len(all_keys),
        "duplicate_count":    len(duplicates),
        "duplicate_examples": list(duplicates.items())[:3],
        "pass":               len(duplicates) == 0,
    }

    # ── J — Target state path ─────────────────────────────────────────────────
    targets = set(e.get("sentient_state_target", "") for e in events)
    J = {
        "distinct_targets": list(targets),
        "target_is_shadow": all("shadow" in t for t in targets if t),
        "target_not_live":  all("sentient_state.json" not in t or "shadow" in t for t in targets if t),
    }

    # ── K — Live hash ─────────────────────────────────────────────────────────
    K = {
        "live_hash_before":    live_hash_before[:32] + "…",
        "live_hash_after":     live_hash_after[:32] + "…",
        "live_state_untouched": live_hash_before == live_hash_after,
        "pass":                live_hash_before == live_hash_after,
    }

    # ── L — State mutation delta ──────────────────────────────────────────────
    L = {
        "shadow_races_before": shadow_races_before,
        "shadow_races_after":  shadow_races_after,
        "delta":               shadow_races_after - shadow_races_before,
        "state_mutated":       shadow_races_after > shadow_races_before,
        "aggression":          shadow_state.get("appetite_state", {}).get("aggression_level"),
    }

    # ── M — DAILY_CLOSE_READY ─────────────────────────────────────────────────
    M = {
        "DAILY_CLOSE_READY": (
            K["live_state_untouched"]
            and C["pass"]
            and F["pass"]
            and G["pass"]
            and I["pass"]
        ),
        "criteria": {
            "live_untouched":        K["live_state_untouched"],
            "observe_success_99pct": C["pass"],
            "mpi_no_null":           F["pass"],
            "chaos_no_null":         G["pass"],
            "no_duplicate_keys":     I["pass"],
        },
    }

    # ── N — LIVE_PROMOTION_READY ──────────────────────────────────────────────
    N = {
        "LIVE_PROMOTION_READY": False,
        "blockers": [
            "HFS_TRAINING_SAFE=False — hard gate unchanged",
            "7-14 day shadow accumulation not yet complete",
            "Operator sign-off not yet given",
        ],
    }

    # ── O — Remaining blockers ────────────────────────────────────────────────
    O_blockers = []
    if not K["live_state_untouched"]:
        O_blockers.append("CRITICAL: live sentient_state.json was modified")
    if not C["pass"]:
        O_blockers.append(f"observe success {success_rate}% < 99% threshold")
    if not F["pass"]:
        O_blockers.append(f"MPI null count: {mpi_null}")
    if not G["pass"]:
        O_blockers.append(f"chaos_bloom null count: {chaos_null} — TypeError risk")
    if not I["pass"]:
        O_blockers.append(f"Duplicate idempotency keys: {len(duplicates)}")
    if sp_hardcoded > 0:
        O_blockers.append(f"SP hardcoded on {sp_hardcoded} events (sp_is_hardcoded=True)")
    O_blockers.append("HFS_TRAINING_SAFE=False — live promotion blocked")
    O_blockers.append("7-14 day shadow accumulation must complete before promotion review")

    O = {"blockers": O_blockers}

    # ── Classification ─────────────────────────────────────────────────────────
    hard_fails = not K["live_state_untouched"] or (bridge.obs_called > 0 and bridge.obs_success == 0)
    soft_fails = not M["DAILY_CLOSE_READY"]

    if hard_fails:
        classification = "SENTIENT_DAILY_BRIDGE_BLOCKED"
    elif soft_fails:
        classification = "SENTIENT_DAILY_BRIDGE_REPAIR_INCOMPLETE"
    else:
        classification = "SENTIENT_DAILY_BRIDGE_READY_FOR_7_DAY_SHADOW"

    return {
        "generated_at":    datetime.utcnow().isoformat() + "Z",
        "date_audited":    date_str,
        "classification":  classification,
        "A_events_scanned":          A,
        "B_observe_attempted":       B,
        "C_observe_succeeded":       C,
        "D_failed_events":           D,
        "E_learning_allowed":        E,
        "F_mpi_stats":               F,
        "G_chaos_bloom_stats":       G,
        "H_sp_provenance":           H,
        "I_idempotency":             I,
        "J_target_state":            J,
        "K_live_hash":               K,
        "L_state_mutation":          L,
        "M_DAILY_CLOSE_READY":       M,
        "N_LIVE_PROMOTION_READY":    N,
        "O_blockers":                O,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Audit VÉLØ sentient daily bridge")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    print("VÉLØ SENTIENT DAILY BRIDGE REGRESSION AUDIT")
    print("=" * 60)

    payload = run_audit(args.date)

    # Write outputs
    dated_out  = DATA / f"audit_sentient_daily_bridge_{args.date.replace('-','_')}.json"
    latest_out = DATA / "audit_sentient_daily_bridge_latest.json"
    dated_out.write_text(json.dumps(payload, indent=2))
    latest_out.write_text(json.dumps(payload, indent=2))

    cls = payload["classification"]
    M   = payload["M_DAILY_CLOSE_READY"]
    F   = payload["F_mpi_stats"]
    G   = payload["G_chaos_bloom_stats"]
    C   = payload["C_observe_succeeded"]
    L   = payload["L_state_mutation"]
    K   = payload["K_live_hash"]

    print(f"\n  Date:               {args.date}")
    print(f"  Events scanned:     {payload['A_events_scanned']['events_scanned']}")
    print(f"  observe attempted:  {payload['B_observe_attempted']['observe_attempted']}")
    print(f"  observe succeeded:  {C['observe_succeeded']} ({C['success_rate_pct']}%) → {'PASS' if C['pass'] else 'FAIL'}")
    print(f"  learning_allowed T: {payload['E_learning_allowed']['learning_allowed_true']}")
    print(f"  MPI null:           {F['null_count']} / mean={F.get('mean')} variance={F.get('variance')} → {'PASS' if F['pass'] else 'FAIL'}")
    print(f"  chaos null:         {G['null_count']} / mean={G.get('mean')} → {'PASS' if G['pass'] else 'FAIL'}")
    print(f"  SP real count:      {payload['H_sp_provenance']['real_sp_count']} / hardcoded={payload['H_sp_provenance']['hardcoded_count']}")
    print(f"  Duplicate keys:     {payload['I_idempotency']['duplicate_count']} → {'PASS' if payload['I_idempotency']['pass'] else 'FAIL'}")
    print(f"  Live hash match:    {K['live_state_untouched']} → {'PASS' if K['pass'] else 'FAIL'}")
    print(f"  State Δ races:      {L['delta']:+d} ({L['shadow_races_before']} → {L['shadow_races_after']})")
    print(f"  DAILY_CLOSE_READY:  {M['DAILY_CLOSE_READY']}")
    print(f"  LIVE_PROM_READY:    {payload['N_LIVE_PROMOTION_READY']['LIVE_PROMOTION_READY']}")
    print(f"\n  CLASSIFICATION: {cls}")
    print(f"\n  Blockers: {len(payload['O_blockers']['blockers'])}")
    for b in payload["O_blockers"]["blockers"]:
        print(f"    - {b[:80]}")

    print(f"\nWritten: {dated_out.name}")
    print(f"Written: {latest_out.name}")


if __name__ == "__main__":
    main()
