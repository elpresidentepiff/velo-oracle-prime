"""
VÉLØ Component Attribution Audit
==================================
Measures liveness, influence, and correlation for each ensemble component
using stored full_analysis data from velo_verdicts.

Components audited:
  sqpe_v17_prob, improvement_score, market_deception_score, release_day_prob,
  place_prob, comment_intel_score, longshot_prob

Tests:
  1. LIVENESS    — non-null%, non-zero%, std, unique values per component
  2. INFLUENCE   — % of races where removing this component changes top pick
                   or changes the final A/B/C/D/X tier
  3. CORRELATION — Pearson r with sqpe_v17_prob and with velo_prime_prob
  4. FEATURE GAP — which specialist models receive all-zero input (stuck constants)

Usage:
    python scripts/run_attribution_audit.py --days 35
    python scripts/run_attribution_audit.py --days 60 --verbose
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from supabase import create_client
import math

SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

# ── Ensemble weights (must match velo_prime_ensemble.py) ──────────────────────
_WEIGHTS = {
    "sqpe_v17_prob":          0.45,
    "improvement_score":      0.12,
    "release_day_prob":       0.10,
    "market_deception_score": 0.10,
    "place_prob":             0.08,
    "comment_intel_score":    0.08,
    "longshot_prob":          0.07,
}
# longshot is SP-gated in production; we include it unconditionally here
# because sp_dec is not reliably stored. Slight over-inclusion is noted.

COMPONENT_LABELS = {
    "sqpe_v17_prob":          "SQPE v17",
    "improvement_score":      "Improvement",
    "release_day_prob":       "Release Window",
    "market_deception_score": "Market Deception",
    "place_prob":             "Place Model",
    "comment_intel_score":    "Comment Intel",
    "longshot_prob":          "Longshot",
}

TIERS = ("A", "B", "C", "D", "X")


def _pct(n, d):
    return f"{n / d * 100:.1f}%" if d else "n/a"


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (sx * sy) if sx * sy > 0 else float("nan")


def _compute_ensemble(runner: dict, exclude: str | None = None) -> float:
    """Recompute velo_prime_prob for a runner, optionally excluding one component."""
    total_w = 0.0
    total_v = 0.0
    for comp, w in _WEIGHTS.items():
        if comp == exclude:
            continue
        v = runner.get(comp)
        if v is None:
            continue
        # longshot: skip if zero (proxy for SP < 10)
        if comp == "longshot_prob" and float(v) == 0.0:
            continue
        total_w += w
        total_v += w * float(v)
    return total_v / total_w if total_w > 0 else 0.0


def _rerank_field(runners: list[dict], exclude: str | None = None) -> list[dict]:
    """Recompute and normalise velo_prime_prob for a field, excluding one component."""
    scored = []
    for r in runners:
        raw = _compute_ensemble(r, exclude=exclude)
        scored.append({**r, "_raw": raw})
    total = sum(s["_raw"] for s in scored)
    if total > 0:
        for s in scored:
            s["_norm"] = s["_raw"] / total
    else:
        for s in scored:
            s["_norm"] = 0.0
    scored.sort(key=lambda x: x["_norm"], reverse=True)
    return scored


def _synthesize_tier(top: dict, second_prob: float) -> str:
    """Simplified synthesize_decision for attribution re-sim (baseline thresholds)."""
    prob = float(top.get("velo_prime_prob") or top.get("_norm") or 0)
    place = float(top.get("place_prob") or 0)
    longshot = float(top.get("longshot_prob") or 0)
    chaos = bool(top.get("macro_chaos_mode") or False)
    improve = float(top.get("improvement_score") or 0)
    gap = prob - second_prob

    eff_conf = "high" if prob >= 0.45 else "normal" if prob >= 0.15 else "low"
    if prob < 0.10 or (gap < 0.015 and place < 0.40) or chaos:
        return "X"
    if prob >= 0.32 and gap >= 0.08 and place >= 0.52:
        return "A"
    if prob >= 0.15 and gap >= 0.03 and eff_conf != "low":
        if place >= 0.45 or gap >= 0.08 or improve >= 0.18:
            return "B"
    if (prob >= 0.13 and gap >= 0.02) or (place >= 0.55 and prob >= 0.11):
        return "C"
    return "D"


def run_audit(days: int = 35, verbose: bool = False):
    print(f"\n{'='*70}")
    print(f"  VÉLØ COMPONENT ATTRIBUTION AUDIT — last {days} days")
    print(f"{'='*70}\n")

    sb = create_client(SB_URL, SB_KEY)
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    resp = sb.table("velo_verdicts") \
        .select("race_id,generated_at,decision_tier,velo_prime_prob,full_analysis") \
        .gte("generated_at", since) \
        .not_.is_("velo_prime_prob", "null") \
        .execute()

    verdicts = resp.data or []
    print(f"Verdicts loaded: {len(verdicts)}")

    # Build per-race fields: list of runner dicts
    races: list[list[dict]] = []
    for v in verdicts:
        fa = v.get("full_analysis") or []
        if isinstance(fa, str):
            fa = json.loads(fa)
        if fa:
            races.append(fa)

    all_runners = [r for field in races for r in field]
    print(f"Total runners: {len(all_runners)}\n")

    components = list(_WEIGHTS.keys())

    # ── 1. LIVENESS ───────────────────────────────────────────────────────────
    print(f"{'-'*70}")
    print("1. LIVENESS — variance and coverage per component")
    print(f"{'-'*70}")
    print(f"{'Component':<26} {'non-null%':>9} {'non-zero%':>10} {'std':>8} {'unique':>8} {'mean':>8} {'status'}")
    print("-" * 82)

    liveness: dict[str, dict] = {}
    for comp in components:
        vals = [float(r[comp]) for r in all_runners if r.get(comp) is not None]
        non_null = len(vals)
        non_zero = sum(1 for v in vals if v != 0.0)
        if vals:
            mean_v = sum(vals) / len(vals)
            std_v = math.sqrt(sum((v - mean_v) ** 2 for v in vals) / len(vals))
            unique = len(set(round(v, 4) for v in vals))
        else:
            mean_v = std_v = 0.0
            unique = 0

        if unique <= 1:
            status = "DEAD — constant output"
        elif unique <= 3:
            status = "WEAK — near-constant"
        elif std_v < 0.02:
            status = "LOW VAR"
        else:
            status = "OK"

        liveness[comp] = {"vals": vals, "std": std_v, "unique": unique, "mean": mean_v, "status": status}
        label = COMPONENT_LABELS[comp]
        print(f"{label:<26} {_pct(non_null, len(all_runners)):>9} {_pct(non_zero, non_null) if non_null else 'n/a':>10} "
              f"{std_v:>8.4f} {unique:>8} {mean_v:>8.4f}  {status}")

    # ── 2. CORRELATION ────────────────────────────────────────────────────────
    print(f"\n{'-'*70}")
    print("2. CORRELATION — relationship with SQPE and final velo_prime_prob")
    print(f"{'-'*70}")
    print(f"{'Component':<26} {'r(SQPE)':>10} {'r(velo_prime)':>14} {'note'}")
    print("-" * 65)

    sqpe_vals = [float(r["sqpe_v17_prob"]) for r in all_runners if r.get("sqpe_v17_prob") is not None]
    vpp_vals = [float(r["velo_prime_prob"]) for r in all_runners if r.get("velo_prime_prob") is not None]

    for comp in components:
        if comp in ("sqpe_v17_prob",):
            r_sqpe = 1.0
            r_vpp = _pearson(sqpe_vals, vpp_vals[:len(sqpe_vals)])
            note = "baseline"
        else:
            comp_vals = liveness[comp]["vals"]
            # Align on runners that have all three
            aligned_sqpe, aligned_comp, aligned_vpp = [], [], []
            for r in all_runners:
                s = r.get("sqpe_v17_prob")
                c = r.get(comp)
                v = r.get("velo_prime_prob")
                if s is not None and c is not None and v is not None:
                    aligned_sqpe.append(float(s))
                    aligned_comp.append(float(c))
                    aligned_vpp.append(float(v))
            r_sqpe = _pearson(aligned_comp, aligned_sqpe)
            r_vpp = _pearson(aligned_comp, aligned_vpp)
            if liveness[comp]["unique"] <= 1:
                note = "constant — correlation meaningless"
            elif abs(r_sqpe) > 0.80:
                note = "HIGH corr with SQPE — likely redundant"
            elif abs(r_vpp) > 0.60:
                note = "strong driver of final score"
            else:
                note = ""
        label = COMPONENT_LABELS[comp]
        print(f"{label:<26} {r_sqpe:>10.3f} {r_vpp:>14.3f}  {note}")

    # ── 3. INFLUENCE — top-pick flips and tier changes ────────────────────────
    print(f"\n{'-'*70}")
    print("3. INFLUENCE — how often removing each component changes top pick / tier")
    print(f"{'-'*70}")
    print(f"{'Component':<26} {'top_flip%':>10} {'tier_flip%':>12} {'note'}")
    print("-" * 65)

    # Baseline: full ensemble tier for each race
    baseline_tops: list[dict] = []
    baseline_tiers: list[str] = []
    for field in races:
        ranked = _rerank_field(field)
        top = ranked[0]
        sec = float(ranked[1]["_norm"]) if len(ranked) > 1 else 0.0
        top["velo_prime_prob"] = top["_norm"]
        tier = _synthesize_tier(top, sec)
        baseline_tops.append(top)
        baseline_tiers.append(tier)

    for comp in components:
        top_flips = 0
        tier_flips = 0
        for i, field in enumerate(races):
            ranked_ex = _rerank_field(field, exclude=comp)
            new_top = ranked_ex[0]
            new_sec = float(ranked_ex[1]["_norm"]) if len(ranked_ex) > 1 else 0.0
            new_top["velo_prime_prob"] = new_top["_norm"]
            new_tier = _synthesize_tier(new_top, new_sec)

            if new_top.get("horse_id") != baseline_tops[i].get("horse_id"):
                top_flips += 1
            if new_tier != baseline_tiers[i]:
                tier_flips += 1

        n = len(races)
        label = COMPONENT_LABELS[comp]
        if comp == "sqpe_v17_prob":
            note = "anchor — expected high influence"
        elif liveness[comp]["unique"] <= 1:
            note = "DEAD — flips are pure noise injection"
        elif top_flips / n < 0.02 and tier_flips / n < 0.02:
            note = "effectively zero influence"
        elif top_flips / n > 0.15:
            note = "high influence — warrants scrutiny"
        else:
            note = ""
        print(f"{label:<26} {_pct(top_flips, n):>10} {_pct(tier_flips, n):>12}  {note}")

    # ── 4. FEATURE GAP ────────────────────────────────────────────────────────
    print(f"\n{'-'*70}")
    print("4. FEATURE GAP — specialist models receiving all-zero input")
    print(f"{'-'*70}")

    import json as _json
    models_dir = ROOT / "models" / "specialist"
    gap_models = [
        ("comment_intelligence_model", "comment_intel_score",  "RPD intent features"),
        ("release_window_model",        "release_day_prob",     "RPD timing features"),
        ("improvement_model",           "improvement_score",    "form + rating features"),
        ("market_deception_model",      "market_deception_score", "odds history features"),
        ("place_model",                 "place_prob",           "SP + class + distance"),
        ("longshot_model",              "longshot_prob",        "SP + rating + field features"),
    ]

    for model_name, score_key, feature_class in gap_models:
        meta_path = models_dir / model_name / "metadata.json"
        if not meta_path.exists():
            print(f"  {model_name:<35}  NO MODEL FILE")
            continue
        with open(meta_path) as f:
            meta = _json.load(f)
        features = meta.get("features", [])

        # Check which features are present in a sample live runner
        sample = all_runners[0] if all_runners else {}
        present = [f for f in features if sample.get(f) is not None]
        missing = [f for f in features if f not in sample]

        live_score_vals = [float(r[score_key]) for r in all_runners if r.get(score_key) is not None]
        unique_out = len(set(round(v, 4) for v in live_score_vals)) if live_score_vals else 0

        verdict = "DEAD (constant)" if unique_out <= 1 else f"LIVE ({unique_out} unique)"
        print(f"  {model_name:<35}  {verdict}")
        print(f"    Required features: {len(features)}  |  present in live: {len(present)}  |  missing: {len(missing)}")
        print(f"    Feature class: {feature_class}")
        if missing and verbose:
            print(f"    Missing: {missing[:6]}{'...' if len(missing) > 6 else ''}")
        print()

    # ── Summary verdict ────────────────────────────────────────────────────────
    print(f"{'-'*70}")
    print("SUMMARY")
    print(f"{'-'*70}")

    dead = [c for c in components if liveness[c]["unique"] <= 1]
    weak = [c for c in components if 1 < liveness[c]["unique"] <= 3]
    live = [c for c in components if liveness[c]["unique"] > 3]

    dead_weight = sum(_WEIGHTS[c] for c in dead)
    print(f"Dead components (constant output):  {[COMPONENT_LABELS[c] for c in dead]}")
    print(f"  Combined ensemble weight: {dead_weight:.0%} — zero signal, distorts normalization")
    print(f"Weak components:            {[COMPONENT_LABELS[c] for c in weak]}")
    print(f"Live components:            {[COMPONENT_LABELS[c] for c in live]}")
    print()
    print("Recommended actions:")
    for c in dead:
        print(f"  REMOVE  {COMPONENT_LABELS[c]:<22} — constant output, features not available live")
    for c in weak:
        print(f"  INSPECT {COMPONENT_LABELS[c]:<22} — near-constant, likely feature gap")
    for c in live:
        if c != "sqpe_v17_prob":
            print(f"  KEEP    {COMPONENT_LABELS[c]:<22} — active signal (verify lift separately)")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days",    type=int, default=35)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    run_audit(days=args.days, verbose=args.verbose)
