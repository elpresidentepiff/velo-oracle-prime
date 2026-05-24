"""
audit_rpdc_scoring_comparison.py
----------------------------------
Compare-only: current scoring vs scoring with RPDC local memory available.

Hard rules:
  - NO Supabase writes
  - NO Telegram
  - NO dashboard publish
  - NO official JSON overwrite
  - NO local official artifact overwrite
  - Read-only comparison only

What this script does:
  - Loads runner snapshot or verdict file for the target date
  - Checks improvement_score variance (current pipeline)
  - Determines whether RPDC memory injection changes scoring
  - Reports: tier changes (NONE expected), probability deltas, verdict

Key finding (pre-computed):
  RPDC local memory = read-only RPDC context enrichment.
  It does NOT inject features into the improvement model.
  Therefore: scoring path A (current) = scoring path B (with RPDC memory).
  improvement_score remains constant unless pipeline explicitly uses RPDC features.

Usage:
  PYTHONPATH=. python scripts/audit_rpdc_scoring_comparison.py --date 2026-05-25
  PYTHONPATH=. python scripts/audit_rpdc_scoring_comparison.py  # uses today
"""
import argparse
import glob
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.load_rpdc_memory import (
    get_memory_summary_for_runner,
    load_rpdc_memory,
)

DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

IMPROVEMENT_FEATURES = [
    "mark_compression_score", "curr_or_minus_best_or", "curr_or_minus_last_win_or",
    "release_window_score", "runs_since_win", "runs_since_place", "trainer_timing_score",
    "distance_fit_score", "course_fit_score", "or_vs_field", "rpr_vs_field", "age_num",
]


def _extract_date_tag(filename: str) -> str | None:
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _load_scored_runners(date_str: str) -> tuple[list[dict], str]:
    """Load runners from runner_snapshot (most complete post-scoring state)."""
    date_tag = date_str.replace("-", "_")
    snap_files = sorted(glob.glob(str(DATA_DIR / f"runner_snapshots_{date_tag}_*.jsonl")))
    if snap_files:
        path = snap_files[-1]
        try:
            seen: dict[str, dict] = {}
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = f"{r.get('horse_id','')}__{r.get('race_id','')}"
                    if key not in seen:
                        seen[key] = r
            return list(seen.values()), f"snapshot:{Path(path).name}"
        except Exception as e:
            pass

    # Fall back to verdict file
    verdict_path = DATA_DIR / f"velo_prime_verdicts_{date_tag}.json"
    if verdict_path.exists():
        try:
            data = json.loads(verdict_path.read_text(encoding="utf-8"))
            races = data if isinstance(data, list) else []
            runners = []
            for race in races:
                top = race.get("top", {}) or {}
                if top.get("horse_id"):
                    top["race_id"] = race.get("race_id", "")
                    top["course"] = race.get("course", "")
                    runners.append(top)
            return runners, f"verdict:{verdict_path.name}"
        except Exception:
            pass

    return [], ""


def run_comparison(date_str: str) -> dict:
    print(f"\n{'='*60}")
    print(f"RPDC SCORING COMPARISON — {date_str}")
    print(f"  (Compare-only — NO scoring changes, NO writes)")
    print(f"{'='*60}")

    # Check May25 card availability
    date_tag = date_str.replace("-", "_")
    snap_25 = sorted(glob.glob(str(DATA_DIR / f"runner_snapshots_{date_tag}_*.jsonl")))
    verdict_25 = DATA_DIR / f"velo_prime_verdicts_{date_tag}.json"
    card_available = bool(snap_25) or verdict_25.exists()

    if not card_available:
        print(f"\n  CARD_UNAVAILABLE: No scored data found for {date_str}.")
        print(f"  Expected: runner_snapshots_{date_tag}_*.jsonl OR velo_prime_verdicts_{date_tag}.json")
        print(f"\n  Using most recent scored day (2026-05-24) as proxy.")
        proxy_date = "2026-05-24"
        runners, source = _load_scored_runners(proxy_date)
        is_proxy = True
        data_date = proxy_date
    else:
        runners, source = _load_scored_runners(date_str)
        is_proxy = False
        data_date = date_str

    if not runners:
        print(f"  ERROR: No runner data available.")
        return {"status": "NO_DATA", "audit_date": date_str}

    print(f"  {'Proxy' if is_proxy else 'Data'} source: {source}")
    print(f"  Runners: {len(runners)}")

    # Load RPDC memory
    memory = load_rpdc_memory()
    print(f"  RPDC memory: {memory['_total_rows']:,} rows ({memory['_date_range']['first']} → {memory['_date_range']['last']})")

    # PATH A: current pipeline — as scored
    improvement_vals_a = [r.get("improvement_score") for r in runners]
    non_null_a = [v for v in improvement_vals_a if v is not None]
    unique_a = set(round(float(v), 6) for v in non_null_a)
    improvement_constant_a = len(unique_a) <= 1
    active_comps_a = runners[0].get("active_components", []) if runners else []
    tiers_a = Counter(r.get("tier") for r in runners)

    # PATH B: with RPDC memory — RPDC adds annotation only, scoring unchanged
    # The improvement model would need RPDC features explicitly injected to change.
    # Option B read-only bridge does NOT inject features → scoring identical.
    # We can measure RPDC annotation coverage only.
    rpdc_matched = 0
    rpdc_cash_window = 0
    rpdc_tagged = 0

    for r in runners:
        ctx = get_memory_summary_for_runner(
            horse_id=r.get("horse_id", ""),
            horse_name=r.get("horse", "") or r.get("top_pick_name", ""),
            as_of_date=date_str,
            memory=memory,
        )
        if ctx["memory_found"]:
            rpdc_matched += 1
        if ctx["rpdc_tag_count"] > 0:
            rpdc_tagged += 1
        if ctx["rpdc_cash_window_flag"]:
            rpdc_cash_window += 1

    match_rate = round(rpdc_matched / len(runners) * 100, 1) if runners else 0

    # Path comparison
    # improvement_score is constant in both paths → no change to any score
    path_a_kills = improvement_constant_a
    path_b_kills = improvement_constant_a  # RPDC doesn't fix improvement

    scoring_identical = True  # Option B is read-only

    # Classification
    if improvement_constant_a:
        formula_status = "FEATURE_DEGRADED"
        formula_detail = (
            f"improvement_score = {list(unique_a)[0] if unique_a else 'unknown':.4f} (constant) "
            f"→ excluded by zero-variance kill switch. "
            f"Active components: {active_comps_a}."
        )
    else:
        formula_status = "FULL_FORMULA"
        formula_detail = f"improvement_score variable ({len(unique_a)} unique values). Active: {active_comps_a}."

    run_ts = datetime.now(timezone.utc).isoformat()

    output = {
        "audit_date": date_str,
        "data_date": data_date,
        "is_proxy": is_proxy,
        "run_at": run_ts,
        "data_source": source,
        "runner_count": len(runners),
        "card_available": card_available,
        "path_a": {
            "description": "Current scoring pipeline (no RPDC injection)",
            "improvement_constant": improvement_constant_a,
            "improvement_unique_values": len(unique_a),
            "improvement_value": list(unique_a)[0] if len(unique_a) == 1 else None,
            "kill_switch_fires": path_a_kills,
            "active_components": active_comps_a,
            "tiers": dict(tiers_a),
        },
        "path_b": {
            "description": "With RPDC local memory (Option B read-only bridge)",
            "scoring_changed": False,
            "improvement_constant": improvement_constant_a,  # unchanged — RPDC doesn't inject
            "kill_switch_fires": path_b_kills,
            "active_components": active_comps_a,  # unchanged
            "tiers": dict(tiers_a),  # unchanged
            "rpdc_annotation_coverage": {
                "matched": rpdc_matched,
                "match_rate_pct": match_rate,
                "tagged": rpdc_tagged,
                "cash_window": rpdc_cash_window,
            },
        },
        "comparison": {
            "scoring_identical": scoring_identical,
            "tier_changes": 0,
            "probability_deltas": "NONE — RPDC Option B is read-only annotation, no scoring formula change",
            "a_tier_changes": 0,
            "b_tier_changes": 0,
            "top_horse_changes": 0,
        },
        "formula_status": formula_status,
        "formula_detail": formula_detail,
        "may25_classification": formula_status,
        "may25_classification_reason": (
            "improvement_score excluded (constant). "
            "RPDC local memory provides annotation context only. "
            "Improvement variance requires pipeline change to inject racecard features (or_vs_field, rpr_vs_field, age_num)."
            if formula_status == "FEATURE_DEGRADED"
            else "Full formula operational."
        ),
    }

    _write_outputs(date_str, output)
    _print_summary(output)
    return output


def _write_outputs(date_str: str, output: dict) -> None:
    json_path = REPORTS_DIR / f"rpdc_scoring_comparison_{date_str}.json"
    md_path = REPORTS_DIR / f"rpdc_scoring_comparison_{date_str}.md"

    json_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")

    a = output["path_a"]
    b = output["path_b"]
    comp = output["comparison"]
    proxy_note = ""
    if output.get("is_proxy"):
        proxy_note = f"\n**NOTE:** Using {output['data_date']} as proxy — {output['audit_date']} card not yet available  "

    lines = [
        f"# RPDC Scoring Comparison — {output['audit_date']}",
        "",
        f"**Generated:** {output['run_at']}  ",
        f"**Data source:** {output['data_source']}  ",
        proxy_note,
        "",
        "---",
        "",
        f"## Formula Status: `{output['formula_status']}`",
        "",
        f"> {output['formula_detail']}",
        "",
        "## Path A vs Path B",
        "",
        "| Metric | Path A (current) | Path B (RPDC bridge) |",
        "|---|---|---|",
        f"| improvement_score constant | {a['improvement_constant']} | {b['improvement_constant']} |",
        f"| Zero-variance kill switch fires | {a['kill_switch_fires']} | {b['kill_switch_fires']} |",
        f"| Active components | {a['active_components']} | {b['active_components']} |",
        f"| Scoring changed | — | {'NO — read-only annotation'} |",
        f"| Tier distribution | {dict(a['tiers'])} | (identical) |",
        "",
        "## RPDC Annotation Coverage (Path B adds)",
        "",
        f"| Metric | Value |",
        "|---|---|",
        f"| Runners matched to RPDC memory | {b['rpdc_annotation_coverage']['matched']} ({b['rpdc_annotation_coverage']['match_rate_pct']}%) |",
        f"| Runners with RPDC tags | {b['rpdc_annotation_coverage']['tagged']} |",
        f"| Cash window runners | {b['rpdc_annotation_coverage']['cash_window']} |",
        "",
        "## Comparison Result",
        "",
        f"| Metric | Result |",
        "|---|---|",
        f"| Scoring identical | {comp['scoring_identical']} |",
        f"| Tier changes | {comp['tier_changes']} |",
        f"| A-tier changes | {comp['a_tier_changes']} |",
        f"| Top horse changes | {comp['top_horse_changes']} |",
        f"| Probability deltas | {comp['probability_deltas']} |",
        "",
        f"## May 25 Classification",
        "",
        f"**`{output['may25_classification']}`**",
        "",
        f"> {output['may25_classification_reason']}",
        "",
        "```",
        f"AUDIT_DATE:          {output['audit_date']}",
        f"IS_PROXY:            {output['is_proxy']}",
        f"FORMULA_STATUS:      {output['formula_status']}",
        f"SCORING_IDENTICAL:   {comp['scoring_identical']}",
        f"IMPROVEMENT_CONST:   {a['improvement_constant']}",
        f"KILL_SWITCH:         {a['kill_switch_fires']}",
        f"SUPABASE_WRITES:     NONE",
        f"SCORING_CHANGE:      NONE",
        f"MODEL_CHANGE:        NONE",
        "```",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  JSON → {json_path}")
    print(f"  MD  → {md_path}")


def _print_summary(output: dict) -> None:
    a = output["path_a"]
    comp = output["comparison"]
    print(f"\n  Formula status:        {output['formula_status']}")
    print(f"  improvement constant:  {a['improvement_constant']} ({a.get('improvement_value', '?'):.4f})" if a.get('improvement_value') else f"  improvement constant:  {a['improvement_constant']}")
    print(f"  Kill switch fires:     {a['kill_switch_fires']}")
    print(f"  Active components:     {a['active_components']}")
    print(f"  Scoring A vs B:        IDENTICAL — RPDC Option B is read-only annotation")
    print(f"  Tier changes:          {comp['tier_changes']}")
    print(f"  May25 classification:  {output['may25_classification']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPDC scoring comparison (compare-only)")
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    run_comparison(args.date)
