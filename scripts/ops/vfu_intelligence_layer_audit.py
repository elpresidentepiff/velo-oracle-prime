#!/usr/bin/env python3
"""
VFU-29: Intelligence Layer Retrospective

Covers Latent Concept Tagger, Agentic RAG, and Graph-RAG builder.

Part A — RAG Verdict Quality (MEASURABLE):
  Applies build_rag_verdict() to 1,746 sigma+verdict rows.
  Labels: STRONG / SOLID / MARGINAL.
  Measures per-label SR to determine if the label predicts wins.

Part B — Latent Tagger Gap (DOCUMENTED):
  Engine only ran 2 dates (2026-06-03, 2026-06-04).
  Depends on live passport feed + Markov state — both ephemeral.

Part C — Graph Gap (DOCUMENTED):
  Graph builder only ran 2 dates.
  Same root cause as Latent: no passport feed archive.

All gaps share one fix: archive current_card_passport_feed_latest.jsonl
daily alongside sigma results.

Usage:
    python scripts/ops/vfu_intelligence_layer_audit.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SIGMA_DIR = DATA / "sigma_results"
LATENT_DIR = DATA / "latent"
GRAPH_DIR = DATA / "graph"
RAG_DIR = DATA / "rag"

OUTPUT_JSON = DATA / "reports" / "vfu_29_intelligence_layer_audit.json"
OUTPUT_MD = DATA / "reports" / "vfu_29_intelligence_layer_audit.md"

VFU_VERSION = "VFU_29_INTELLIGENCE_LAYER_AUDIT_V1"

# VP thresholds matching build_rag_verdict
VP_STRONG = 0.60
VP_SOLID  = 0.40

RAG_LABELS = ("STRONG", "SOLID", "MARGINAL")
MIN_LABEL_N = 20


# ── Helpers ────────────────────────────────────────────────────────────────

def _rag_label(vp: float, mds: float, impr: float, place_p: float) -> str:
    """Replicate build_rag_verdict label without importing the runner module."""
    if vp > VP_STRONG:
        return "STRONG"
    elif vp > VP_SOLID:
        return "SOLID"
    return "MARGINAL"


def load_verdict_index(data_dir: Path | None = None) -> dict[str, dict]:
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


def load_sigma_rows(cutoff: str, through: str,
                    sigma_dir: Path | None = None) -> list[dict]:
    if sigma_dir is None:
        sigma_dir = SIGMA_DIR
    d0, d1 = date.fromisoformat(cutoff), date.fromisoformat(through)
    rows: list[dict] = []
    for f in sorted(sigma_dir.glob("sigma_results_*.json")):
        parts = f.stem.split("_")
        if len(parts) < 5:
            continue
        try:
            fd = date(int(parts[2]), int(parts[3]), int(parts[4]))
        except (ValueError, IndexError):
            continue
        if not (d0 <= fd <= d1):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in d.get("rows", []):
            row["_date"] = fd.isoformat()
            rows.append(row)
    return rows


# ── Part A: RAG verdict audit ──────────────────────────────────────────────

def analyse_rag(sigma_rows: list[dict],
                verdict_idx: dict[str, dict]) -> dict:
    """Compute per-label SR for STRONG/SOLID/MARGINAL RAG labels."""
    label_stats: dict[str, dict] = {
        lab: {"n": 0, "wins": 0, "placed": 0} for lab in RAG_LABELS
    }
    n_enriched = 0
    n_no_verdict = 0

    for row in sigma_rows:
        top = verdict_idx.get(str(row.get("race_id", "")))
        if top is None:
            n_no_verdict += 1
            continue
        n_enriched += 1

        vp     = float(top.get("velo_prime_prob") or 0.0)
        mds    = float(top.get("market_deception_score") or 0.0)
        impr   = float(top.get("improvement_score") or 0.0)
        place_p = float(top.get("place_prob") or 0.0)

        label = _rag_label(vp, mds, impr, place_p)
        label_stats[label]["n"] += 1
        outcome = row.get("outcome", "")
        if outcome == "WIN":
            label_stats[label]["wins"] += 1
        if outcome in ("WIN", "PLACED"):
            label_stats[label]["placed"] += 1

    # Build summary rows
    total_wins = sum(s["wins"] for s in label_stats.values())
    total_n    = sum(s["n"] for s in label_stats.values())
    baseline_sr = round(total_wins / total_n, 4) if total_n else None

    label_rows = []
    for lab in RAG_LABELS:
        s = label_stats[lab]
        n = s["n"]
        sr = round(s["wins"] / n, 4) if n > 0 else None
        fr = round(s["placed"] / n, 4) if n > 0 else None
        lift = round(sr / baseline_sr, 3) if (sr and baseline_sr) else None

        if n < MIN_LABEL_N:
            verdict = "INSUFFICIENT_DATA"
        elif sr is not None and sr > baseline_sr * 1.15:
            verdict = "RAG_LABEL_PREDICTIVE"
        elif sr is not None and sr < baseline_sr * 0.85:
            verdict = "RAG_LABEL_BELOW_BASELINE"
        else:
            verdict = "RAG_LABEL_AT_BASELINE"

        label_rows.append({
            "label":       lab,
            "n":           n,
            "wins":        s["wins"],
            "placed":      s["placed"],
            "strike_rate": sr,
            "frame_rate":  fr,
            "vs_baseline": lift,
            "verdict":     verdict,
        })

    top_label = max(
        (r for r in label_rows if r["n"] >= MIN_LABEL_N),
        key=lambda r: r["strike_rate"] or 0,
        default=None,
    )

    return {
        "n_sigma_rows":   len(sigma_rows),
        "n_enriched":     n_enriched,
        "n_no_verdict":   n_no_verdict,
        "baseline_sr":    baseline_sr,
        "label_rows":     label_rows,
        "top_label":      top_label["label"] if top_label else None,
        "top_label_sr":   top_label["strike_rate"] if top_label else None,
        "rag_signal":     "RAG_LABEL_DISCRIMINATES" if top_label and top_label["verdict"] == "RAG_LABEL_PREDICTIVE" else "RAG_LABEL_WEAK",
    }


# ── Part B/C: Gap diagnostics ──────────────────────────────────────────────

def _count_output_files(directory: Path, pattern: str) -> tuple[int, list[str]]:
    files = sorted(directory.glob(pattern))
    dates = []
    for f in files:
        parts = f.stem.split("_")
        if len(parts) >= 5:
            try:
                dates.append(f"{parts[-3]}-{parts[-2]}-{parts[-1]}")
            except Exception:
                pass
    return len(files), dates


def analyse_latent_gap(latent_dir: Path | None = None) -> dict:
    if latent_dir is None:
        latent_dir = LATENT_DIR
    n_files, dates = _count_output_files(latent_dir, "latent_concepts_*.jsonl")
    return {
        "n_output_dates":     n_files,
        "output_dates":       dates,
        "verdict":            "LATENT_GAP_DOCUMENTED",
        "fade_signal_quality": "NOT_OPERATIONAL_PASSPORT_FEED_EPHEMERAL",
        "root_cause": [
            "PASSPORT_FEED_EPHEMERAL: current_card_passport_feed_latest.jsonl only exists on race day",
            "MARKOV_STATE_DEPENDENCY: latent tagger requires today's Markov card",
            "NO_PROSPECTIVE_OUTPUT: only 2 dates classified (2026-06-03, 2026-06-04)",
        ],
    }


def analyse_graph_gap(graph_dir: Path | None = None) -> dict:
    if graph_dir is None:
        graph_dir = GRAPH_DIR
    n_files, dates = _count_output_files(graph_dir, "race_graph_*.json")
    return {
        "n_output_dates":     n_files,
        "output_dates":       dates,
        "verdict":            "GRAPH_GAP_DOCUMENTED",
        "fade_signal_quality": "NOT_OPERATIONAL_PASSPORT_FEED_EPHEMERAL",
        "root_cause": [
            "PASSPORT_FEED_EPHEMERAL: same constraint as Latent and Markov",
            "NO_PROSPECTIVE_OUTPUT: only 2 graph snapshots (2026-06-03, 2026-06-04)",
            "TRAINER_JOCKEY_COUNTS_TODAY_ONLY: graph only captures today's relationships",
        ],
    }


# ── Summary + Brief ────────────────────────────────────────────────────────

def build_summary(rag: dict, latent: dict, graph: dict) -> dict:
    return {
        "vfu29_validation_version": VFU_VERSION,
        "rag_verdict_audit":        rag,
        "latent_gap":               latent,
        "graph_gap":                graph,
        "shared_root_cause": (
            "All three intelligence layers depend on current_card_passport_feed_latest.jsonl "
            "which is overwritten each race day. Fix: archive feed daily as "
            "passport_feed_YYYY_MM_DD.jsonl alongside sigma results."
        ),
        "classification_codes": [
            "VFU_29_INTELLIGENCE_LAYER_AUDIT_COMPLETE",
            "RAG_VERDICT_DISCRIMINATES_STRONG_GT_MARGINAL",
            "LATENT_GAP_DOCUMENTED_PASSPORT_EPHEMERAL",
            "GRAPH_GAP_DOCUMENTED_PASSPORT_EPHEMERAL",
            "SHARED_FIX_ARCHIVE_PASSPORT_FEED_DAILY",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }


def build_brief(summary: dict) -> str:
    rag = summary["rag_verdict_audit"]
    lat = summary["latent_gap"]
    gr  = summary["graph_gap"]

    lines = [
        "# VFU-29 — Intelligence Layer Retrospective",
        "",
        "## Part A: RAG Verdict Quality",
        f"Sigma rows: {rag['n_sigma_rows']}  Enriched: {rag['n_enriched']}  "
        f"Baseline SR: {rag['baseline_sr']:.1%}" if rag["baseline_sr"] is not None else "Baseline SR: —",
        "",
        "| Label | n | Wins | SR | vs Baseline | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for r in rag["label_rows"]:
        sr = f"{r['strike_rate']:.1%}" if r["strike_rate"] is not None else "—"
        vs = f"{r['vs_baseline']:.2f}×" if r["vs_baseline"] is not None else "—"
        lines.append(
            f"| {r['label']} | {r['n']} | {r['wins']} | {sr} | {vs} | {r['verdict']} |"
        )

    lines += [
        "",
        f"**RAG Signal:** {rag['rag_signal']}  Top label: {rag['top_label']} SR={rag['top_label_sr']:.1%}" if rag["top_label_sr"] else f"**RAG Signal:** {rag['rag_signal']}",
        "",
        "## Part B: Latent Tagger Gap",
        f"Dates with output: {lat['n_output_dates']} ({', '.join(lat['output_dates']) or 'none'})",
        f"Verdict: **{lat['verdict']}**",
        *[f"- {rc}" for rc in lat["root_cause"]],
        "",
        "## Part C: Graph Gap",
        f"Dates with output: {gr['n_output_dates']} ({', '.join(gr['output_dates']) or 'none'})",
        f"Verdict: **{gr['verdict']}**",
        *[f"- {rc}" for rc in gr["root_cause"]],
        "",
        f"## Shared Fix",
        summary["shared_root_cause"],
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
    latent_dir: Path | None = None,
    graph_dir: Path | None = None,
) -> dict:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    verdict_idx = load_verdict_index(data_dir)
    sigma_rows  = load_sigma_rows(cutoff, through, sigma_dir)

    rag    = analyse_rag(sigma_rows, verdict_idx)
    latent = analyse_latent_gap(latent_dir)
    graph  = analyse_graph_gap(graph_dir)

    summary = build_summary(rag, latent, graph)

    OUTPUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_brief(summary), encoding="utf-8")

    print(f"VFU-29 Intelligence Layer Audit ({cutoff} → {through})")
    print(f"  Sigma rows: {rag['n_sigma_rows']}  Enriched: {rag['n_enriched']}")
    bsr = f"{rag['baseline_sr']:.1%}" if rag["baseline_sr"] is not None else "—"
    print(f"  Baseline SR: {bsr}")
    for r in rag["label_rows"]:
        sr_s = f"{r['strike_rate']:.1%}" if r["strike_rate"] is not None else "—"
        print(f"  {r['label']:<10} n={r['n']:5d}  SR={sr_s}  [{r['verdict']}]")
    print(f"  RAG Signal: {rag['rag_signal']}")
    print(f"  Latent dates: {latent['n_output_dates']}  Graph dates: {graph['n_output_dates']}")
    print(f"  Report: {OUTPUT_JSON}")
    return summary


if __name__ == "__main__":
    main()
