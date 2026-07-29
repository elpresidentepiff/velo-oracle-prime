#!/usr/bin/env python3
"""
VFU-27: Extended Elo Signal Audit

Rebuilds the sidecar Elo tournament using verdict files + sigma_results (1,746 rows),
vs the original 69-race run from sigma_memory.

Sidecars:
  improvement_score          threshold >0.30 (top field)
  market_deception_score     threshold >0.30 (top field)
  place_prob                 threshold >0.50 (top field)
  comment_intel_score        threshold >0.50 (top field — new)

Verdict: REPORT_ONLY, NO_LIVE_SCORING_CHANGE, NO_SUPABASE_WRITES.

Usage:
    python scripts/ops/vfu_elo_signal_audit.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SIGMA_DIR = DATA / "sigma_results"
OUTPUT_JSON = DATA / "reports" / "vfu_27_elo_signal_audit.json"
OUTPUT_MD = DATA / "reports" / "vfu_27_elo_signal_audit.md"

VFU_VERSION = "VFU_27_ELO_SIGNAL_AUDIT_V1"

# ── Sidecar config ─────────────────────────────────────────────────────────
SIDECARS: dict[str, dict] = {
    "improvement_score":       {"field": "improvement_score",       "threshold": 0.30},
    "market_deception_score":  {"field": "market_deception_score",  "threshold": 0.30},
    "place_prob":              {"field": "place_prob",              "threshold": 0.50},
    "comment_intel_score":     {"field": "comment_intel_score",     "threshold": 0.50},
}

# Elo constants (same as original run_sidecar_elo.py)
STARTING_ELO = 1000
K_CORRECT   =  32
K_INCORRECT = -32
K_MISSED    =  -8

# Baseline from the original 69-race run (June 2026)
BASELINE_69 = {
    "market_deception_score": 1040,
    "improvement_score":       848,
    "new_build_agreed":        840,
    "place_prob":              824,
}

MIN_FIRES_FOR_VERDICT = 20


# ── Data loading ───────────────────────────────────────────────────────────

def load_verdict_index(data_dir: Path | None = None) -> dict[str, dict]:
    """Build {race_id: top_dict} from all verdict files."""
    if data_dir is None:
        data_dir = DATA
    idx: dict[str, dict] = {}
    for f in sorted(data_dir.glob("velo_prime_verdicts_*.json")):
        try:
            races = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for race in races:
            top = race.get("top")
            if top and top.get("race_id"):
                idx[str(top["race_id"])] = top
    return idx


def load_sigma_rows(cutoff: str, through: str, sigma_dir: Path | None = None) -> list[dict]:
    """Load sigma rows between cutoff and through (inclusive, YYYY-MM-DD)."""
    if sigma_dir is None:
        sigma_dir = SIGMA_DIR
    d0 = date.fromisoformat(cutoff)
    d1 = date.fromisoformat(through)
    rows: list[dict] = []
    for f in sorted(sigma_dir.glob("sigma_results_*.json")):
        stem = f.stem  # sigma_results_2026_07_05
        parts = stem.split("_")
        if len(parts) < 4:
            continue
        try:
            file_date = date(int(parts[2]), int(parts[3]), int(parts[4]))
        except (ValueError, IndexError):
            continue
        if not (d0 <= file_date <= d1):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in d.get("rows", []):
            row["_date"] = file_date.isoformat()
            rows.append(row)
    return rows


# ── Elo evaluation ─────────────────────────────────────────────────────────

def _fired(top: dict, sidecar_key: str) -> bool:
    cfg = SIDECARS[sidecar_key]
    val = top.get(cfg["field"])
    if val is None:
        return False
    try:
        return float(val) > cfg["threshold"]
    except (ValueError, TypeError):
        return False


def run_tournament(sigma_rows: list[dict], verdict_idx: dict[str, dict]) -> dict:
    """
    Run the Elo tournament. Returns per-sidecar stats and ledger.

    Each sigma row = one race's top pick result.
    """
    stats: dict[str, dict] = {
        k: {"n_fired": 0, "n_correct": 0, "n_missed": 0, "n_no_fire_win": 0, "elo": STARTING_ELO}
        for k in SIDECARS
    }
    ledger: list[dict] = []
    n_enriched = 0
    n_no_verdict = 0

    for row in sigma_rows:
        race_id = str(row.get("race_id", ""))
        top = verdict_idx.get(race_id)
        if top is None:
            n_no_verdict += 1
            continue
        n_enriched += 1

        is_win = row.get("outcome") == "WIN"

        for skey in SIDECARS:
            fired = _fired(top, skey)
            elo_change = 0
            event = ""

            if fired:
                stats[skey]["n_fired"] += 1
                if is_win:
                    stats[skey]["n_correct"] += 1
                    elo_change = K_CORRECT
                    event = "CORRECT_FIRE"
                else:
                    stats[skey]["n_missed"] += 1
                    elo_change = K_INCORRECT
                    event = "INCORRECT_FIRE"
            else:
                if is_win:
                    stats[skey]["n_no_fire_win"] += 1
                    elo_change = K_MISSED
                    event = "MISSED_WINNER"
                else:
                    event = "NO_FIRE"

            stats[skey]["elo"] += elo_change
            ledger.append({
                "race_id": race_id,
                "date": row.get("_date"),
                "sidecar": skey,
                "event": event,
                "elo_change": elo_change,
                "new_elo": stats[skey]["elo"],
            })

    return {
        "stats": stats,
        "ledger": ledger,
        "n_rows": len(sigma_rows),
        "n_enriched": n_enriched,
        "n_no_verdict": n_no_verdict,
    }


# ── Analysis ───────────────────────────────────────────────────────────────

def analyse(result: dict) -> dict:
    stats = result["stats"]
    n_enriched = result["n_enriched"]

    rankings: list[dict] = []
    for skey, s in stats.items():
        n_f = s["n_fired"]
        sr = round(s["n_correct"] / n_f, 4) if n_f > 0 else None
        fire_rate = round(n_f / n_enriched, 4) if n_enriched > 0 else None

        if n_f < MIN_FIRES_FOR_VERDICT:
            verdict = "INSUFFICIENT_FIRES"
        elif sr is None:
            verdict = "INSUFFICIENT_FIRES"
        elif sr >= 0.45:
            verdict = "ELO_SIGNAL_STRONG"
        elif sr >= 0.35:
            verdict = "ELO_SIGNAL_MODERATE"
        else:
            verdict = "ELO_SIGNAL_WEAK"

        baseline_elo = BASELINE_69.get(skey)
        elo_drift = s["elo"] - baseline_elo if baseline_elo is not None else None

        rankings.append({
            "sidecar":         skey,
            "elo":             s["elo"],
            "baseline_elo":    baseline_elo,
            "elo_drift":       elo_drift,
            "n_fired":         n_f,
            "n_correct":       s["n_correct"],
            "n_missed":        s["n_missed"],
            "n_no_fire_win":   s["n_no_fire_win"],
            "strike_rate":     sr,
            "fire_rate":       fire_rate,
            "verdict":         verdict,
        })

    rankings.sort(key=lambda x: x["elo"], reverse=True)

    return {
        "vfu27_validation_version": VFU_VERSION,
        "n_sigma_rows":             result["n_rows"],
        "n_enriched":               n_enriched,
        "n_no_verdict":             result["n_no_verdict"],
        "baseline_n_races":         69,
        "rankings":                 rankings,
        "classification_codes": [
            "VFU_27_ELO_SIGNAL_AUDIT_COMPLETE",
            "ELO_TOURNAMENT_EXTENDED_1700_PLUS_ROWS",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }


# ── Brief ──────────────────────────────────────────────────────────────────

def build_brief(summary: dict) -> str:
    lines = [
        "# VFU-27 — Extended Elo Signal Audit",
        "",
        f"Sigma rows: {summary['n_sigma_rows']}  "
        f"Enriched: {summary['n_enriched']}  "
        f"Baseline was: {summary['baseline_n_races']} races",
        "",
        "| Rank | Sidecar | Elo | Baseline | Drift | Fires | Correct | SR | Verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(summary["rankings"], 1):
        drift = f"{r['elo_drift']:+d}" if r["elo_drift"] is not None else "—"
        sr = f"{r['strike_rate']:.1%}" if r["strike_rate"] is not None else "—"
        lines.append(
            f"| {i} | **{r['sidecar']}** | {r['elo']} | {r['baseline_elo'] or '—'} "
            f"| {drift} | {r['n_fired']} | {r['n_correct']} | {sr} | {r['verdict']} |"
        )
    lines += [
        "",
        "## Classifications",
        *[f"- {c}" for c in summary["classification_codes"]],
    ]
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────

def main(
    cutoff: str = "2026-03-17",
    through: str = "2026-07-27",
    data_dir: Path | None = None,
    sigma_dir: Path | None = None,
) -> dict:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    verdict_idx = load_verdict_index(data_dir)
    sigma_rows = load_sigma_rows(cutoff, through, sigma_dir)

    result = run_tournament(sigma_rows, verdict_idx)
    summary = analyse(result)

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_brief(summary), encoding="utf-8")

    print(f"VFU-27 Elo Signal Audit ({cutoff} → {through})")
    print(f"  Sigma rows: {summary['n_sigma_rows']}  Enriched: {summary['n_enriched']}")
    for r in summary["rankings"]:
        dr = f"{r['elo_drift']:+d}" if r["elo_drift"] is not None else "n/a"
        sr_s = f"{r['strike_rate']:.1%}" if r["strike_rate"] is not None else "—"
        print(f"  {r['sidecar']:<28} Elo={r['elo']:5d} drift={dr:>5}  fires={r['n_fired']:4d}  SR={sr_s}  [{r['verdict']}]")
    print(f"  Report: {OUTPUT_JSON}")
    return summary


if __name__ == "__main__":
    main()
