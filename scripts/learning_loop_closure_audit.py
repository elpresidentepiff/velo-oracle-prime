"""
learning_loop_closure_audit.py
==============================
Checks whether every daily prediction, shadow signal, paper directive,
and learning state has received closed results.

AUDIT ONLY — no mutations, no writes to Supabase, no model changes.

Outputs:
  data/learning_loop_closure_audit_latest.json
  data/learning_loop_closure_audit_latest.md
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime, date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

OUTPUT_JSON = ROOT / "data" / "learning_loop_closure_audit_latest.json"
OUTPUT_MD = ROOT / "data" / "learning_loop_closure_audit_latest.md"

# ── Supabase REST helpers ───────────────────────────────────────────────────────

def _sb_env() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    return url, key


def _sb_get(table: str, select: str, params: dict | None = None, limit: int = 10000) -> list[dict]:
    url, key = _sb_env()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Prefer": "count=none",
    }
    all_rows: list[dict] = []
    offset = 0
    page = min(limit, 1000)
    while True:
        query: dict[str, str] = {"select": select, "limit": str(page), "offset": str(offset)}
        if params:
            query.update(params)
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query.items())
        req_url = f"{url}/rest/v1/{table}?{qs}"
        req = urllib.request.Request(req_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            print(f"  WARNING: Supabase fetch error ({table}): {exc}", file=sys.stderr)
            return all_rows
        if not isinstance(data, list):
            print(f"  WARNING: Unexpected response from {table}: {data}", file=sys.stderr)
            return all_rows
        all_rows.extend(data)
        if len(data) < page:
            break
        offset += page
        if offset >= limit:
            break
    return all_rows


# Add urllib.parse import at module level
import urllib.parse

# ── CSV helpers ─────────────────────────────────────────────────────────────────

def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _check_ledger_fields(rows: list[dict], required_fields: list[str]) -> list[str]:
    """Return list of required fields that are missing from any row (or all blank)."""
    missing = []
    for field in required_fields:
        count_missing = sum(1 for r in rows if not r.get(field))
        if count_missing == len(rows):
            missing.append(f"{field} (all_blank)")
        elif count_missing > 0:
            missing.append(f"{field} ({count_missing}/{len(rows)} blank)")
    return missing


# ── Main audit ─────────────────────────────────────────────────────────────────

def run_audit() -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    print(f"[learning_loop_closure_audit] Starting audit at {generated_at}")

    # ── 1. Verdicts ─────────────────────────────────────────────────────────────
    print("  Fetching velo_verdicts from Supabase ...")
    verdict_rows = _sb_get("velo_verdicts", "race_id,generated_at,decision_tier,velo_prime_prob")
    total_verdicts = len(verdict_rows)

    # Build a set of race_ids that have results in runner_results
    print("  Fetching runner_results (race_ids with closed results) ...")
    result_rows_sb = _sb_get("runner_results", "race_id,horse_id,position,sp_dec,is_winner")
    closed_race_ids: set[str] = {str(r["race_id"]) for r in result_rows_sb if r.get("race_id")}

    verdict_race_ids: set[str] = {str(r["race_id"]) for r in verdict_rows if r.get("race_id")}
    verdicts_with_results = len(verdict_race_ids & closed_race_ids)
    verdicts_without_results = len(verdict_race_ids - closed_race_ids)

    # ── 2. Sigma audits ─────────────────────────────────────────────────────────
    print("  Fetching sigma_audits from Supabase ...")
    sigma_rows = _sb_get("sigma_audits", "race_id,date,outcome,top_pick_position")
    sigma_by_date: dict[str, list[dict]] = defaultdict(list)
    for r in sigma_rows:
        d = str(r.get("date") or "unknown")
        sigma_by_date[d].append(r)

    sigma_closed_count: dict[str, int] = {}
    sigma_unclosed_count: dict[str, int] = {}
    for d, rows in sigma_by_date.items():
        closed = sum(1 for r in rows if r.get("outcome") and r.get("outcome") != "PENDING")
        sigma_closed_count[d] = closed
        sigma_unclosed_count[d] = len(rows) - closed

    # ── 3. Racing API shadow forward ledger ────────────────────────────────────
    print("  Reading racing_api_shadow_forward_ledger.csv ...")
    api_ledger_path = ROOT / "data" / "racing_api_shadow_forward_ledger.csv"
    api_rows = _read_csv(api_ledger_path)
    racing_api_shadow_rows = len(api_rows)
    racing_api_shadow_outcome_backfilled = sum(
        1 for r in api_rows if r.get("won") or r.get("result_position")
    )

    api_missing_fields = _check_ledger_fields(api_rows, ["race_id", "horse_id", "sp_decimal"]) if api_rows else []
    rows_missing_race_id_api = sum(1 for r in api_rows if not r.get("race_id"))
    rows_missing_horse_id_api = sum(1 for r in api_rows if not r.get("horse_id"))
    rows_missing_sp_api = sum(1 for r in api_rows if not r.get("sp_decimal"))

    # ── 4. Paper ledger ────────────────────────────────────────────────────────
    print("  Reading velo_execution_bridge_paper_ledger.csv ...")
    paper_ledger_path = ROOT / "data" / "velo_execution_bridge_paper_ledger.csv"
    paper_rows = _read_csv(paper_ledger_path)
    power_anchor_rows = sum(1 for r in paper_rows if r.get("directive_type") == "POWER_ANCHOR_MODE")
    power_anchor_outcome_backfilled = sum(
        1 for r in paper_rows
        if r.get("directive_type") == "POWER_ANCHOR_MODE"
        and (r.get("won") or r.get("result_position"))
    )

    paper_missing_fields = _check_ledger_fields(paper_rows, ["race_id", "horse_id", "sp_decimal"]) if paper_rows else []
    rows_missing_race_id_paper = sum(1 for r in paper_rows if not r.get("race_id"))
    rows_missing_horse_id_paper = sum(1 for r in paper_rows if not r.get("horse_id"))
    rows_missing_sp_paper = sum(1 for r in paper_rows if not r.get("sp_decimal"))

    # ── 5. Router shadow audit ledger ─────────────────────────────────────────
    print("  Reading router_shadow_audit_ledger.csv ...")
    router_ledger_path = ROOT / "data" / "router_shadow_audit_ledger.csv"
    router_rows = _read_csv(router_ledger_path)
    router_missing_fields = _check_ledger_fields(router_rows, ["run_ts", "lane", "n"]) if router_rows else []

    # ── 6. Sentient state ──────────────────────────────────────────────────────
    print("  Checking sentient_state_shadow.json ...")
    sentient_path = ROOT / "data" / "sentient_state_shadow.json"
    sentient_state: dict = {}
    sentient_status = "NOT_FOUND"
    if sentient_path.exists():
        try:
            sentient_state = json.loads(sentient_path.read_text(encoding="utf-8"))
            sentient_status = "FOUND"
        except Exception as e:
            sentient_status = f"PARSE_ERROR: {e}"

    sentient_path2 = ROOT / "data" / "sentient_state.json"
    sentient_state2: dict = {}
    if sentient_path2.exists():
        try:
            sentient_state2 = json.loads(sentient_path2.read_text(encoding="utf-8"))
            sentient_status = "FOUND_BOTH"
        except Exception:
            pass

    # ── 7. Sidecar ablation audit ─────────────────────────────────────────────
    print("  Checking live_sidecar_ablation_audit_latest.json ...")
    sidecar_path = ROOT / "data" / "live_sidecar_ablation_audit_latest.json"
    sidecar_status = "NOT_FOUND"
    sidecar_generated_at = None
    sidecar_baseline_matched = None
    if sidecar_path.exists():
        try:
            sidecar_data = json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar_status = "FOUND"
            sidecar_generated_at = sidecar_data.get("generated_at")
            sidecar_baseline_matched = sidecar_data.get("sample", {}).get("baseline_top_matched")
        except Exception as e:
            sidecar_status = f"PARSE_ERROR: {e}"

    # ── 8. Local results JSON files ─────────────────────────────────────────────
    print("  Scanning data/results_*.json files ...")
    results_files = sorted(ROOT.glob("data/results_*.json"))
    results_file_count = len(results_files)
    results_total_races = 0
    results_with_positions = 0
    for rf in results_files:
        try:
            d = json.loads(rf.read_text(encoding="utf-8"))
            races = d.get("results", []) if isinstance(d, dict) else d
            for race in races:
                runners = race.get("runners", [])
                results_total_races += 1
                if any(r.get("position") for r in runners):
                    results_with_positions += 1
        except Exception:
            pass

    # ── 9. Daily closure status ────────────────────────────────────────────────
    print("  Computing daily closure status ...")
    # A day is CLOSED if sigma has results AND verdicts have runner_results
    # PARTIAL if some sigma rows are unclosed
    # BROKEN if sigma exists but no results at all

    all_dates: set[str] = set(sigma_by_date.keys())
    # Also gather dates from verdicts
    for r in verdict_rows:
        gen = str(r.get("generated_at") or "")
        if gen:
            all_dates.add(gen[:10])

    daily_closure_status: dict[str, str] = {}
    for d in sorted(all_dates):
        if d == "unknown":
            continue
        has_sigma = d in sigma_by_date
        sigma_closed = sigma_closed_count.get(d, 0)
        sigma_unclosed = sigma_unclosed_count.get(d, 0)
        sigma_total = sigma_closed + sigma_unclosed

        # Check if any verdicts for this day have results
        day_verdict_ids = {
            str(r["race_id"])
            for r in verdict_rows
            if str(r.get("generated_at", "")).startswith(d)
        }
        day_has_results = bool(day_verdict_ids & closed_race_ids)

        if not has_sigma:
            daily_closure_status[d] = "BROKEN"
        elif sigma_total == 0:
            daily_closure_status[d] = "BROKEN"
        elif sigma_unclosed == 0 and day_has_results:
            daily_closure_status[d] = "CLOSED"
        elif sigma_closed > 0:
            daily_closure_status[d] = "PARTIAL"
        else:
            daily_closure_status[d] = "BROKEN"

    # ── 10. Broken connectors ─────────────────────────────────────────────────
    broken_connectors: list[str] = []

    if verdicts_without_results > 0:
        broken_connectors.append(
            f"velo_verdicts: {verdicts_without_results}/{total_verdicts} verdicts have no runner_results"
        )
    if racing_api_shadow_rows > 0 and racing_api_shadow_outcome_backfilled == 0:
        broken_connectors.append(
            f"racing_api_shadow_forward_ledger: {racing_api_shadow_rows} rows, 0 outcomes backfilled"
        )
    if power_anchor_rows > 0 and power_anchor_outcome_backfilled == 0:
        broken_connectors.append(
            f"paper_ledger POWER_ANCHOR: {power_anchor_rows} rows, 0 outcomes backfilled"
        )
    if sentient_status == "NOT_FOUND":
        broken_connectors.append("sentient_state_shadow.json: NOT_FOUND — Playbook G state not persisted")
    broken_from_sigma = [d for d, s in daily_closure_status.items() if s == "BROKEN"]
    if broken_from_sigma:
        broken_connectors.append(
            f"sigma loop broken for {len(broken_from_sigma)} dates: {broken_from_sigma[:5]}"
        )
    if sidecar_status == "NOT_FOUND":
        broken_connectors.append("live_sidecar_ablation_audit_latest.json: NOT_FOUND")

    # ── Combined missing fields ────────────────────────────────────────────────
    ledgers_missing_result_fields = (
        [f"api_ledger:{f}" for f in api_missing_fields]
        + [f"paper_ledger:{f}" for f in paper_missing_fields]
        + [f"router_ledger:{f}" for f in router_missing_fields]
    )

    # ── Summary counts ─────────────────────────────────────────────────────────
    closed_days = sum(1 for s in daily_closure_status.values() if s == "CLOSED")
    partial_days = sum(1 for s in daily_closure_status.values() if s == "PARTIAL")
    broken_days = sum(1 for s in daily_closure_status.values() if s == "BROKEN")

    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "total_verdicts": total_verdicts,
        "verdicts_with_results": verdicts_with_results,
        "verdicts_without_results": verdicts_without_results,
        "sigma_total_rows": len(sigma_rows),
        "sigma_closed_count": dict(sigma_closed_count),
        "sigma_unclosed_count": dict(sigma_unclosed_count),
        "racing_api_shadow_rows": racing_api_shadow_rows,
        "racing_api_shadow_outcome_backfilled": racing_api_shadow_outcome_backfilled,
        "power_anchor_rows": power_anchor_rows,
        "power_anchor_outcome_backfilled": power_anchor_outcome_backfilled,
        "paper_ledger_rows_total": len(paper_rows),
        "router_ledger_rows_total": len(router_rows),
        "ledgers_missing_result_fields": ledgers_missing_result_fields,
        "rows_missing_race_id": rows_missing_race_id_api + rows_missing_race_id_paper,
        "rows_missing_horse_id": rows_missing_horse_id_api + rows_missing_horse_id_paper,
        "rows_missing_sp": rows_missing_sp_api + rows_missing_sp_paper,
        "daily_closure_status": daily_closure_status,
        "daily_summary": {
            "closed": closed_days,
            "partial": partial_days,
            "broken": broken_days,
            "total": len(daily_closure_status),
        },
        "broken_connectors": broken_connectors,
        "sentient_state_status": sentient_status,
        "sentient_has_doctrine_strengths": bool(
            sentient_state.get("doctrine_strengths") or sentient_state2.get("doctrine_strengths")
        ),
        "results_json_files": results_file_count,
        "results_json_total_races": results_total_races,
        "results_json_with_positions": results_with_positions,
        "sidecar_ablation_status": sidecar_status,
        "sidecar_ablation_generated_at": sidecar_generated_at,
        "sidecar_ablation_baseline_matched": sidecar_baseline_matched,
    }

    return payload


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    ds = payload["daily_summary"]
    lines = [
        "# VÉLØ Learning Loop Closure Audit",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        "",
        "## Verdicts",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total velo_verdicts | {payload['total_verdicts']} |",
        f"| Verdicts with closed runner_results | {payload['verdicts_with_results']} |",
        f"| Verdicts WITHOUT results | {payload['verdicts_without_results']} |",
        "",
        "## Sigma Audits",
        "",
        f"| Total sigma rows | {payload['sigma_total_rows']} |",
        f"|---|---|",
    ]

    # Daily sigma breakdown
    lines += ["", "| Date | Closed | Unclosed | Status |", "|---|---|---|---|"]
    for d, status in sorted(payload["daily_closure_status"].items())[-20:]:
        cl = payload["sigma_closed_count"].get(d, 0)
        un = payload["sigma_unclosed_count"].get(d, 0)
        lines.append(f"| {d} | {cl} | {un} | {status} |")
    lines.append("")

    lines += [
        "## Ledger Closure Status",
        "",
        f"| Ledger | Rows | Outcomes Backfilled |",
        f"|---|---|---|",
        f"| Racing API Shadow Forward | {payload['racing_api_shadow_rows']} | {payload['racing_api_shadow_outcome_backfilled']} |",
        f"| Paper Ledger (POWER_ANCHOR) | {payload['power_anchor_rows']} | {payload['power_anchor_outcome_backfilled']} |",
        f"| Paper Ledger (total) | {payload['paper_ledger_rows_total']} | — |",
        f"| Router Shadow Ledger | {payload['router_ledger_rows_total']} | — |",
        "",
        "## Results JSON Files",
        "",
        f"- Files found: `{payload['results_json_files']}`",
        f"- Total races: `{payload['results_json_total_races']}`",
        f"- Races with positions: `{payload['results_json_with_positions']}`",
        "",
        "## Missing Fields",
        "",
    ]
    if payload["ledgers_missing_result_fields"]:
        for f in payload["ledgers_missing_result_fields"]:
            lines.append(f"- {f}")
    else:
        lines.append("- None detected")
    lines.append("")

    lines += [
        "## Daily Summary",
        "",
        f"| Status | Count |",
        f"|---|---|",
        f"| CLOSED | {ds['closed']} |",
        f"| PARTIAL | {ds['partial']} |",
        f"| BROKEN | {ds['broken']} |",
        f"| Total | {ds['total']} |",
        "",
        "## Broken Connectors",
        "",
    ]
    if payload["broken_connectors"]:
        for bc in payload["broken_connectors"]:
            lines.append(f"- {bc}")
    else:
        lines.append("- None — all connectors wired")
    lines.append("")

    lines += [
        "## Learning State",
        "",
        f"- Sentient state status: `{payload['sentient_state_status']}`",
        f"- Has doctrine_strengths: `{payload['sentient_has_doctrine_strengths']}`",
        f"- Sidecar ablation audit: `{payload['sidecar_ablation_status']}`",
        f"- Sidecar audit generated_at: `{payload['sidecar_ablation_generated_at']}`",
        f"- Sidecar baseline matched: `{payload['sidecar_ablation_baseline_matched']}`",
        "",
        "---",
        "*Audit only — no mutations.*",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Written: {OUTPUT_JSON.name}")
    print(f"  Written: {OUTPUT_MD.name}")


def main() -> int:
    payload = run_audit()
    write_outputs(payload)

    ds = payload["daily_summary"]
    print()
    print("=" * 60)
    print("LEARNING LOOP CLOSURE AUDIT SUMMARY")
    print("=" * 60)
    print(f"  Verdicts total:    {payload['total_verdicts']}")
    print(f"  With results:      {payload['verdicts_with_results']}")
    print(f"  Without results:   {payload['verdicts_without_results']}")
    print(f"  Days CLOSED:       {ds['closed']}")
    print(f"  Days PARTIAL:      {ds['partial']}")
    print(f"  Days BROKEN:       {ds['broken']}")
    if payload["broken_connectors"]:
        print(f"\n  BROKEN CONNECTORS:")
        for bc in payload["broken_connectors"]:
            print(f"    - {bc}")
    else:
        print("\n  No broken connectors detected.")

    if ds["broken"] > 0:
        status = "BROKEN"
    elif ds["partial"] > 0:
        status = "PARTIAL"
    else:
        status = "CLOSED"
    print(f"\n  OVERALL STATUS: {status}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
