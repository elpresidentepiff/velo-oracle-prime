"""
compare_live_weight_profiles.py

Replay the unified evidence corpus (721 historical top-selections with results)
under four weight profiles. Produces a ranked comparison to inform whether
the current sidecar stack improves or damages economics.

Profiles:
  A_CURRENT        — stored velo_prime_prob (live blend, runtime-proven)
  B_CLEAN_VALUE    — SQPE + MDS + place_prob (capped) + longshot (gated);
                     improvement_score halved; release/comment zeroed
  C_SQPE_MDS_ONLY  — SQPE + MDS + place_prob only
  D_SQPE_ONLY      — SQPE baseline, nothing else

Output:
  data/live_weight_profile_comparison_latest.json
  data/live_weight_profile_comparison_latest.md

Hard rules:
  - Read-only. No scoring change. No SQPE. No router. No staking. No Telegram.
  - Do not commit output data files.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT       = Path(__file__).resolve().parents[1]
CORPUS     = ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"
OUT_JSON   = ROOT / "data" / "live_weight_profile_comparison_latest.json"
OUT_MD     = ROOT / "data" / "live_weight_profile_comparison_latest.md"

# ─── Weight profiles ──────────────────────────────────────────────────────────

# A: Current live blend — measured via stored velo_prime_prob
# (no re-computation; uses the exact runtime scores)
PROFILE_A = {
    "name": "A_CURRENT",
    "label": "Live blend (velo_prime_prob ≥ 0.25)",
    "use_stored_vp": True,
    "threshold": 0.25,
    "weights": {},  # not used — stored VP used directly
}

# B: Clean value — harmful sidecars zeroed or halved, good sidecars kept
PROFILE_B = {
    "name": "B_CLEAN_VALUE",
    "label": "Clean value (SQPE + MDS + place_prob capped + longshot gated; release/comment zeroed)",
    "use_stored_vp": False,
    "weights": {
        "sqpe_v17_prob":          0.55,
        "market_deception_score": 0.20,
        "place_prob":             0.10,  # capped vs current relative share
        "longshot_prob":          0.07,  # gated: only contributes if sp_decimal >= 10
        "improvement_score":      0.06,  # halved from declared 0.12 share
        "release_day_prob":       0.00,  # zeroed — harmful ROI per audit
        "comment_intel_score":    0.00,  # zeroed — harmful ROI per audit
    },
    "longshot_gate_sp": 10.0,
}

# C: SQPE + MDS + place_prob only — stripped to three proven signals
PROFILE_C = {
    "name": "C_SQPE_MDS_ONLY",
    "label": "SQPE + MDS + place_prob only",
    "use_stored_vp": False,
    "weights": {
        "sqpe_v17_prob":          0.70,
        "market_deception_score": 0.20,
        "place_prob":             0.10,
        "improvement_score":      0.00,
        "release_day_prob":       0.00,
        "comment_intel_score":    0.00,
        "longshot_prob":          0.00,
    },
}

# D: SQPE only — pure model baseline
PROFILE_D = {
    "name": "D_SQPE_ONLY",
    "label": "SQPE only (pure model baseline)",
    "use_stored_vp": False,
    "weights": {
        "sqpe_v17_prob":          1.00,
        "market_deception_score": 0.00,
        "place_prob":             0.00,
        "improvement_score":      0.00,
        "release_day_prob":       0.00,
        "comment_intel_score":    0.00,
        "longshot_prob":          0.00,
    },
}

PROFILES = [PROFILE_A, PROFILE_B, PROFILE_C, PROFILE_D]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val) if val not in (None, "", "None", "nan") else default
    except (ValueError, TypeError):
        return default


def _blend(row: dict, profile: dict) -> float:
    """Compute blended score for a row under the given weight profile."""
    if profile.get("use_stored_vp"):
        return _f(row.get("velo_prime_prob"))

    w = profile["weights"]
    gate_sp = profile.get("longshot_gate_sp")
    score = 0.0
    total_w = 0.0

    for col, weight in w.items():
        if weight == 0.0:
            continue
        if col == "longshot_prob" and gate_sp is not None:
            sp = _f(row.get("sp_decimal"), default=0.0)
            if sp < gate_sp:
                continue  # longshot gate not met — don't add contribution
        val = _f(row.get(col))
        score += weight * val
        total_w += weight

    return score / total_w if total_w > 0 else 0.0


def _metrics(selections: list[dict]) -> dict:
    """Compute full metrics for a selection set."""
    n = len(selections)
    if n == 0:
        return {"n": 0}

    wins       = [r for r in selections if str(r.get("won", "")).lower() == "true"]
    placed_sel = [r for r in selections if str(r.get("placed", "")).lower() == "true"]

    sr   = len(wins) / n
    fr   = len(placed_sel) / n

    # ROI (level stakes 1 unit)
    pnl_list = []
    for r in selections:
        won = str(r.get("won", "")).lower() == "true"
        sp  = _f(r.get("sp_decimal"), default=1.0)
        pnl_list.append(sp - 1.0 if won else -1.0)
    roi = sum(pnl_list) / n * 100  # percent

    # Max drawdown (peak-to-trough on running P&L)
    running = 0.0
    peak    = 0.0
    max_dd  = 0.0
    for p in pnl_list:
        running += p
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    # Longest losing run
    cur_lose = 0
    max_lose = 0
    for r in selections:
        if str(r.get("won", "")).lower() != "true":
            cur_lose += 1
            max_lose = max(max_lose, cur_lose)
        else:
            cur_lose = 0

    # Average SP
    sps    = [_f(r.get("sp_decimal"), default=0.0) for r in selections if _f(r.get("sp_decimal")) > 0]
    avg_sp = sum(sps) / len(sps) if sps else 0.0

    # Signal overlaps
    mds_high  = sum(1 for r in selections if _f(r.get("market_deception_score")) > 0.50)
    imp_high  = sum(1 for r in selections if _f(r.get("improvement_score")) > 0.30)

    # Decision tier overlaps (CLASS_4 / VP30 tier)
    tier_counts: dict[str, int] = {}
    for r in selections:
        t = (r.get("decision_tier") or r.get("tier") or "UNKNOWN").strip()
        tier_counts[t] = tier_counts.get(t, 0) + 1
    vp30_tiers = sum(v for k, v in tier_counts.items()
                     if any(x in k for x in ["POWER_ANCHOR", "VP30", "CLASS_4", "V2"]))

    return {
        "n":                n,
        "wins":             len(wins),
        "strike_rate_pct":  round(sr * 100, 2),
        "frame_rate_pct":   round(fr * 100, 2),
        "roi_pct":          round(roi, 2),
        "total_pnl":        round(sum(pnl_list), 2),
        "max_drawdown":     round(max_dd, 2),
        "longest_lose_run": max_lose,
        "avg_sp":           round(avg_sp, 2),
        "mds_high_n":       mds_high,
        "mds_high_pct":     round(mds_high / n * 100, 1),
        "improve_high_n":   imp_high,
        "improve_high_pct": round(imp_high / n * 100, 1),
        "vp30_tier_n":      vp30_tiers,
        "vp30_tier_pct":    round(vp30_tiers / n * 100, 1),
        "tier_breakdown":   tier_counts,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    with CORPUS.open(newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    # 721 usable rows: have won + sp_decimal
    usable = [r for r in all_rows
              if r.get("won", "").strip() and r.get("sp_decimal", "").strip()]
    print(f"Corpus: {len(all_rows)} total | {len(usable)} usable (won + SP)")

    results: list[dict] = []

    # Step 1: determine baseline N from PROFILE_A (stored VP threshold)
    pa = PROFILE_A
    a_selections = [r for r in usable if _f(r.get("velo_prime_prob")) >= pa["threshold"]]
    n_baseline   = len(a_selections)
    print(f"Profile A — {n_baseline} selections at VP >= {pa['threshold']}")

    a_metrics = _metrics(a_selections)
    results.append({
        "profile":  pa["name"],
        "label":    pa["label"],
        "metrics":  a_metrics,
        "delta_roi_vs_A":  0.0,
        "delta_sr_vs_A":   0.0,
        "delta_fr_vs_A":   0.0,
        "top_sel_changed": 0,
        "top_sel_changed_pct": 0.0,
    })

    a_ids = {r.get("canonical_key") or r.get("horse_id") or i
             for i, r in enumerate(a_selections)}

    # Step 2: for each other profile, score all usable rows, take top-N
    for profile in [PROFILE_B, PROFILE_C, PROFILE_D]:
        scored = sorted(usable, key=lambda r: _blend(r, profile), reverse=True)
        selections = scored[:n_baseline]

        m = _metrics(selections)

        sel_ids = {r.get("canonical_key") or r.get("horse_id") or i
                   for i, r in enumerate(selections)}
        changed = len(a_ids.symmetric_difference(sel_ids))

        results.append({
            "profile":  profile["name"],
            "label":    profile["label"],
            "metrics":  m,
            "delta_roi_vs_A":  round(m["roi_pct"] - a_metrics["roi_pct"], 2),
            "delta_sr_vs_A":   round(m["strike_rate_pct"] - a_metrics["strike_rate_pct"], 2),
            "delta_fr_vs_A":   round(m["frame_rate_pct"] - a_metrics["frame_rate_pct"], 2),
            "top_sel_changed": changed,
            "top_sel_changed_pct": round(changed / n_baseline * 100, 1),
        })
        print(f"Profile {profile['name']} — SR={m['strike_rate_pct']}% "
              f"ROI={m['roi_pct']}% FR={m['frame_rate_pct']}% "
              f"(Δ ROI vs A: {results[-1]['delta_roi_vs_A']:+.2f}pp)")

    # ── Decision rule ──────────────────────────────────────────────────────────
    b, c, d = results[1], results[2], results[3]
    a_roi = a_metrics["roi_pct"]
    a_fr  = a_metrics["frame_rate_pct"]

    recommendations: list[str] = []

    b_frame_ok = b["metrics"]["frame_rate_pct"] >= a_fr * 0.70
    b_sr_ok    = abs(b["delta_sr_vs_A"]) <= 3.0
    if b["delta_roi_vs_A"] > 2.0 and b_frame_ok and b_sr_ok:
        recommendations.append("PROFILE_B → PATCH_CANDIDATE: improves ROI >{:.1f}pp, "
                               "frame within 70% of current, SR within 3pp".format(b["delta_roi_vs_A"]))
    else:
        recommendations.append("PROFILE_B → HOLD: ROI delta={:+.2f}pp | frame_ok={} | sr_ok={}".format(
            b["delta_roi_vs_A"], b_frame_ok, b_sr_ok))

    if c["delta_roi_vs_A"] > 3.0:
        recommendations.append("PROFILE_C → SIDECAR_REDUCTION_URGENT: "
                               "stripping to SQPE+MDS+place_prob gains {:+.2f}pp ROI".format(c["delta_roi_vs_A"]))
    else:
        recommendations.append("PROFILE_C → HOLD: SQPE+MDS+place_prob delta={:+.2f}pp".format(c["delta_roi_vs_A"]))

    if d["delta_roi_vs_A"] > c["delta_roi_vs_A"] and d["delta_roi_vs_A"] > b["delta_roi_vs_A"]:
        recommendations.append("PROFILE_D → SQPE_ONLY_DOMINANT: ensemble sidecars collectively damaging — "
                               "rebuild candidate. Gain {:+.2f}pp".format(d["delta_roi_vs_A"]))
    else:
        recommendations.append("PROFILE_D → SQPE baseline not dominant; some sidecars add value")

    # ── Write JSON ─────────────────────────────────────────────────────────────
    payload = {
        "corpus_total":        len(all_rows),
        "corpus_usable":       len(usable),
        "baseline_n":          n_baseline,
        "profiles":            results,
        "recommendations":     recommendations,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    # ── Write Markdown ─────────────────────────────────────────────────────────
    lines: list[str] = [
        "# VÉLØ Live Weight Profile Comparison",
        "",
        f"Corpus: {len(usable)} usable selections (won + SP confirmed)",
        f"Baseline n: {n_baseline} (Profile A, VP ≥ 0.25)",
        "",
        "## Profile Results",
        "",
        "| Profile | n | SR% | FR% | ROI% | Δ ROI vs A | Max DD | Lose Run | Avg SP | MDS>0.5 | IMP>0.3 | Top Sel Δ |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        m = r["metrics"]
        lines.append(
            f"| **{r['profile']}** "
            f"| {m['n']} "
            f"| {m['strike_rate_pct']} "
            f"| {m['frame_rate_pct']} "
            f"| {m['roi_pct']} "
            f"| {r['delta_roi_vs_A']:+.2f} "
            f"| {m['max_drawdown']:.2f} "
            f"| {m['longest_lose_run']} "
            f"| {m['avg_sp']:.2f} "
            f"| {m['mds_high_pct']}% "
            f"| {m['improve_high_pct']}% "
            f"| {r['top_sel_changed_pct']}% |"
        )

    lines += ["", "## Recommendations", ""]
    for rec in recommendations:
        lines.append(f"- {rec}")

    lines += [
        "",
        "## Decision Rules Applied",
        "",
        "- **B = PATCH_CANDIDATE** if: Δ ROI > +2pp AND frame_rate ≥ 70% of current AND |ΔSR| ≤ 3pp",
        "- **C → SIDECAR_REDUCTION_URGENT** if: Δ ROI > +3pp",
        "- **D → SQPE_ONLY_DOMINANT** if: D beats both B and C on ROI",
        "",
        "## Hard Rules",
        "",
        "- No live code changed.",
        "- No SQPE changed.",
        "- No router changed.",
        "- No staking.",
        "- No Telegram betting alert.",
        "- Output is simulation evidence only.",
        "- Weight changes require 30-day shadow proof before promotion.",
    ]

    OUT_MD.write_text("\n".join(lines))

    print(f"\nWritten: {OUT_JSON.name}")
    print(f"Written: {OUT_MD.name}")
    print("\n=== RECOMMENDATIONS ===")
    for rec in recommendations:
        print(f"  {rec}")


if __name__ == "__main__":
    main()
