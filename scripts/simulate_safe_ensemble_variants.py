"""
simulate_safe_ensemble_variants.py

Replay historical top-selections from the unified evidence corpus under
alternative ensemble weight schemes.  Pure audit/simulation — no production
change, no scoring side effect.

Methodology:
  V0_CURRENT_LIVE uses the stored velo_prime_prob (the actual live blend output).
  All other variants re-blend from raw component scores, then select top-N
  rows by new probability where N matches V0 coverage at threshold.
  This ensures fair like-for-like coverage comparisons.

Input:
  data/velo_unified_evidence_corpus_v1.csv

Output:
  data/safe_ensemble_simulation_latest.json
  data/safe_ensemble_simulation_latest.md

Usage:
  python scripts/simulate_safe_ensemble_variants.py [--threshold 0.25]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORPUS_CSV  = ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"
OUTPUT_JSON = ROOT / "data" / "safe_ensemble_simulation_latest.json"
OUTPUT_MD   = ROOT / "data" / "safe_ensemble_simulation_latest.md"

CURRENT_LIVE_WEIGHTS = {
    "sqpe_v17_prob":           0.45,
    "improvement_score":       0.12,
    "release_day_prob":        0.10,
    "market_deception_score":  0.10,
    "place_prob":              0.08,
    "comment_intel_score":     0.08,
    "longshot_prob":           0.07,
}

COMPONENT_COLS = list(CURRENT_LIVE_WEIGHTS.keys())
HARMFUL      = ["release_day_prob", "comment_intel_score"]
OVERBET_RISK = ["improvement_score", "place_prob", "market_deception_score", "longshot_prob"]


def _norm(w: dict) -> dict:
    total = sum(v for v in w.values() if v > 0)
    return {k: v / total for k, v in w.items() if v > 0} if total else w


def _blend(row: dict, weights: dict) -> float:
    prob = 0.0
    for col, w in weights.items():
        try:
            prob += float(row.get(col) or 0) * w
        except (ValueError, TypeError):
            pass
    return min(1.0, max(0.0, prob))


def _ablation_remove(comp: str) -> dict:
    return _norm({k: v for k, v in CURRENT_LIVE_WEIGHTS.items() if k != comp})


def build_variants() -> list[tuple[str, dict | None, str]]:
    """(id, weights_or_None_for_stored, label).  None = use stored velo_prime_prob."""
    v = []
    v.append(("V0_CURRENT_LIVE", None,
              "Current live blend (stored velo_prime_prob)"))
    v.append(("V1_SQPE_ONLY", _norm({"sqpe_v17_prob": 1.0}),
              "SQPE only — all sidecars zeroed"))
    v.append(("V2_SQPE_MDS_PLACE", _norm({
        "sqpe_v17_prob": 0.60, "market_deception_score": 0.25, "place_prob": 0.15}),
        "SQPE + MDS + place_prob only"))
    v.append(("V3_SQPE_MDS_ONLY", _norm({
        "sqpe_v17_prob": 0.70, "market_deception_score": 0.30}),
        "SQPE + MDS only"))
    v.append(("V4_REMOVE_HARMFUL", _norm({
        "sqpe_v17_prob": 0.55, "market_deception_score": 0.15,
        "place_prob": 0.15, "improvement_score": 0.15}),
        "Remove harmful: no release_day_prob / comment_intel / longshot"))
    v.append(("V5_VALUE_DISCIPLINE", _norm({
        "sqpe_v17_prob": 0.65, "market_deception_score": 0.20, "improvement_score": 0.15}),
        "Value discipline: SQPE dominant, MDS + improvement only"))
    v.append(("V6_SHADOW_RACING_API_AWARE", _norm({
        "sqpe_v17_prob": 0.65, "market_deception_score": 0.20, "improvement_score": 0.15}),
        "V5 + Racing API annotation only (no live weight)"))
    for comp in COMPONENT_COLS:
        v.append((f"ABL_{comp}", _ablation_remove(comp),
                  f"Current minus {comp} (renormalized)"))
    return v


def _metrics(sel_rows: list[dict]) -> dict:
    n = len(sel_rows)
    if n == 0:
        return {"n": 0, "sr": 0.0, "fr": 0.0, "pl": 0.0, "roi": 0.0,
                "avg_sp": 0.0, "med_sp": 0.0, "max_drawdown": 0.0,
                "longest_losing_run": 0,
                "vp30_n": 0, "vp30_sr": 0.0, "vp30_fr": 0.0, "vp30_roi": 0.0}

    wins = frames = 0
    pl = 0.0
    sps: list[float] = []
    peak = dd = max_dd = 0.0
    cur_loss = max_loss = 0
    vp30_sel = []

    for r in sel_rows:
        won    = r.get("won","") in ("True","1")
        placed = r.get("placed","") in ("True","1") or won
        try:
            sp = float(r.get("sp_decimal") or 0)
        except (ValueError, TypeError):
            sp = 0.0
        if sp > 0:
            sps.append(sp)
        pl_this = (sp - 1.0) if won else -1.0
        pl += pl_this
        peak = max(peak, pl)
        max_dd = max(max_dd, peak - pl)
        if won:
            wins += 1
            cur_loss = 0
        else:
            cur_loss += 1
            max_loss = max(max_loss, cur_loss)
        if placed:
            frames += 1
        # VP30 uses stored velo_prime_prob
        try:
            if float(r.get("velo_prime_prob") or 0) >= 0.30:
                vp30_sel.append(r)
        except (ValueError, TypeError):
            pass

    vp30_n   = len(vp30_sel)
    vp30_w   = sum(1 for r in vp30_sel if r.get("won","") in ("True","1"))
    vp30_p   = sum(1 for r in vp30_sel if r.get("placed","") in ("True","1") or r.get("won","") in ("True","1"))
    vp30_pl  = sum((float(r.get("sp_decimal") or 0) - 1) if r.get("won","") in ("True","1") else -1 for r in vp30_sel)
    sps_s = sorted(sps)

    return {
        "n": n,
        "sr":  round(wins / n * 100, 2),
        "fr":  round(frames / n * 100, 2),
        "pl":  round(pl, 3),
        "roi": round(pl / n * 100, 2),
        "avg_sp": round(sum(sps) / len(sps), 2) if sps else 0.0,
        "med_sp": round(sps_s[len(sps_s) // 2], 2) if sps_s else 0.0,
        "max_drawdown": round(max_dd, 3),
        "longest_losing_run": max_loss,
        "vp30_n":   vp30_n,
        "vp30_sr":  round(vp30_w / vp30_n * 100, 2) if vp30_n else 0.0,
        "vp30_fr":  round(vp30_p / vp30_n * 100, 2) if vp30_n else 0.0,
        "vp30_roi": round(vp30_pl / vp30_n * 100, 2) if vp30_n else 0.0,
    }


def _answers(results: dict) -> list[str]:
    v0 = results.get("V0_CURRENT_LIVE", {})
    out = []

    def _cmp(key: str, q: str) -> str:
        r = results.get(key, {})
        if not r or not v0:
            return f"{q}: INSUFFICIENT_DATA"
        rd = r["roi"] - v0["roi"]
        sd = r["sr"]  - v0["sr"]
        fd = r["fr"]  - v0["fr"]
        dir_ = "IMPROVES" if rd > 0 else "WORSENS"
        return (f"{q}: ROI {v0['roi']:.2f}% → {r['roi']:.2f}% "
                f"(Δ{rd:+.2f}pp) — {dir_} | SR Δ{sd:+.2f}pp | Frame Δ{fd:+.2f}pp")

    out.append(_cmp("ABL_release_day_prob",      "Q1 remove release_day_prob"))
    out.append(_cmp("ABL_comment_intel_score",    "Q2 remove comment_intel_score"))
    out.append(_cmp("ABL_improvement_score",      "Q3 remove improvement_score"))

    r_mds = results.get("ABL_market_deception_score", {})
    if r_mds and v0:
        rd = r_mds["roi"] - v0["roi"]
        verdict = "KEEP_MDS" if rd < 0 else "REMOVE_MDS"
        out.append(f"Q4 MDS: {verdict} (removing ROI Δ{rd:+.2f}pp)")

    r_pl = results.get("ABL_place_prob", {})
    if r_pl and v0:
        rd = r_pl["roi"] - v0["roi"]
        verdict = "KEEP_PLACE_LIVE" if rd < 0 else "FRAME_ONLY"
        out.append(f"Q5 place_prob: {verdict} (removing ROI Δ{rd:+.2f}pp)")

    v1 = results.get("V1_SQPE_ONLY", {})
    if v1 and v0:
        rd = v1["roi"] - v0["roi"]
        verdict = "YES_SQPE_BETTER" if rd > 0 else "NO_BLEND_STILL_BETTER"
        out.append(f"Q6 SQPE-only better: {verdict} "
                   f"(SQPE={v1['roi']:.2f}% vs current={v0['roi']:.2f}%)")

    cand = ["V1_SQPE_ONLY","V2_SQPE_MDS_PLACE","V3_SQPE_MDS_ONLY",
            "V4_REMOVE_HARMFUL","V5_VALUE_DISCIPLINE"]
    best = max((k for k in cand if k in results), key=lambda k: results[k].get("roi",-999))
    out.append(f"Q7 safest candidate: {best} ROI={results[best].get('roi',0):.2f}%")
    return out


def _api_annotation(rows: list[dict]) -> dict:
    api_cols = ["racing_api_connection_shadow_score","racing_api_course_shadow_score",
                "racing_api_distance_shadow_score","racing_api_enrichment_shadow_score"]
    totals = {c: 0.0 for c in api_cols}
    counts = {c: 0 for c in api_cols}
    for r in rows:
        for c in api_cols:
            try:
                v = float(r.get(c) or 0)
                totals[c] += v; counts[c] += 1
            except (ValueError, TypeError):
                pass
    avgs = {c: round(totals[c]/counts[c], 4) if counts[c] else 0.0 for c in api_cols}
    hi = [r for r in rows if float(r.get("racing_api_enrichment_shadow_score") or 0) > 0.5]
    hi_sr = sum(1 for r in hi if r.get("won","") in ("True","1")) / len(hi) * 100 if hi else 0.0
    return {"avg_scores": avgs, "high_enrichment_n": len(hi),
            "high_enrichment_sr": round(hi_sr, 2),
            "note": "Racing API enrichment SHADOW ONLY — no live weight applied"}


def _render_md(results: dict, variant_meta: list, answers: list, threshold: float,
               corpus_n: int, usable_n: int, api_ann: dict, v0_n: int) -> str:
    lines = []
    lines.append("# VÉLØ Safe Ensemble Simulation — Variant Comparison")
    lines.append("")
    lines.append(f"Corpus: {corpus_n} rows | Usable (won+SP): {usable_n} | "
                 f"V0 selections at VP≥{threshold}: {v0_n}")
    lines.append("")
    lines.append("**All variants match V0 coverage (top-N by re-blended score).**")
    lines.append("**No production weight change. Simulation and governance only.**")
    lines.append("")

    hdrs = ["Variant", "n", "SR%", "FR%", "P&L", "ROI%",
            "AvgSP", "MedSP", "MaxDD", "LossRun",
            "VP30n", "VP30_SR%", "VP30_ROI%",
            "Changed", "W_Gain", "W_Lost", "ROI_Δ", "FR_Δ"]
    lines.append("## Full Variant Table")
    lines.append("")
    lines.append("| " + " | ".join(hdrs) + " |")
    lines.append("| " + " | ".join(["---"]*len(hdrs)) + " |")

    v0_roi = results.get("V0_CURRENT_LIVE", {}).get("roi", 0.0)
    v0_fr  = results.get("V0_CURRENT_LIVE", {}).get("fr",  0.0)
    for vid, _, _ in variant_meta:
        r = results.get(vid, {})
        if not r:
            continue
        chg  = str(r.get("changed_vs_v0","—"))
        wg   = str(r.get("winners_gained","—"))
        wl   = str(r.get("winners_lost","—"))
        rd   = f"{r['roi']-v0_roi:+.2f}" if vid != "V0_CURRENT_LIVE" else "—"
        fd   = f"{r['fr'] -v0_fr :+.2f}" if vid != "V0_CURRENT_LIVE" else "—"
        cells = [vid, str(r["n"]), f"{r['sr']:.1f}", f"{r['fr']:.1f}",
                 f"{r['pl']:.2f}", f"{r['roi']:.2f}",
                 f"{r['avg_sp']:.2f}", f"{r['med_sp']:.2f}",
                 f"{r['max_drawdown']:.2f}", str(r["longest_losing_run"]),
                 str(r["vp30_n"]), f"{r['vp30_sr']:.1f}", f"{r['vp30_roi']:.2f}",
                 chg, wg, wl, rd, fd]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Ablation sub-table
    abl_ids = [(vid, lbl) for vid, _, lbl in variant_meta if vid.startswith("ABL_")]
    if abl_ids:
        lines.append("## Ablation Table (Current Minus One, Same Coverage)")
        lines.append("")
        ah = ["Ablated", "n", "SR%", "FR%", "P&L", "ROI%",
              "ROI_Δ", "FR_Δ", "Changed", "W_Gained", "W_Lost"]
        lines.append("| " + " | ".join(ah) + " |")
        lines.append("| " + " | ".join(["---"]*len(ah)) + " |")
        for vid, lbl in abl_ids:
            r = results.get(vid, {})
            if not r:
                continue
            comp = vid.replace("ABL_","")
            rd   = f"{r['roi']-v0_roi:+.2f}"
            fd   = f"{r['fr'] -v0_fr :+.2f}"
            cells = [comp, str(r["n"]), f"{r['sr']:.1f}", f"{r['fr']:.1f}",
                     f"{r['pl']:.2f}", f"{r['roi']:.2f}", rd, fd,
                     str(r.get("changed_vs_v0","—")),
                     str(r.get("winners_gained","—")),
                     str(r.get("winners_lost","—"))]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    lines.append("## Direct Answers")
    lines.append("")
    for a in answers:
        lines.append(f"- {a}")
    lines.append("")

    lines.append("## Racing API Enrichment (Shadow Annotation — No Live Weight)")
    lines.append("")
    for k, v in api_ann["avg_scores"].items():
        lines.append(f"  {k}: avg={v}")
    lines.append(f"High enrichment (>0.5) rows: {api_ann['high_enrichment_n']} "
                 f"SR={api_ann['high_enrichment_sr']}%")
    lines.append(f"Note: {api_ann['note']}")
    lines.append("")

    lines.append("## Governance Recommendation")
    lines.append("")
    lines.append("See `docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md` → Safe Ensemble Candidate Review.")
    lines.append("")
    lines.append("**Operating decision**: Do not touch production weights blindly.")
    lines.append("Prove safer blend first. If it beats current on ROI/drawdown without")
    lines.append("killing strike/frame → create SHADOW_SAFE_BLEND. Only then does live")
    lines.append("weight change become a formal discussion.")
    lines.append("")
    return "\n".join(lines)


def run(threshold: float = 0.25) -> None:
    if not CORPUS_CSV.exists():
        print(f"ERROR: corpus not found at {CORPUS_CSV}", file=sys.stderr)
        sys.exit(1)

    all_rows = list(csv.DictReader(CORPUS_CSV.open()))
    usable = [
        r for r in all_rows
        if r.get("won","") in ("True","False","1","0")
        and r.get("sp_decimal","") not in ("","None","0")
    ]
    corpus_n  = len(all_rows)
    usable_n  = len(usable)
    print(f"Corpus: {corpus_n} total | {usable_n} usable (won+SP)")

    variant_meta = build_variants()

    # ── V0: use stored velo_prime_prob ────────────────────────────────────────
    v0_sel = [r for r in usable
              if float(r.get("velo_prime_prob") or 0) >= threshold]
    v0_n = len(v0_sel)
    v0_idxs: set[int] = set()
    v0_winner_idxs: set[int] = set()
    for i, r in enumerate(usable):
        try:
            if float(r.get("velo_prime_prob") or 0) >= threshold:
                v0_idxs.add(i)
                if r.get("won","") in ("True","1"):
                    v0_winner_idxs.add(i)
        except (ValueError, TypeError):
            pass

    v0_metrics = _metrics(v0_sel)
    results: dict[str, dict] = {"V0_CURRENT_LIVE": v0_metrics}
    print(f"V0 baseline: n={v0_n} SR={v0_metrics['sr']}% "
          f"FR={v0_metrics['fr']}% ROI={v0_metrics['roi']}%")

    # ── All other variants: top-N by re-blended score ─────────────────────────
    for vid, weights, label in variant_meta[1:]:
        if weights is None:
            continue

        # Score every usable row
        scored = [(i, _blend(r, weights), r) for i, r in enumerate(usable)]
        scored.sort(key=lambda x: -x[1])

        # Take top-N matching V0 coverage (but include all rows that tie at cutoff)
        sel_rows = [r for _, _, r in scored[:v0_n]]
        sel_idxs = {i for i, _, _ in scored[:v0_n]}

        m = _metrics(sel_rows)

        # Delta stats vs V0
        changed = len(sel_idxs.symmetric_difference(v0_idxs))
        only_variant = sel_idxs - v0_idxs
        only_v0      = v0_idxs - sel_idxs
        w_gained = sum(1 for i in only_variant
                       if usable[i].get("won","") in ("True","1"))
        w_lost   = sum(1 for i in only_v0
                       if usable[i].get("won","") in ("True","1"))

        m["changed_vs_v0"]  = changed
        m["winners_gained"] = w_gained
        m["winners_lost"]   = w_lost
        m["roi_delta"]      = round(m["roi"] - v0_metrics["roi"], 2)
        m["frame_delta"]    = round(m["fr"]  - v0_metrics["fr"],  2)
        results[vid] = m
        print(f"  {vid}: n={m['n']} SR={m['sr']}% ROI={m['roi']}% "
              f"(Δroi={m['roi_delta']:+.2f}pp  changed={changed}  W+={w_gained}  W-={w_lost})")

    answers  = _answers(results)
    api_ann  = _api_annotation(usable)

    # Safest candidate
    cand_keys = ["V1_SQPE_ONLY","V2_SQPE_MDS_PLACE","V3_SQPE_MDS_ONLY",
                 "V4_REMOVE_HARMFUL","V5_VALUE_DISCIPLINE"]
    best = max((k for k in cand_keys if k in results),
               key=lambda k: results[k].get("roi", -999))
    best_roi = results[best].get("roi", 0)

    # Build clean output payload
    clean_results = {}
    for vid, weights, label in variant_meta:
        r = results.get(vid, {})
        if not r:
            continue
        clean_results[vid] = {
            **{k: v for k, v in r.items() if not k.startswith("_")},
            "label": label,
            "weights": weights if weights else {"stored_velo_prime_prob": 1.0},
        }

    payload = {
        "corpus_n": corpus_n,
        "usable_n": usable_n,
        "v0_n": v0_n,
        "threshold": threshold,
        "variants": clean_results,
        "answers": answers,
        "racing_api_annotation": api_ann,
        "safest_candidate_blend": best,
        "safest_candidate_roi": best_roi,
        "governance": {
            "harmful_confirmed": HARMFUL,
            "overbet_risk": OVERBET_RISK,
            "production_unchanged": True,
            "recommended_next": "CREATE_SHADOW_SAFE_BLEND_AFTER_REVIEW",
        },
    }

    OUTPUT_JSON.write_text(json.dumps(payload, indent=2))
    print(f"\nJSON: {OUTPUT_JSON}")
    md = _render_md(results, variant_meta, answers, threshold,
                    corpus_n, usable_n, api_ann, v0_n)
    OUTPUT_MD.write_text(md)
    print(f"MD:   {OUTPUT_MD}")

    print("\n── SIMULATION SUMMARY ─────────────────────────────────────────────")
    print(f"Sample: {usable_n}  |  V0 selections: {v0_n}  |  Threshold: VP≥{threshold}")
    print(f"V0 baseline: SR={v0_metrics['sr']}%  FR={v0_metrics['fr']}%  "
          f"ROI={v0_metrics['roi']}%  AvgSP={v0_metrics['avg_sp']}")
    print()
    for a in answers:
        print(f"  {a}")
    print()
    print(f"Safest candidate: {best}  ROI={best_roi:.2f}%")
    print("Production weights: UNCHANGED — simulation only.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()
    run(threshold=args.threshold)
