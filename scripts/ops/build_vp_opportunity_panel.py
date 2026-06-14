#!/usr/bin/env python3
"""
VP Opportunity Panel — Daily Gate Classifier
=============================================
Reads today's (or supplied) verdicts/sigma artifacts and classifies
the day as GREEN / AMBER / RED based on VP signal concentration.

This is a DRY-RUN ONLY reporting tool. It does not:
  - Change live scoring
  - Change model weights
  - Write to Supabase
  - Send Telegram
  - Enable staking rules

Evidence base: corrected row-bearing Sigma universe, May 23–Jun 13, 711 rows.

MANDATORY CAVEAT (hardcoded in every output):
  Jun 09 2026 had VP_avg=0.355 with 10 VP>=0.40 picks and produced 0 wins
  from 33 evaluated. High VP does not guarantee wins. This gate identifies
  opportunity conditions only — it is NOT a staking permission.

Usage:
    # Use today's verdicts (auto-detect date):
    PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py

    # Specify a date:
    PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py --date 2026-06-13

    # Use a specific verdicts file:
    PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py --verdicts-file data/velo_prime_verdicts_2026_06_13.json

    # Use a completed sigma results file (post-race analysis):
    PYTHONPATH=. python scripts/ops/build_vp_opportunity_panel.py --sigma-file data/sigma_results/sigma_results_2026_06_13.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERDICTS_DIR = ROOT / "data"
SIGMA_DIR = ROOT / "data" / "sigma_results"
REPORTS_DIR = ROOT / "data" / "reports"

# ── Gate thresholds (from corrected 711-row evidence) ────────────────────────
# Do not change without operator review and evidence update.
GREEN_AVG_VP_MIN = 0.35
GREEN_VP40_MIN = 5
GREEN_VP45_MIN = 2
AMBER_AVG_VP_MIN = 0.25
AMBER_VP40_MIN = 1

# Low-SR courses (OBSERVATION/CAUTION only — not hard bans)
DRAIN_COURSES = {
    "Nottingham",   # n=20, SR=10.0% — MEANINGFUL sample
    "Goodwood",     # n=12, SR=8.3%  — CAUTION
    "Catterick",    # n=7,  SR=0.0%  — OBSERVATION
    "Lingfield",    # n=19, SR=10.5% — CAUTION
    "Brighton",     # n=7,  SR=14.3% — OBSERVATION
    "Chester",      # n=7,  SR=14.3% — OBSERVATION
}

EXCELLING_COURSES = {
    "Newton Abbot", "Uttoxeter", "Fontwell", "Plumpton",
    "Chepstow", "Epsom", "Bangor-on-Dee",
}


def _load_verdicts(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("verdicts", data.get("races", []))


def _row_from_verdict(v: dict) -> dict:
    top = v.get("top", {})
    return {
        "race_id": top.get("race_id") or v.get("race_id", ""),
        "horse": top.get("horse", ""),
        "course": v.get("course", ""),
        "off": v.get("off_time", v.get("off", "")),
        "velo_prime_prob": float(top.get("velo_prime_prob") or 0),
        "sqpe_v17_prob": float(top.get("sqpe_v17_prob") or 0),
        "improvement_score": float(top.get("improvement_score") or 0),
        "market_deception_score": float(top.get("market_deception_score") or 0),
        "place_prob": float(top.get("place_prob") or 0),
        "pick_sp": None,   # not available pre-race
        "winner_sp": None,
        "outcome": None,
    }


def _row_from_sigma(r: dict) -> dict:
    return {
        "race_id": r.get("race_id", ""),
        "horse": r.get("predicted", ""),
        "course": r.get("course", ""),
        "off": r.get("off", ""),
        "velo_prime_prob": float(r.get("velo_prime_prob") or 0),
        "sqpe_v17_prob": float(r.get("sqpe_v17_prob") or 0),
        "improvement_score": float(r.get("improvement_score") or 0),
        "market_deception_score": float(r.get("market_deception_score") or 0),
        "place_prob": float(r.get("place_prob") or 0),
        "pick_sp": None,
        "winner_sp": r.get("winner_sp"),
        "outcome": r.get("outcome"),
    }


def classify_day(picks: list[dict]) -> dict:
    """
    Classify day as GREEN / AMBER / RED and compute all panel metrics.
    """
    if not picks:
        return {"label": "NO_DATA", "reason": "No picks provided"}

    vps = [p["velo_prime_prob"] for p in picks]
    avg_vp = sum(vps) / len(vps)
    med_vp = statistics.median(vps)

    n_vp30 = sum(1 for v in vps if v >= 0.30)
    n_vp40 = sum(1 for v in vps if v >= 0.40)
    n_vp45 = sum(1 for v in vps if v >= 0.45)
    n_vp50 = sum(1 for v in vps if v >= 0.50)

    courses = [p["course"] for p in picks if p.get("course")]
    drain_count = sum(1 for c in courses if c in DRAIN_COURSES)
    drain_pct = drain_count / len(courses) if courses else 0
    excelling_count = sum(1 for c in courses if c in EXCELLING_COURSES)

    # SP zone breakdown (where pick SP is known — post-race or if SP included)
    sp_vals = [p["winner_sp"] for p in picks if p.get("winner_sp") and p["winner_sp"] > 0]
    sp_in_window = sum(1 for s in sp_vals if 1.5 <= s < 4.0)
    sp_danger = sum(1 for s in sp_vals if 4.0 <= s < 6.0)
    sp_dead = sum(1 for s in sp_vals if s >= 6.0)
    sp_window_pct = sp_in_window / len(sp_vals) if sp_vals else None
    sp_dead_pct = sp_dead / len(sp_vals) if sp_vals else None

    # Gate classification
    warnings = []

    if avg_vp >= GREEN_AVG_VP_MIN and n_vp40 >= GREEN_VP40_MIN and n_vp45 >= GREEN_VP45_MIN:
        label = "GREEN"
        reason = (f"avg VP={avg_vp:.3f} (>={GREEN_AVG_VP_MIN}), "
                  f"{n_vp40} picks VP>=0.40 (>={GREEN_VP40_MIN}), "
                  f"{n_vp45} picks VP>=0.45 (>={GREEN_VP45_MIN})")
    elif avg_vp >= AMBER_AVG_VP_MIN and n_vp40 >= AMBER_VP40_MIN:
        label = "AMBER"
        reason = (f"avg VP={avg_vp:.3f} (0.25-0.35), "
                  f"{n_vp40} picks VP>=0.40 (1-4 range)")
    else:
        label = "RED"
        reason_parts = []
        if avg_vp < AMBER_AVG_VP_MIN:
            reason_parts.append(f"avg VP={avg_vp:.3f} < {AMBER_AVG_VP_MIN}")
        if n_vp40 == 0:
            reason_parts.append("zero VP>=0.40 picks")
        reason = "; ".join(reason_parts) if reason_parts else f"avg VP={avg_vp:.3f}"

    if drain_pct > 0.4:
        warnings.append(f"HIGH_DRAIN_EXPOSURE: {drain_count}/{len(courses)} picks at drain courses ({drain_pct:.0%})")
    if label == "GREEN":
        warnings.append(
            "FALSE_GREEN_POSSIBLE: Jun 09 2026 had VP_avg=0.355 / 10 VP>=0.40 picks / 0 wins from 33 — "
            "this gate is an opportunity signal, not a staking permission"
        )

    # Top picks by VP
    top10 = sorted(picks, key=lambda p: p["velo_prime_prob"], reverse=True)[:10]

    return {
        "label": label,
        "reason": reason,
        "warnings": warnings,
        "metrics": {
            "total_picks": len(picks),
            "avg_vp": round(avg_vp, 4),
            "median_vp": round(med_vp, 4),
            "n_vp30": n_vp30,
            "n_vp40": n_vp40,
            "n_vp45": n_vp45,
            "n_vp50": n_vp50,
            "vp40_pct": round(n_vp40 / len(picks), 4),
            "vp45_pct": round(n_vp45 / len(picks), 4),
            "sp_in_window_1p5_4p0_pct": round(sp_window_pct, 4) if sp_window_pct is not None else None,
            "sp_dead_zone_6plus_pct": round(sp_dead_pct, 4) if sp_dead_pct is not None else None,
            "drain_course_count": drain_count,
            "drain_course_pct": round(drain_pct, 4),
            "excelling_course_count": excelling_count,
        },
        "top10_by_vp": [
            {
                "horse": p["horse"],
                "course": p["course"],
                "off": p["off"],
                "velo_prime_prob": p["velo_prime_prob"],
                "improvement_score": p["improvement_score"],
                "market_deception_score": p["market_deception_score"],
                "outcome": p.get("outcome"),
                "winner_sp": p.get("winner_sp"),
            }
            for p in top10
        ],
        "course_mix": {c: courses.count(c) for c in sorted(set(courses))},
        "drain_courses_present": [c for c in DRAIN_COURSES if c in set(courses)],
        "excelling_courses_present": [c for c in EXCELLING_COURSES if c in set(courses)],
    }


def write_reports(target_date: str, panel: dict, picks: list[dict]):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_key = target_date.replace("-", "_")

    result = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "date": target_date,
        "panel_version": "VP_OPPORTUNITY_GATE_V1",
        "evidence_base": "corrected_row_bearing_sigma_universe_711_rows_2026_05_23_to_2026_06_13",
        "scoring_formula_changed": False,
        "supabase_written": False,
        "staking_enabled": False,
        **panel,
    }

    json_path = REPORTS_DIR / f"vp_opportunity_panel_{date_key}.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    md_lines = [
        f"# VP Opportunity Panel — {target_date}",
        "",
        f"**Gate Label: {panel['label']}**",
        "",
        f"Reason: {panel['reason']}",
        "",
    ]
    if panel["warnings"]:
        md_lines.append("## Warnings")
        for w in panel["warnings"]:
            md_lines.append(f"- {w}")
        md_lines.append("")

    m = panel["metrics"]
    md_lines += [
        "## Metrics",
        f"| Field | Value |",
        f"|---|---|",
        f"| Total picks | {m['total_picks']} |",
        f"| Avg VP | {m['avg_vp']:.4f} |",
        f"| Median VP | {m['median_vp']:.4f} |",
        f"| VP >= 0.30 | {m['n_vp30']} |",
        f"| VP >= 0.40 | {m['n_vp40']} ({m['vp40_pct']:.0%}) |",
        f"| VP >= 0.45 | {m['n_vp45']} ({m['vp45_pct']:.0%}) |",
        f"| VP >= 0.50 | {m['n_vp50']} |",
        f"| SP 1.5-4.0 window % | {m['sp_in_window_1p5_4p0_pct'] or 'N/A (pre-race)'} |",
        f"| SP 6.0+ dead zone % | {m['sp_dead_zone_6plus_pct'] or 'N/A (pre-race)'} |",
        f"| Drain course picks | {m['drain_course_count']} ({m['drain_course_pct']:.0%}) |",
        f"| Excelling course picks | {m['excelling_course_count']} |",
        "",
        "## Top 10 Picks by VP",
        "| Horse | Course | Off | VP | Improve | MDS | Outcome |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in panel["top10_by_vp"]:
        outcome = p.get("outcome") or "-"
        md_lines.append(
            f"| {p['horse']} | {p['course']} | {p['off']} "
            f"| {p['velo_prime_prob']:.4f} | {p['improvement_score']:.4f} "
            f"| {p['market_deception_score']:.4f} | {outcome} |"
        )

    md_lines += [
        "",
        "## Course Mix",
        "| Course | Count | Drain? |",
        "|---|---|---|",
    ]
    for c, cnt in sorted(panel["course_mix"].items(), key=lambda x: -x[1]):
        drain = "DRAIN" if c in DRAIN_COURSES else ("EXCELLING" if c in EXCELLING_COURSES else "")
        md_lines.append(f"| {c} | {cnt} | {drain} |")

    md_lines += [
        "",
        "---",
        "",
        "## Gate Rules (VP_OPPORTUNITY_GATE_V1)",
        "| Label | Criteria |",
        "|---|---|",
        f"| GREEN | avg VP >= {GREEN_AVG_VP_MIN}, VP40 count >= {GREEN_VP40_MIN}, VP45 count >= {GREEN_VP45_MIN} |",
        f"| AMBER | avg VP >= {AMBER_AVG_VP_MIN}, VP40 count >= {AMBER_VP40_MIN} |",
        "| RED | avg VP < 0.25 OR zero VP>=0.40 picks |",
        "",
        "**Evidence base**: corrected row-bearing Sigma universe, 711 rows, May 23–Jun 13.",
        "**Supabase written**: NO | **Live scoring changed**: NO | **Staking enabled**: NO",
    ]

    md_path = REPORTS_DIR / f"vp_opportunity_panel_{date_key}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Overwrite latest
    (REPORTS_DIR / "vp_opportunity_panel_latest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (REPORTS_DIR / "vp_opportunity_panel_latest.md").write_text(
        "\n".join(md_lines), encoding="utf-8"
    )

    print(f"  Panel: {panel['label']}")
    print(f"  Reason: {panel['reason']}")
    for w in panel["warnings"]:
        print(f"  [WARN] {w}")
    print(f"  Written: {json_path.name}, {md_path.name}, *_latest.*")


def main():
    parser = argparse.ArgumentParser(description="VP Opportunity Panel — daily gate classifier")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--verdicts-file", type=str, default=None, help="Path to verdicts JSON")
    parser.add_argument("--sigma-file", type=str, default=None, help="Path to sigma results JSON")
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()
    date_key = target_date.replace("-", "_")

    picks = []

    if args.sigma_file:
        sigma_path = Path(args.sigma_file)
        data = json.loads(sigma_path.read_text(encoding="utf-8"))
        rows = data.get("rows", [])
        if not rows:
            print(f"[WARN] Sigma file has no rows[] — cannot build panel from aggregate-only artifact")
        picks = [_row_from_sigma(r) for r in rows]
        print(f"Loaded {len(picks)} picks from sigma file: {sigma_path.name}")

    elif args.verdicts_file:
        vpath = Path(args.verdicts_file)
        verdicts = _load_verdicts(vpath)
        picks = [_row_from_verdict(v) for v in verdicts]
        print(f"Loaded {len(picks)} picks from verdicts file: {vpath.name}")

    else:
        # Auto-detect: try sigma first (post-race), then verdicts (pre-race)
        sigma_path = SIGMA_DIR / f"sigma_results_{date_key}.json"
        verdict_path = VERDICTS_DIR / f"velo_prime_verdicts_{date_key}.json"

        if sigma_path.exists():
            data = json.loads(sigma_path.read_text(encoding="utf-8"))
            rows = data.get("rows", [])
            if rows:
                picks = [_row_from_sigma(r) for r in rows]
                print(f"Auto: loaded {len(picks)} picks from sigma ({sigma_path.name})")
            else:
                print(f"[WARN] Sigma file exists but has no rows[]. Trying verdicts.")

        if not picks and verdict_path.exists():
            verdicts = _load_verdicts(verdict_path)
            picks = [_row_from_verdict(v) for v in verdicts]
            print(f"Auto: loaded {len(picks)} picks from verdicts ({verdict_path.name})")

        if not picks:
            print(f"[ERROR] No data found for {target_date}. "
                  f"Expected: {sigma_path} or {verdict_path}")
            return 1

    panel = classify_day(picks)
    write_reports(target_date, panel, picks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
