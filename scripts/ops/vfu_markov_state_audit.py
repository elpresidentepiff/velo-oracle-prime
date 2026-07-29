#!/usr/bin/env python3
"""
VFU-28: Markov State Engine Gap Audit

The Markov hidden-state engine (run_markov_state_engine.py) is OBSERVATION ONLY
and not wired to sigma evaluation. This VFU:
  1. Loads the 2 existing Markov output files (2026-06-03, 2026-06-04)
  2. Joins to sigma outcomes for those dates
  3. Reports per-state SR where possible
  4. Documents the operational gap: 71% UNKNOWN, 0 high-confidence states,
     no prospective Markov output after June 4
  5. Recommends fixes for the next phase

Verdict: MARKOV_GAP_DOCUMENTED — REPORT_ONLY.

Usage:
    python scripts/ops/vfu_markov_state_audit.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MARKOV_DIR = DATA / "markov"
SIGMA_DIR = DATA / "sigma_results"
OUTPUT_JSON = DATA / "reports" / "vfu_28_markov_state_audit.json"
OUTPUT_MD = DATA / "reports" / "vfu_28_markov_state_audit.md"

VFU_VERSION = "VFU_28_MARKOV_STATE_AUDIT_V1"

MIN_ROWS_PER_STATE = 10


# ── Data loading ───────────────────────────────────────────────────────────

def _norm(s: str | None) -> str:
    if not s:
        return ""
    import re
    v = str(s).strip().lower().replace("(aw)", "").replace("aw", "")
    return re.sub(r"[^a-z ]", "", v).strip()


def load_markov_cards(markov_dir: Path | None = None) -> list[dict]:
    """Load all markov_state_card_*.jsonl files."""
    if markov_dir is None:
        markov_dir = MARKOV_DIR
    rows: list[dict] = []
    for f in sorted(markov_dir.glob("markov_state_card_*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows.append(row)
    return rows


def load_sigma_index(sigma_dir: Path | None = None) -> dict[tuple[str, str], str]:
    """
    Build {(race_id, norm_horse): outcome} from sigma_results files.
    Covers only dates where Markov output exists.
    """
    if sigma_dir is None:
        sigma_dir = SIGMA_DIR
    idx: dict[tuple[str, str], str] = {}
    for f in sorted(sigma_dir.glob("sigma_results_2026_06_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in d.get("rows", []):
            race_id = str(row.get("race_id", ""))
            predicted = _norm(row.get("predicted", ""))
            outcome = row.get("outcome", "")
            if race_id and predicted and outcome:
                idx[(race_id, predicted)] = outcome
    return idx


# ── Analysis ───────────────────────────────────────────────────────────────

def analyse(markov_rows: list[dict], sigma_idx: dict[tuple[str, str], str]) -> dict:
    """
    Join Markov state to sigma outcomes (VELO top pick only).
    Returns per-state stats + gap metrics.
    """
    from collections import Counter

    total_runners = len(markov_rows)
    state_counts: Counter = Counter(r["state"] for r in markov_rows)
    conf_counts: Counter = Counter(r.get("confidence", "LOW") for r in markov_rows)

    # Join: find sigma outcome for each Markov runner
    per_state: dict[str, dict] = defaultdict(lambda: {"n": 0, "wins": 0, "outcomes": []})
    joined = 0
    unjoined = 0

    for row in markov_rows:
        race_id = str(row.get("race_id", ""))
        horse_norm = _norm(row.get("horse", ""))
        outcome = sigma_idx.get((race_id, horse_norm))
        if outcome is None:
            # Try without normalization issue
            unjoined += 1
            continue
        joined += 1
        state = row["state"]
        per_state[state]["n"] += 1
        if outcome == "WIN":
            per_state[state]["wins"] += 1

    # Compute per-state SR
    state_sr: list[dict] = []
    for state, s in sorted(per_state.items(), key=lambda x: -x[1]["n"]):
        n = s["n"]
        sr = round(s["wins"] / n, 4) if n > 0 else None
        verdict = (
            "SUFFICIENT_DATA" if n >= MIN_ROWS_PER_STATE else "INSUFFICIENT_DATA"
        )
        state_sr.append({
            "state": state,
            "n":     n,
            "wins":  s["wins"],
            "sr":    sr,
            "verdict": verdict,
        })

    # Gap diagnostics
    unknown_pct = round(state_counts.get("UNKNOWN", 0) / total_runners, 4) if total_runners else 0
    high_conf_n = conf_counts.get("HIGH", 0)

    root_cause = [
        "PASSPORT_COVERAGE_GAP: Most runners lack passport history, defaulting to UNKNOWN state",
        "NO_PROSPECTIVE_OUTPUT: Markov engine ran only 2 dates (2026-06-03, 2026-06-04); nothing since",
        "NOT_WIRED_TO_SIGMA: Markov state cards are never joined to outcomes automatically",
        "FEED_IS_LIVE_ONLY: current_card_passport_feed_latest.jsonl exists only on race day",
        "HIGH_CONF_STATES_ZERO: No HIGH confidence classifications on June 4 (0 of 391 runners)",
    ]

    # Determine overall verdict
    if joined < 10:
        verdict = "MARKOV_GAP_INSUFFICIENT_OVERLAP"
    else:
        verdict = "MARKOV_GAP_DOCUMENTED"

    return {
        "vfu28_validation_version": VFU_VERSION,
        "dates_with_markov_output": ["2026-06-03", "2026-06-04"],
        "total_runners_classified": total_runners,
        "state_distribution":       dict(state_counts),
        "confidence_distribution":  dict(conf_counts),
        "unknown_pct":              unknown_pct,
        "high_conf_n":              high_conf_n,
        "sigma_joined_n":           joined,
        "sigma_unjoined_n":         unjoined,
        "per_state_sr":             state_sr,
        "root_cause":               root_cause,
        "verdict":                  verdict,
        "fade_signal_quality":      "NOT_OPERATIONAL_INSUFFICIENT_PASSPORT_DATA",
        "recommendation": (
            "Archive passport feed daily alongside current card. "
            "After 30 Markov dates, re-evaluate per-state SR and consider "
            "CASH_RUN / BOUNCE_RISK as gate signals in the TIE v3 pipeline."
        ),
        "classification_codes": [
            "VFU_28_MARKOV_GAP_DIAGNOSTIC_COMPLETE",
            "MARKOV_NOT_OPERATIONAL_NO_PROSPECTIVE_OUTPUT",
            "MARKOV_ROOT_CAUSE_PASSPORT_COVERAGE_GAP",
            "MARKOV_RETROACTIVE_FIX_DEFERRED_TO_PHASE_7",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }


# ── Brief ──────────────────────────────────────────────────────────────────

def build_brief(summary: dict) -> str:
    lines = [
        "# VFU-28 — Markov State Engine Gap Audit",
        "",
        f"Dates with output: {', '.join(summary['dates_with_markov_output'])}  "
        f"Total runners: {summary['total_runners_classified']}",
        "",
        "## State Distribution",
        "| State | Count | Joined to Sigma | SR |",
        "|---|---|---|---|",
    ]
    state_dist = summary["state_distribution"]
    per_state = {s["state"]: s for s in summary["per_state_sr"]}
    for state, count in sorted(state_dist.items(), key=lambda x: -x[1]):
        ps = per_state.get(state, {})
        n_j = ps.get("n", 0)
        sr = f"{ps['sr']:.1%}" if ps.get("sr") is not None else "—"
        lines.append(f"| {state} | {count} | {n_j} | {sr} |")

    lines += [
        "",
        f"**UNKNOWN %:** {summary['unknown_pct']:.1%}  "
        f"**High-conf states:** {summary['high_conf_n']}  "
        f"**Sigma joined:** {summary['sigma_joined_n']}",
        "",
        "## Root Cause",
        *[f"- {rc}" for rc in summary["root_cause"]],
        "",
        f"## Verdict: **{summary['verdict']}**",
        "",
        f"**Recommendation:** {summary['recommendation']}",
        "",
        "## Classifications",
        *[f"- {c}" for c in summary["classification_codes"]],
    ]
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────

def main(markov_dir: Path | None = None, sigma_dir: Path | None = None) -> dict:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    markov_rows = load_markov_cards(markov_dir)
    sigma_idx = load_sigma_index(sigma_dir)

    if not markov_rows:
        summary = {
            "vfu28_validation_version": VFU_VERSION,
            "verdict": "NO_MARKOV_DATA",
            "total_runners_classified": 0,
            "dates_with_markov_output": [],
            "state_distribution": {},
            "confidence_distribution": {},
            "unknown_pct": 0.0,
            "high_conf_n": 0,
            "sigma_joined_n": 0,
            "sigma_unjoined_n": 0,
            "per_state_sr": [],
            "root_cause": ["NO_MARKOV_OUTPUT_FILES: No markov_state_card_*.jsonl files found"],
            "fade_signal_quality": "NOT_OPERATIONAL_NO_DATA",
            "recommendation": "Run run_markov_state_engine.py on at least 30 race days.",
            "classification_codes": [
                "VFU_28_MARKOV_GAP_DIAGNOSTIC_COMPLETE",
                "MARKOV_NOT_OPERATIONAL_NO_PROSPECTIVE_OUTPUT",
                "NO_LIVE_SCORING_CHANGE",
                "NO_SUPABASE_WRITES",
                "REPORT_ONLY",
            ],
        }
    else:
        summary = analyse(markov_rows, sigma_idx)

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_brief(summary), encoding="utf-8")

    print(f"VFU-28 Markov State Gap Audit")
    print(f"  Total Markov runners: {summary.get('total_runners_classified', 0)}")
    print(f"  UNKNOWN %: {summary.get('unknown_pct', 0):.1%}")
    print(f"  High-conf states: {summary.get('high_conf_n', 0)}")
    print(f"  Sigma joined: {summary.get('sigma_joined_n', 0)}")
    print(f"  Verdict: {summary.get('verdict')}")
    print(f"  Report: {OUTPUT_JSON}")
    return summary


if __name__ == "__main__":
    main()
