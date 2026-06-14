#!/usr/bin/env python3
"""
100-Day Truth Ledger — READ-ONLY forensic reconciliation
=========================================================
Classifies every historical race day from evidence: local artifacts +
GET-only Supabase reads. No mutation, no rewriting, no hindsight.

Operator command 2026-06-10: VELO_100_DAY_TRUTH_RECONCILIATION_REQUIRED.
Old verdicts are immutable; this ledger only labels them.

Day classifications (severity order, first match wins; all flags kept
in reasons):
  RPDC_ATTACH_FAILURE        candidates existed, local attach got nothing
  RPDC_PERSIST_CORRUPTED     persist boundary wrong (hijack window) —
                             evidence label corruption, NOT pick corruption
  SOURCE_UNKNOWN             no source-truth proof exists for the day
  PERSISTENCE_UNPROVEN       local output exists, Supabase rows absent
  SIGMA_MISSING              no post-race reconciliation found anywhere
  VALID_BUT_FEATURE_DEGRADED degraded source/features, outputs still valid
  SIGNED_CLEAN               full evidence chain green
  HISTORICAL_OUTPUT_ONLY     output exists, not enough evidence to certify

Cross-cutting flags: LEARNING_CONTAMINATION_RISK, PUBLIC_STATS_EXCLUDED,
training_eligible, public_stats_eligible.

Usage:
    PYTHONPATH=. python scripts/ops/build_100_day_truth_ledger.py

Outputs:
    data/current/velo_100_day_truth_ledger.json
    data/reports/velo_100_day_truth_ledger.md
"""
from __future__ import annotations

import glob
import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HIJACK_START = "2026-04-21"  # fda78d4 — RPDC persist boundary overwritten
HIJACK_END = "2026-06-10"    # 66d23a0 fixes forward from 2026-06-11
OBSERVABILITY_ERA_START = "2026-05-29"  # first observability packet on disk


# ── Supabase (GET-only, paginated) ────────────────────────────────────────────

def _load_env() -> dict:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _sb_page(env: dict, table: str, select: str, order: str) -> list | None:
    url = env.get("SUPABASE_URL") or (
        f"https://{env['SUPABASE_PROJECT_ID']}.supabase.co" if env.get("SUPABASE_PROJECT_ID") else ""
    )
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_KEY") or ""
    if not url or not key:
        return None
    rows: list = []
    offset = 0
    while True:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/{table}?select={select}&order={order}&limit=1000&offset={offset}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                batch = json.loads(resp.read().decode())
        except Exception:
            return None
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def fetch_supabase_day_buckets() -> dict | None:
    env = _load_env()
    vv = _sb_page(env, "velo_verdicts", "generated_at,rpdc_primary_tag,decision_tier", "generated_at.asc")
    if vv is None:
        return None
    sa = _sb_page(env, "sigma_audits", "created_at", "created_at.asc") or []
    rc = _sb_page(env, "runner_release_candidates", "run_date", "run_date.asc") or []
    out: dict = defaultdict(lambda: {"sb_verdicts": 0, "sb_rpdc_tagged": 0, "sb_null_tier": 0,
                                     "sb_sigma_rows": 0, "sb_candidates": 0})
    for r in vv:
        d = r["generated_at"][:10]
        out[d]["sb_verdicts"] += 1
        if r.get("rpdc_primary_tag"):
            out[d]["sb_rpdc_tagged"] += 1
        if r.get("decision_tier") is None:
            out[d]["sb_null_tier"] += 1
    for r in sa:
        out[r["created_at"][:10]]["sb_sigma_rows"] += 1
    for r in rc:
        out[r["run_date"]]["sb_candidates"] += 1
    return dict(out)


# ── Local artifacts ───────────────────────────────────────────────────────────

def _dates_from(pattern: str, rx: str) -> set[str]:
    out = set()
    for f in glob.glob(str(ROOT / pattern)):
        m = re.search(rx, f)
        if m:
            out.add(m.group(1).replace("_", "-"))
    return out


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def local_day_facts(d: str) -> dict:
    du = d.replace("-", "_")
    facts: dict = {"date": d}

    backup = _read_json(ROOT / "data" / f"velo_prime_verdicts_{du}.json")
    races = backup if isinstance(backup, list) else (backup or {}).get("races", [])
    facts["local_races"] = len(races)
    # Runner counts are not stored per race in older backups; races is the unit.
    synth = sum(1 for r in races if str(r.get("race_id", "")).startswith("rp_"))
    facts["synthetic_race_ids"] = synth
    statuses: dict[str, int] = {}
    for r in races:
        s = (r.get("top") or {}).get("rpdc_lookup_status")
        statuses[s or "FIELD_ABSENT"] = statuses.get(s or "FIELD_ABSENT", 0) + 1
    facts["rpdc_lookup_statuses"] = statuses
    facts["local_rpdc_attached"] = statuses.get("attached", 0)

    sig = _read_json(ROOT / "data" / "sigma_results" / f"sigma_results_{du}.json")
    if sig:
        facts["sigma_local"] = {
            "wins": sig.get("wins"),
            "evaluated": sig.get("evaluated_count") or sig.get("evaluated"),
            "frames": sig.get("frames"),
        }
    facts["results_file"] = (ROOT / "data" / "results" / f"rp_results_{du}.json").exists() or (
        ROOT / "data" / f"results_{du}.json"
    ).exists()

    # Observability: newest packet's source_truth
    best_label, best_ts = None, ""
    for f in glob.glob(str(ROOT / "data" / f"velo_run_observability_{du}_*.json")):
        pk = _read_json(Path(f)) or {}
        ts = pk.get("timestamp", "")
        if pk.get("source_truth") and ts >= best_ts:
            best_label, best_ts = pk.get("source_truth"), ts
    facts["observability_source_truth"] = best_label

    mc = _read_json(ROOT / "data" / "mission_control" / f"{d}_mission_control.json")
    if mc:
        facts["mc"] = {
            "source_truth": mc.get("source_truth"),
            "learning_gate": mc.get("learning_gate_status"),
            "council": mc.get("council_verdict"),
            "flatline_count": mc.get("flatline_count"),
        }

    ls = _read_json(ROOT / "data" / f"nightly_eod_learning_status_{du}.json")
    facts["learning_ran"] = ls is not None or (ROOT / "data" / f"playbook_g_nightly_audit_{du}.json").exists()
    if ls:
        facts["learning_status"] = {k: ls.get(k) for k in ("verdict", "live_sentient_state_touched", "events_created") if k in ls}
    return facts


# ── Classification ────────────────────────────────────────────────────────────

def classify(f: dict, sb: dict) -> tuple[str, list[str], bool, bool, bool]:
    """Return (final_classification, reasons, public_eligible, training_eligible, contamination_risk)."""
    d = f["date"]
    reasons: list[str] = []
    flags: list[str] = []

    src = f.get("observability_source_truth") or (f.get("mc") or {}).get("source_truth")
    sigma_present = bool(f.get("sigma_local")) or sb.get("sb_sigma_rows", 0) > 0
    sb_verdicts = sb.get("sb_verdicts", 0)
    candidates = sb.get("sb_candidates", 0)
    local_attached = f.get("local_rpdc_attached", 0)
    statuses = f.get("rpdc_lookup_statuses", {})
    rpdc_field_known = "FIELD_ABSENT" not in statuses or len(statuses) > 1

    # RPDC attach failure: candidates existed but attach demonstrably got nothing.
    attach_failure = False
    if candidates > 0 and f.get("local_races", 0) > 0:
        if rpdc_field_known and local_attached == 0 and statuses.get("no_data", 0) >= f["local_races"] * 0.9:
            attach_failure = True
        elif not rpdc_field_known and f.get("synthetic_race_ids", 0) >= f.get("local_races", 0) and f["local_races"] > 0:
            attach_failure = True
            reasons.append("synthetic race_ids on full card with candidates present (attach impossible)")
    if attach_failure:
        flags.append("RPDC_ATTACH_FAILURE")
        reasons.append(f"candidates={candidates}, local_attached=0")

    # RPDC persist corruption window (evidence labels, not picks).
    if HIJACK_START <= d <= HIJACK_END and sb_verdicts > 0:
        flags.append("RPDC_PERSIST_CORRUPTED")
        reasons.append("persist boundary hijacked fda78d4 window — Supabase rpdc fields not trustworthy")

    if src is None:
        flags.append("SOURCE_UNKNOWN")
        reasons.append("no observability/MC source-truth proof")
    elif src in ("RP_MERGED_DEGRADED", "SOURCE_UNKNOWN_BLOCK", "UNKNOWN"):
        flags.append("VALID_BUT_FEATURE_DEGRADED" if src == "RP_MERGED_DEGRADED" else "SOURCE_UNKNOWN")
        reasons.append(f"source_truth={src}")

    if f.get("local_races", 0) > 0 and sb_verdicts == 0:
        flags.append("PERSISTENCE_UNPROVEN")
        reasons.append("local verdicts exist, no Supabase rows for date")

    if not sigma_present:
        flags.append("SIGMA_MISSING")
        reasons.append("no sigma artifact locally or in sigma_audits")

    if (f.get("mc") or {}).get("flatline_count"):
        flags.append("VALID_BUT_FEATURE_DEGRADED")
        reasons.append(f"flatline_count={f['mc']['flatline_count']}")

    # Final classification by severity.
    order = [
        "RPDC_ATTACH_FAILURE",
        "RPDC_PERSIST_CORRUPTED",
        "SOURCE_UNKNOWN",
        "PERSISTENCE_UNPROVEN",
        "SIGMA_MISSING",
        "VALID_BUT_FEATURE_DEGRADED",
    ]
    final = next((c for c in order if c in flags), None)
    if final is None:
        if src == "RP_MERGED_CLEAN" and sigma_present and sb_verdicts > 0:
            final = "SIGNED_CLEAN"
        else:
            final = "HISTORICAL_OUTPUT_ONLY"
            reasons.append("output exists; evidence chain predates loop era")
    # Pre-evidence-era days with only SOURCE_UNKNOWN downgrade to HISTORICAL_OUTPUT_ONLY.
    if final == "SOURCE_UNKNOWN" and d < OBSERVABILITY_ERA_START and "RPDC_ATTACH_FAILURE" not in flags:
        final = (
            "RPDC_PERSIST_CORRUPTED" if "RPDC_PERSIST_CORRUPTED" in flags else "HISTORICAL_OUTPUT_ONLY"
        )

    contamination_risk = bool(f.get("learning_ran")) and final != "SIGNED_CLEAN"
    public_eligible = final == "SIGNED_CLEAN"
    training_eligible = final == "SIGNED_CLEAN"
    return final, reasons, public_eligible, training_eligible, contamination_risk


def main() -> int:
    sb_buckets = fetch_supabase_day_buckets()
    if sb_buckets is None:
        print("WARNING: Supabase unreachable — ledger will mark persistence UNPROVEN everywhere")
        sb_buckets = {}

    local_days = _dates_from("data/velo_prime_verdicts_*.json", r"verdicts_(\d{4}_\d{2}_\d{2})")
    sb_days = {d for d, v in sb_buckets.items() if v.get("sb_verdicts")}
    all_days = sorted(local_days | sb_days)

    ledger = []
    for d in all_days:
        facts = local_day_facts(d)
        sb = sb_buckets.get(d, {})
        final, reasons, pub, train, contam = classify(facts, sb)
        row = {
            **facts,
            **sb,
            "final_day_classification": final,
            "reasons": reasons,
            "public_stats_eligible": pub,
            "training_eligible": train,
            "learning_contamination_risk": contam,
        }
        ledger.append(row)

    counts: dict[str, int] = defaultdict(int)
    for row in ledger:
        counts[row["final_day_classification"]] += 1
    contam_days = [r["date"] for r in ledger if r["learning_contamination_risk"]]
    learning_days = [r["date"] for r in ledger if r.get("learning_ran")]

    # Sigma-verified aggregate after exclusions (clean-source sigma days only).
    sig_all_w = sig_all_e = sig_all_f = 0
    sig_clean_w = sig_clean_e = sig_clean_f = 0
    for r in ledger:
        s = r.get("sigma_local")
        if not s or not s.get("evaluated"):
            continue
        sig_all_w += s.get("wins") or 0
        sig_all_e += s.get("evaluated") or 0
        sig_all_f += s.get("frames") or 0
        if r.get("observability_source_truth") == "RP_MERGED_CLEAN" and "RPDC_ATTACH_FAILURE" not in r["reasons"][0:1] and r["final_day_classification"] not in ("RPDC_ATTACH_FAILURE",):
            sig_clean_w += s.get("wins") or 0
            sig_clean_e += s.get("evaluated") or 0
            sig_clean_f += s.get("frames") or 0

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only_confirmed": True,
        "old_verdicts_mutated": False,
        "scope": {
            "first_date": all_days[0] if all_days else None,
            "last_date": all_days[-1] if all_days else None,
            "race_days": len(all_days),
            "local_verdict_days": len(local_days),
            "supabase_verdict_days": len(sb_days),
        },
        "classification_counts": dict(counts),
        "learning_ran_days": learning_days,
        "learning_contamination_risk_days": contam_days,
        "sigma_recomputable": {
            "all_sigma_days": {"wins": sig_all_w, "evaluated": sig_all_e, "frames": sig_all_f,
                               "sr": round(sig_all_w / sig_all_e, 4) if sig_all_e else None},
            "clean_source_days_only": {"wins": sig_clean_w, "evaluated": sig_clean_e, "frames": sig_clean_f,
                                       "sr": round(sig_clean_w / sig_clean_e, 4) if sig_clean_e else None},
        },
        "days": ledger,
    }

    out_json = ROOT / "data/current/velo_100_day_truth_ledger.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(output, indent=2))

    lines = [
        "# VÉLØ 100-Day Truth Ledger",
        "",
        f"Generated {output['generated_at']} · READ-ONLY · old verdicts immutable",
        "",
        f"**Scope:** {output['scope']['first_date']} → {output['scope']['last_date']} · {output['scope']['race_days']} race days",
        "",
        "## Classification counts",
        "",
        "| Classification | Days |",
        "|---|---|",
    ]
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        f"**Learning ran on:** {len(learning_days)} days · **contamination risk:** {len(contam_days)} days",
        f"**Sigma recomputable (all):** {sig_all_w}/{sig_all_e} SR={output['sigma_recomputable']['all_sigma_days']['sr']}",
        f"**Sigma clean-source only:** {sig_clean_w}/{sig_clean_e} SR={output['sigma_recomputable']['clean_source_days_only']['sr']}",
        "",
        "## Per-day ledger",
        "",
        "| Date | Class | Races | SB verdicts | RPDC cand/local/SB | Sigma | Learning | Reasons |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in ledger:
        s = r.get("sigma_local") or {}
        sig = f"{s.get('wins')}/{s.get('evaluated')}" if s else ("rows" if r.get("sb_sigma_rows") else "—")
        lines.append(
            f"| {r['date']} | {r['final_day_classification']} | {r.get('local_races', 0)} | "
            f"{r.get('sb_verdicts', 0)} | {r.get('sb_candidates', 0)}/{r.get('local_rpdc_attached', 0)}/"
            f"{r.get('sb_rpdc_tagged', 0)} | {sig} | "
            f"{'RAN' + ('⚠' if r['learning_contamination_risk'] else '') if r.get('learning_ran') else '—'} | "
            f"{'; '.join(r['reasons'][:2])} |"
        )
    (ROOT / "data/reports").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/reports/velo_100_day_truth_ledger.md").write_text("\n".join(lines))

    print(f"Ledger built: {len(all_days)} days -> {out_json}")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    print(f"  learning ran: {len(learning_days)} days; contamination risk: {len(contam_days)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
