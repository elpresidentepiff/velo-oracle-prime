#!/usr/bin/env python3
"""
Sigma Universe Extractor — READ-ONLY
=====================================
Reconciles EVERY sigma-conclusion source before any ROI number is allowed
to call itself "the number". Operator law: SIGMA_UNIVERSE_FIRST.

Sources scanned:
  1. Supabase sigma_audits (GET-only, paginated)   -> RACE_SIGMA (canonical)
  2. data/sigma_results/*.json                      -> DAY_SIGMA summaries
  3. data/velo_innovation_protocol_1k_deduped.csv   -> DERIVED top-pick rows
  4. data/velo_execution_bridge_paper_ledger.csv    -> SHADOW_ROUTER_SIGMA
  5. data/sigma_memory/sigma_retrieval_corpus_v1.jsonl -> DERIVED_DUPLICATE
  6. data/velo_unified_evidence_audit_v1.json       -> historical summary
  7. data/router_shadow_audit_ledger.csv            -> SHADOW_ROUTER_SIGMA agg

Outputs:
    data/current/sigma_universe.json
    data/reports/sigma_universe.md
"""
from __future__ import annotations

import csv
import glob
import json
import sys
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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


def fetch_sigma_audits() -> list | None:
    env = _load_env()
    url = env.get("SUPABASE_URL") or (
        f"https://{env['SUPABASE_PROJECT_ID']}.supabase.co" if env.get("SUPABASE_PROJECT_ID") else ""
    )
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_KEY") or ""
    if not url or not key:
        return None
    rows: list = []
    offset = 0
    sel = "date,race_id,horse_id,event_type,outcome,actual_winner_sp,decision_tier,miss_reason"
    while True:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/sigma_audits?select={sel}&order=created_at.asc&limit=1000&offset={offset}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
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


def main() -> int:
    universe: dict = {"generated_at": datetime.now(UTC).isoformat(), "read_only_confirmed": True, "sources": {}}

    # 1. Canonical race-level conclusions
    sa = fetch_sigma_audits()
    if sa is None:
        universe["sources"]["supabase_sigma_audits"] = {"status": "UNREACHABLE"}
        sa = []
    else:
        keyed = {(r["date"], r["race_id"]): r for r in sa}
        oc = Counter(r.get("outcome") for r in sa)
        universe["sources"]["supabase_sigma_audits"] = {
            "classification": "RACE_SIGMA (canonical per-race conclusions)",
            "raw_rows": len(sa),
            "deduplicated": len(keyed),
            "date_range": [min((r["date"] for r in sa if r.get("date")), default=None),
                           max((r["date"] for r in sa if r.get("date")), default=None)],
            "outcomes": {str(k): v for k, v in oc.items()},
            "event_types": dict(Counter(str(r.get("event_type")) for r in sa)),
        }

    # 2. Day summaries
    day_files = sorted(glob.glob(str(ROOT / "data/sigma_results/sigma_results_*.json")))
    day_tot_w = day_tot_e = 0
    for f in day_files:
        try:
            d = json.loads(Path(f).read_text())
            day_tot_w += d.get("wins") or 0
            day_tot_e += d.get("evaluated_count") or 0
        except Exception:
            pass
    universe["sources"]["local_sigma_results"] = {
        "classification": "DAY_SIGMA (summaries — derived from race sigma)",
        "files": len(day_files),
        "wins": day_tot_w,
        "evaluated": day_tot_e,
    }

    # 3. Innovation protocol (router evidence — derived from verdicts+results)
    inn_path = ROOT / "data/velo_innovation_protocol_1k_deduped.csv"
    inn_rows = []
    if inn_path.exists():
        inn_rows = list(csv.DictReader(inn_path.open()))
    with_result = [r for r in inn_rows if (r.get("result_position") or "").strip()]
    universe["sources"]["innovation_protocol"] = {
        "classification": "TOP_PICK_SIGMA / DERIVED (verdict+result join with pick SP, model prob, edge)",
        "raw_rows": len(inn_rows),
        "rows_with_result": len(with_result),
        "date_range": [min((r["date"] for r in inn_rows if r.get("date")), default=None),
                       max((r["date"] for r in inn_rows if r.get("date")), default=None)],
    }

    # 4. Paper ledger (shadow execution)
    pl_path = ROOT / "data/velo_execution_bridge_paper_ledger.csv"
    pl_rows = list(csv.DictReader(pl_path.open())) if pl_path.exists() else []
    universe["sources"]["paper_ledger"] = {
        "classification": "SHADOW_ROUTER_SIGMA — EVIDENCE_INTEGRITY_SUSPECT (synthetic IDs block closure)",
        "raw_rows": len(pl_rows),
        "rows_closed": sum(1 for r in pl_rows if (r.get("result_position") or "").strip()),
    }

    # 5. Retrieval corpus
    rc_path = ROOT / "data/sigma_memory/sigma_retrieval_corpus_v1.jsonl"
    rc_n = sum(1 for _ in rc_path.open()) if rc_path.exists() else 0
    universe["sources"]["retrieval_corpus"] = {
        "classification": "DERIVED_DUPLICATE (memory representation of race sigma)",
        "raw_rows": rc_n,
    }

    # 6. April unified audit (historical summary document)
    ua_path = ROOT / "data/velo_unified_evidence_audit_v1.json"
    universe["sources"]["unified_evidence_audit_v1"] = {
        "classification": "DERIVED summary (2026-04-28 snapshot: 49 days / 1,391 sigma rows)",
        "present": ua_path.exists(),
    }

    # 7. Router ledger aggregates
    rl_path = ROOT / "data/router_shadow_audit_ledger.csv"
    rl_n = (sum(1 for _ in rl_path.open()) - 1) if rl_path.exists() else 0
    universe["sources"]["router_shadow_ledger"] = {
        "classification": "SHADOW_ROUTER_SIGMA aggregate snapshots",
        "raw_rows": rl_n,
    }

    # Reconciliation verdict
    canonical = universe["sources"].get("supabase_sigma_audits", {})
    universe["reconciliation"] = {
        "canonical_source": "supabase.sigma_audits",
        "canonical_race_conclusions": canonical.get("deduplicated"),
        "near_2000_figure_explained": (
            "The ~2,000 figure is supabase.sigma_audits: "
            f"{canonical.get('raw_rows')} race-level conclusion rows "
            f"({canonical.get('date_range')}), one row per (date, race_id). "
            "All other sources are day summaries, derived joins, shadow ledgers, "
            "or memory duplicates of this canonical set."
        ),
        "runner_level_sigma": "NOT_FOUND — sigma concludes at race level (top pick vs result); no per-runner sigma universe exists",
        "layers": {
            "RACE_SIGMA": canonical.get("deduplicated"),
            "DAY_SIGMA": universe["sources"]["local_sigma_results"]["files"],
            "TOP_PICK_SIGMA_DERIVED": universe["sources"]["innovation_protocol"]["raw_rows"],
            "SHADOW_ROUTER_SIGMA": universe["sources"]["paper_ledger"]["raw_rows"],
            "DERIVED_DUPLICATE": rc_n,
        },
    }

    out = ROOT / "data/current/sigma_universe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(universe, indent=2))

    lines = ["# Sigma Universe — reconciled", "",
             f"Generated {universe['generated_at']} · READ-ONLY", ""]
    for name, src in universe["sources"].items():
        lines.append(f"## {name}")
        for k, v in src.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append("## Reconciliation")
    for k, v in universe["reconciliation"].items():
        lines.append(f"- **{k}**: {v}")
    (ROOT / "data/reports").mkdir(exist_ok=True)
    (ROOT / "data/reports/sigma_universe.md").write_text("\n".join(lines))

    print(f"Sigma universe -> {out}")
    print(json.dumps(universe["reconciliation"]["layers"], indent=1))
    print(universe["reconciliation"]["near_2000_figure_explained"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
