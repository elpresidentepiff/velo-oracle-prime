"""
router_shadow_audit.py
=======================
Execution Router Evidence Engine — shadow lane analysis only.

Reads the deduped Innovation Protocol dataset and produces:
  data/router_shadow_audit_latest.csv
  data/router_shadow_audit_latest.md

Router lanes audited:
  V1_BASE         — Class 3|4, Structure, SP 2-4, VP≥0.30, FS≤12
  V2_CLASS4_ONLY  — Class 4, Structure, SP 2-4, VP≥0.30, FS≤12
  V6_GOLD_SEAM    — Class 4, Structure, SP 3-4, VP≥0.35, FS≤12

No live betting. No model changes. No staking. Read-only except output files.

Usage:
  python scripts/router_shadow_audit.py
  python scripts/router_shadow_audit.py --prev-csv data/router_shadow_audit_prev.csv
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import numpy as np  # noqa: E402

DEDUPED_PATH = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
AUDIT_CSV    = ROOT / "data" / "router_shadow_audit_latest.csv"
AUDIT_MD     = ROOT / "data" / "router_shadow_audit_latest.md"

PROMOTION_GATES = {
    "V1_BASE": {
        "WATCHLIST":           {"n": 27,  "roi_min": 0.0, "fr_min": 75.0},
        "SHADOW_CANDIDATE":    {"n": 50,  "roi_min": 0.0, "fr_min": 75.0},
        "PAPER_EXECUTION":     {"n": 100, "roi_min": 0.0, "fr_min": 75.0},
    },
    "V2_CLASS4_ONLY": {
        "WATCHLIST":           {"n": 20,  "roi_min": 0.0, "fr_min": 0.0},
        "SHADOW_CANDIDATE":    {"n": 30,  "roi_min": 0.0, "fr_min": 75.0},
        "PAPER_EXECUTION":     {"n": 60,  "roi_min": 0.0, "fr_min": 75.0},
        "LIVE_DISCUSSION":     {"n": 100, "roi_min": 0.0, "fr_min": 75.0},
    },
    "V6_GOLD_SEAM": {
        "SHADOW_CANDIDATE":    {"n": 20,  "roi_min": 0.0, "fr_min": 0.0},
        "PAPER_EXECUTION":     {"n": 50,  "roi_min": 0.0, "fr_min": 75.0},
    },
}

FREEZE_RULES = {
    "roi_negative_after_n20": "If n≥20 and ROI turns negative → FREEZE",
    "frame_below_70":         "If frame rate drops below 70% at n≥20 → FREEZE",
    "duplicate_contamination": "If dedup key collision rate >5% → STOP AND FIX",
}

LANES = {
    "V1_BASE": {
        "class_num": (3, 4), "archetype": "Structure",
        "sp_lo": 2.0, "sp_hi": 4.0, "vp_min": 0.30,
        "fs_max": 12, "going_block": "heavy", "arch_block": "Chaos",
    },
    "V2_CLASS4_ONLY": {
        "class_num": (4,), "archetype": "Structure",
        "sp_lo": 2.0, "sp_hi": 4.0, "vp_min": 0.30,
        "fs_max": 12, "going_block": "heavy", "arch_block": "Chaos",
    },
    "V6_GOLD_SEAM": {
        "class_num": (4,), "archetype": "Structure",
        "sp_lo": 3.0, "sp_hi": 4.0, "vp_min": 0.35,
        "fs_max": 12, "going_block": "heavy", "arch_block": "Chaos",
    },
}


# ── Lane mask ─────────────────────────────────────────────────────────────────

def lane_mask(df: pd.DataFrame, cfg: dict) -> pd.Series:
    m = (
        df["class_num"].isin(cfg["class_num"])
        & (df["archetype"] == cfg["archetype"])
        & (df["sp_decimal"] >= cfg["sp_lo"])
        & (df["sp_decimal"] <= cfg["sp_hi"])
        & (df["model_probability"] >= cfg["vp_min"])
        & (df["field_size"] <= cfg["fs_max"])
        & ~df["going"].str.lower().str.contains(cfg["going_block"], na=False)
        & (df["archetype"] != cfg["arch_block"])
    )
    return m


# ── Stats ─────────────────────────────────────────────────────────────────────

def _pl_series(sub: pd.DataFrame) -> pd.Series:
    return sub["won"] * (sub["sp_decimal"] - 1) + (1 - sub["won"]) * -1


def max_drawdown(pl_series: pd.Series) -> float:
    cumulative = pl_series.cumsum()
    peak = cumulative.cummax()
    drawdown = cumulative - peak
    return float(drawdown.min())


def longest_losing_run(won_series: pd.Series) -> int:
    max_run = run = 0
    for w in won_series:
        if w == 0:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run


def promotion_status(label: str, n: int, roi: float, fr: float) -> str:
    gates = PROMOTION_GATES.get(label, {})
    status_levels = list(gates.keys())
    achieved = []
    for level in reversed(status_levels):
        gate = gates[level]
        if n >= gate["n"] and roi >= gate["roi_min"] and fr >= gate["fr_min"]:
            achieved.append(level)
    if not achieved:
        # Find next gate
        for level in status_levels:
            gate = gates[level]
            if n < gate["n"]:
                remaining = gate["n"] - n
                return f"SHADOW_BUILDING → {level} needs +{remaining} more results"
        return "BUILDING"
    return achieved[0]


def analyse_lane(label: str, df: pd.DataFrame, has_res: pd.Series) -> dict:
    cfg = LANES[label]
    mask = lane_mask(df, cfg)
    total_cands = int(mask.sum())
    sub = df[mask & has_res].copy()
    n = len(sub)

    if n == 0:
        return {
            "label": label, "total_cands": total_cands, "n": 0, "wins": 0,
            "sr": 0.0, "fr": 0.0, "pl": 0.0, "roi": 0.0,
            "avg_sp": 0.0, "avg_vp": 0.0,
            "max_drawdown": 0.0, "longest_losing_run": 0,
            "status": "NO DATA", "freeze": False,
            "class_breakdown": {}, "fs_breakdown": {},
            "winners": [], "losers": [],
        }

    pl_ser = _pl_series(sub)
    pl = float(pl_ser.sum())
    roi = pl / n * 100
    wins = int(sub["won"].sum())
    placed_n = int(sub["placed"].sum())
    sr = wins / n * 100
    fr = placed_n / n * 100
    avg_sp = float(sub["sp_decimal"].mean())
    avg_vp = float(sub["model_probability"].mean())
    mdd = max_drawdown(pl_ser)
    llr = longest_losing_run(sub["won"].tolist())

    # Freeze check
    freeze = False
    freeze_reason = ""
    if n >= 20 and roi < 0:
        freeze = True
        freeze_reason = "ROI NEGATIVE at n≥20"
    if n >= 20 and fr < 70:
        freeze = True
        freeze_reason += " | FRAME RATE <70% at n≥20"

    status = promotion_status(label, n, roi, fr)
    if freeze:
        status = f"FROZEN — {freeze_reason.strip(' | ')}"

    # Class breakdown
    class_bd = {}
    for cls in sorted(sub["class_num"].dropna().unique()):
        b = sub[sub["class_num"] == cls]
        b_pl = float(_pl_series(b).sum())
        class_bd[f"CL{cls:.0f}"] = {
            "n": len(b), "wins": int(b["won"].sum()),
            "sr": b["won"].mean() * 100, "pl": b_pl,
        }

    # Field size breakdown
    fs_bd = {}
    for lo, hi, lbl in [(2, 5, "2-5"), (6, 8, "6-8"), (9, 12, "9-12"), (13, 20, "13+")]:
        b = sub[(sub["field_size"] >= lo) & (sub["field_size"] <= hi)]
        if len(b):
            b_pl = float(_pl_series(b).sum())
            fs_bd[lbl] = {
                "n": len(b), "wins": int(b["won"].sum()),
                "sr": b["won"].mean() * 100, "pl": b_pl,
            }

    # Winners / losers
    winners = sub[sub["won"] == 1].sort_values("sp_decimal", ascending=False)
    winners_list = [
        {
            "horse": row["horse"], "sp": row["sp_decimal"],
            "vp": row["model_probability"], "class": row["class_num"],
            "fs": row["field_size"], "date": row.get("date", ""),
        }
        for _, row in winners.iterrows()
    ]

    losers = sub[sub["won"] == 0].sort_values("model_probability", ascending=False).head(12)
    losers_list = [
        {
            "horse": row["horse"], "pos": row["result_position"],
            "sp": row["sp_decimal"], "vp": row["model_probability"],
            "class": row["class_num"], "fs": row["field_size"],
            "date": row.get("date", ""),
        }
        for _, row in losers.iterrows()
    ]

    return {
        "label": label, "total_cands": total_cands, "n": n, "wins": wins,
        "sr": sr, "fr": fr, "pl": pl, "roi": roi,
        "avg_sp": avg_sp, "avg_vp": avg_vp,
        "max_drawdown": mdd, "longest_losing_run": llr,
        "status": status, "freeze": freeze,
        "class_breakdown": class_bd, "fs_breakdown": fs_bd,
        "winners": winners_list, "losers": losers_list,
    }


# ── Comparison with previous ──────────────────────────────────────────────────

def load_prev(prev_path: str | None) -> dict:
    if not prev_path or not Path(prev_path).exists():
        return {}
    try:
        prev_df = pd.read_csv(prev_path, low_memory=False)
        out = {}
        for _, row in prev_df.iterrows():
            out[row["label"]] = {"n": row["n"], "roi": row["roi"], "pl": row["pl"]}
        return out
    except Exception:
        return {}


# ── Markdown builder ──────────────────────────────────────────────────────────

def build_md(results: list[dict], total_rows: int, total_results: int,
             prev: dict, run_ts: str) -> str:
    lines = []
    lines.append(f"# VÉLØ Execution Router Shadow Audit")
    lines.append(f"Generated: {run_ts}")
    lines.append(f"Dataset: {total_rows} rows | {total_results} with results")
    lines.append("")
    lines.append("**No live betting. No staking. Shadow annotation only.**")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Lane | n | SR | Frame | P&L | ROI | Drawdown | LLR | Status |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        p = prev.get(r["label"], {})
        roi_delta = f" ({r['roi'] - p['roi']:+.1f}%)" if p else ""
        lines.append(
            f"| {r['label']} | {r['n']} | {r['sr']:.1f}% | {r['fr']:.1f}% | "
            f"£{r['pl']:+.2f} | {r['roi']:+.1f}%{roi_delta} | "
            f"£{r['max_drawdown']:.2f} | {r['longest_losing_run']} | {r['status']} |"
        )
    lines.append("")

    # Previous comparison
    if prev:
        lines.append("## Change vs Previous Run")
        lines.append("")
        for r in results:
            p = prev.get(r["label"], {})
            if p:
                n_delta  = r["n"] - p.get("n", r["n"])
                roi_delta = r["roi"] - p.get("roi", r["roi"])
                pl_delta  = r["pl"] - p.get("pl", r["pl"])
                lines.append(f"**{r['label']}**: n {p.get('n','?')} → {r['n']} (+{n_delta}) | "
                              f"ROI {p.get('roi','?'):.1f}% → {r['roi']:.1f}% ({roi_delta:+.1f}%) | "
                              f"P&L £{p.get('pl','?'):.2f} → £{r['pl']:.2f} ({pl_delta:+.2f})")
        lines.append("")

    # Per-lane detail
    for r in results:
        lines.append(f"## {r['label']}")
        lines.append("")
        low_sample = " *** LOW SAMPLE ***" if r["n"] < 30 else ""
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| n (with results) | {r['n']}{low_sample} |")
        lines.append(f"| Wins | {r['wins']} |")
        lines.append(f"| Strike rate | {r['sr']:.1f}% |")
        lines.append(f"| Frame/placed rate | {r['fr']:.1f}% |")
        lines.append(f"| Flat 1pt P&L | £{r['pl']:+.2f} |")
        lines.append(f"| ROI | {r['roi']:+.1f}% |")
        lines.append(f"| Avg SP | {r['avg_sp']:.2f} |")
        lines.append(f"| Avg VP | {r['avg_vp']:.3f} |")
        lines.append(f"| Max drawdown | £{r['max_drawdown']:.2f} |")
        lines.append(f"| Longest losing run | {r['longest_losing_run']} |")
        lines.append(f"| Status | **{r['status']}** |")
        lines.append(f"| Freeze active | {'YES — ' + r['status'] if r['freeze'] else 'NO'} |")
        lines.append("")

        if r["class_breakdown"]:
            lines.append("**Class breakdown:**")
            lines.append("")
            lines.append("| Class | n | SR | P&L |")
            lines.append("|---|---|---|---|")
            for cls, b in r["class_breakdown"].items():
                lines.append(f"| {cls} | {b['n']} | {b['sr']:.0f}% | £{b['pl']:+.2f} |")
            lines.append("")

        if r["fs_breakdown"]:
            lines.append("**Field size breakdown:**")
            lines.append("")
            lines.append("| Field size | n | SR | P&L |")
            lines.append("|---|---|---|---|")
            for fs_lbl, b in r["fs_breakdown"].items():
                lines.append(f"| {fs_lbl} | {b['n']} | {b['sr']:.0f}% | £{b['pl']:+.2f} |")
            lines.append("")

        if r["winners"]:
            lines.append("**Winners:**")
            lines.append("")
            lines.append("| Horse | Date | SP | VP | Class | FS |")
            lines.append("|---|---|---|---|---|---|")
            for w in r["winners"]:
                lines.append(f"| {w['horse']} | {w['date']} | {w['sp']:.1f} | {w['vp']:.3f} | CL{w['class']:.0f} | {w['fs']:.0f} |")
            lines.append("")

        if r["losers"]:
            lines.append("**Top losers (by VP):**")
            lines.append("")
            lines.append("| Horse | Date | Pos | SP | VP | Class | FS |")
            lines.append("|---|---|---|---|---|---|---|")
            for lo in r["losers"]:
                lines.append(f"| {lo['horse']} | {lo['date']} | {lo['pos']} | {lo['sp']:.1f} | {lo['vp']:.3f} | CL{lo['class']:.0f} | {lo['fs']:.0f} |")
            lines.append("")

    # Promotion gates
    lines.append("## Promotion Gates")
    lines.append("")
    lines.append("| Lane | Gate | n Required | Current n | Remaining |")
    lines.append("|---|---|---|---|---|")
    for label, gates in PROMOTION_GATES.items():
        res = next((r for r in results if r["label"] == label), None)
        curr_n = res["n"] if res else 0
        for gate_name, cfg in gates.items():
            remaining = max(0, cfg["n"] - curr_n)
            lines.append(f"| {label} | {gate_name} | {cfg['n']} | {curr_n} | {remaining if remaining else 'REACHED'} |")
    lines.append("")

    # Freeze rules
    lines.append("## Freeze Rules (always active)")
    lines.append("")
    for rule, desc in FREEZE_RULES.items():
        lines.append(f"- **{rule}**: {desc}")
    lines.append("")

    lines.append("---")
    lines.append("*No live betting. No staking. Shadow annotation only.*")
    lines.append(f"*Safety: SQPE untouched | Playbook E untouched | model_probability read-only*")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Router shadow lane audit")
    parser.add_argument("--prev-csv", help="Path to previous audit CSV for comparison")
    parser.add_argument("--input", default=str(DEDUPED_PATH), help="Input deduped CSV path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    df = pd.read_csv(input_path, low_memory=False)
    has_res = df["result_position"].notna() & (df["sp_decimal"] > 0)

    print(f"Dataset: {len(df)} rows | {has_res.sum()} with results")
    print(f"Running audit on {len(LANES)} lanes...\n")

    results = []
    for label in LANES:
        r = analyse_lane(label, df, has_res)
        results.append(r)
        status_flag = "*** FROZEN ***" if r["freeze"] else ""
        print(f"  {label}: n={r['n']}, SR={r['sr']:.1f}%, Frame={r['fr']:.1f}%, "
              f"ROI={r['roi']:+.1f}%, LLR={r['longest_losing_run']}, DD=£{r['max_drawdown']:.2f}  {status_flag}")
        print(f"    Status: {r['status']}")

    # Load previous for comparison
    prev = load_prev(args.prev_csv)

    run_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── CSV output ────────────────────────────────────────────────────────────
    csv_rows = []
    for r in results:
        csv_rows.append({
            "label": r["label"],
            "total_cands": r["total_cands"],
            "n": r["n"],
            "wins": r["wins"],
            "sr": round(r["sr"], 2),
            "fr": round(r["fr"], 2),
            "pl": round(r["pl"], 2),
            "roi": round(r["roi"], 2),
            "avg_sp": round(r["avg_sp"], 3),
            "avg_vp": round(r["avg_vp"], 3),
            "max_drawdown": round(r["max_drawdown"], 2),
            "longest_losing_run": r["longest_losing_run"],
            "status": r["status"],
            "freeze": r["freeze"],
            "run_ts": run_ts,
        })
    audit_df = pd.DataFrame(csv_rows)
    audit_df.to_csv(AUDIT_CSV, index=False)
    print(f"\nSaved: {AUDIT_CSV}")

    # ── Markdown output ───────────────────────────────────────────────────────
    md = build_md(results, len(df), int(has_res.sum()), prev, run_ts)
    AUDIT_MD.write_text(md)
    print(f"Saved: {AUDIT_MD}")

    # ── Console summary ───────────────────────────────────────────────────────
    print(f"\n{'='*56}")
    print(f"EXECUTION ROUTER EVIDENCE ENGINE — {run_ts}")
    print(f"{'='*56}")
    print(f"{'Lane':<22} {'n':>4} {'SR':>6} {'Frame':>6} {'P&L':>8} {'ROI':>7}  Status")
    print(f"{'-'*22} {'-'*4} {'-'*6} {'-'*6} {'-'*8} {'-'*7}  ------")
    for r in results:
        print(f"{r['label']:<22} {r['n']:>4} {r['sr']:>5.1f}% {r['fr']:>5.1f}% "
              f"{r['pl']:>+8.2f} {r['roi']:>+6.1f}%  {r['status'][:40]}")

    any_frozen = any(r["freeze"] for r in results)
    if any_frozen:
        print("\n*** WARNING: ONE OR MORE LANES FROZEN — SEE AUDIT FOR DETAILS ***")
    else:
        print("\nAll lanes healthy. No freeze conditions met.")


if __name__ == "__main__":
    main()
