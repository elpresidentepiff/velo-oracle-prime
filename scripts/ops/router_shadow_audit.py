"""
router_shadow_audit.py
=======================
Execution Router Evidence Engine — shadow lane analysis only.

Every run writes:
  1. Latest outputs (always overwritten):
       data/router_shadow_audit_latest.csv
       data/router_shadow_audit_latest.md
  2. Timestamped immutable snapshot:
       data/router_shadow_audit_runs/router_shadow_audit_<YYYYMMDD_HHMMSS>.csv
       data/router_shadow_audit_runs/router_shadow_audit_<YYYYMMDD_HHMMSS>.md
  3. Append-only ledger (never overwritten, only appended):
       data/router_shadow_audit_ledger.csv

Router lanes audited:
  V1_BASE         — Class 3|4, Structure, SP 2-4, VP≥0.30, FS≤12
  V2_CLASS4_ONLY  — Class 4,   Structure, SP 2-4, VP≥0.30, FS≤12
  V6_GOLD_SEAM    — Class 4,   Structure, SP 3-4, VP≥0.35, FS≤12

No live betting. No model changes. No staking.

Usage:
  python scripts/router_shadow_audit.py
  python scripts/router_shadow_audit.py --prev-csv data/router_shadow_audit_latest.csv
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

DEDUPED_PATH = ROOT / "data" / "velo_innovation_protocol_1k_deduped.csv"
AUDIT_CSV    = ROOT / "data" / "router_shadow_audit_latest.csv"
AUDIT_MD     = ROOT / "data" / "router_shadow_audit_latest.md"
RUNS_DIR     = ROOT / "data" / "router_shadow_audit_runs"
LEDGER_PATH  = ROOT / "data" / "router_shadow_audit_ledger.csv"

LEDGER_COLS = [
    "run_ts", "dataset_rows", "result_rows",
    "lane", "n", "wins", "strike_rate", "frame_rate",
    "pnl", "roi", "max_drawdown", "longest_losing_run",
    "status", "freeze_flag", "threshold_message",
]

PROMOTION_GATES = {
    "V1_BASE": [
        ("WATCHLIST",        {"n": 27,  "roi_min": 0.0, "fr_min": 75.0}),
        ("SHADOW_CANDIDATE", {"n": 50,  "roi_min": 0.0, "fr_min": 75.0}),
        ("PAPER_EXECUTION",  {"n": 100, "roi_min": 0.0, "fr_min": 75.0}),
    ],
    "V2_CLASS4_ONLY": [
        ("WATCHLIST",        {"n": 20,  "roi_min": 0.0, "fr_min": 0.0}),
        ("SHADOW_CANDIDATE", {"n": 30,  "roi_min": 0.0, "fr_min": 75.0}),
        ("PAPER_EXECUTION",  {"n": 60,  "roi_min": 0.0, "fr_min": 75.0}),
        ("LIVE_DISCUSSION",  {"n": 100, "roi_min": 0.0, "fr_min": 75.0}),
    ],
    "V6_GOLD_SEAM": [
        ("SHADOW_CANDIDATE", {"n": 20,  "roi_min": 0.0, "fr_min": 0.0}),
        ("PAPER_EXECUTION",  {"n": 50,  "roi_min": 0.0, "fr_min": 75.0}),
    ],
}

FREEZE_RULES = {
    "roi_negative_after_n20":    "n≥20 and ROI < 0 → LANE_FROZEN",
    "frame_below_70_after_n20":  "n≥20 and frame rate < 70% → LANE_FROZEN",
    "duplicate_contamination":   "dedup key collision rate >5% → STOP AND FIX",
    "unexpected_n_drop":         "n decreases between runs → STOP AND INVESTIGATE",
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
    return (
        df["class_num"].isin(cfg["class_num"])
        & (df["archetype"] == cfg["archetype"])
        & (df["sp_decimal"] >= cfg["sp_lo"])
        & (df["sp_decimal"] <= cfg["sp_hi"])
        & (df["model_probability"] >= cfg["vp_min"])
        & (df["field_size"] <= cfg["fs_max"])
        & ~df["going"].str.lower().str.contains(cfg["going_block"], na=False)
        & (df["archetype"] != cfg["arch_block"])
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

def _pl_series(sub: pd.DataFrame) -> pd.Series:
    return sub["won"] * (sub["sp_decimal"] - 1) + (1 - sub["won"]) * -1


def max_drawdown(pl_series: pd.Series) -> float:
    cum = pl_series.cumsum()
    peak = cum.cummax()
    return float((cum - peak).min())


def longest_losing_run(won_list: list) -> int:
    max_run = run = 0
    for w in won_list:
        if w == 0:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run


# ── Promotion + threshold ─────────────────────────────────────────────────────

def _eval_gates(label: str, n: int, roi: float, fr: float) -> tuple[str, str]:
    """Returns (status_label, threshold_message)."""
    gates = PROMOTION_GATES.get(label, [])
    highest_achieved = None
    for gate_name, cfg in gates:
        if n >= cfg["n"] and roi >= cfg["roi_min"] and fr >= cfg["fr_min"]:
            highest_achieved = gate_name

    # Next gate not yet achieved
    next_gate = next_threshold = None
    for gate_name, cfg in gates:
        if n < cfg["n"] or roi < cfg["roi_min"] or fr < cfg["fr_min"]:
            next_gate = gate_name
            remaining_n = max(0, cfg["n"] - n)
            next_threshold = (
                f"→ {gate_name}: needs +{remaining_n} results"
                + (f", ROI≥0" if roi < cfg["roi_min"] else "")
                + (f", Frame≥{cfg['fr_min']:.0f}%" if fr < cfg["fr_min"] else "")
            )
            break

    if highest_achieved:
        status = highest_achieved
        msg = next_threshold or "ALL GATES REACHED"
    else:
        status = "LOW_SAMPLE" if n < 10 else "SHADOW_BUILDING"
        msg = next_threshold or "NO GATES DEFINED"

    return status, msg


def threshold_detail(label: str, n: int) -> str:
    """Verbose threshold breakdown for console output."""
    if label == "V2_CLASS4_ONLY":
        lines = [
            f"  V2 threshold tracker:",
            f"    current n:                {n}",
            f"    → WATCHLIST:              needs_to +{max(0, 20 - n)} (target 20)",
            f"    → SHADOW_ROUTER_CANDIDATE: needs_to +{max(0, 30 - n)} (target 30)",
            f"    → PAPER_EXECUTION:         needs_to +{max(0, 60 - n)} (target 60)",
            f"    → LIVE_DISCUSSION:         needs_to +{max(0, 100 - n)} (target 100)",
        ]
    elif label == "V6_GOLD_SEAM":
        lines = [
            f"  V6 threshold tracker:",
            f"    current n:                        {n}",
            f"    → SHADOW_CANDIDATE:               needs_to +{max(0, 20 - n)} (target 20)",
            f"    → MIN_PROMOTION_REVIEW:            needs_to +{max(0, 50 - n)} (target 50)",
        ]
    else:
        lines = [
            f"  V1 threshold tracker:",
            f"    current n:                {n}",
            f"    → WATCHLIST:              needs_to +{max(0, 27 - n)} (target 27)",
            f"    → SHADOW_CANDIDATE:       needs_to +{max(0, 50 - n)} (target 50)",
            f"    → PAPER_EXECUTION:        needs_to +{max(0, 100 - n)} (target 100)",
        ]
    return "\n".join(lines)


# ── Lane analysis ─────────────────────────────────────────────────────────────

def analyse_lane(label: str, df: pd.DataFrame, has_res: pd.Series) -> dict:
    cfg = LANES[label]
    mask = lane_mask(df, cfg)
    total_cands = int(mask.sum())
    sub = df[mask & has_res].copy()
    n = len(sub)

    empty = {
        "label": label, "total_cands": total_cands, "n": 0, "wins": 0,
        "sr": 0.0, "fr": 0.0, "pl": 0.0, "roi": 0.0,
        "avg_sp": 0.0, "avg_vp": 0.0, "max_drawdown": 0.0,
        "longest_losing_run": 0, "status": "NO_DATA", "lane_state": "LOW_SAMPLE",
        "freeze": False, "freeze_reasons": [],
        "threshold_msg": "NO DATA — run race days to build sample",
        "class_breakdown": {}, "fs_breakdown": {}, "winners": [], "losers": [],
    }
    if n == 0:
        return empty

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

    # ── Freeze evaluation ─────────────────────────────────────────────────────
    freeze_reasons = []
    if n >= 20 and roi < 0:
        freeze_reasons.append("ROI_NEGATIVE_AT_N20+")
    if n >= 20 and fr < 70.0:
        freeze_reasons.append("FRAME_BELOW_70_AT_N20+")
    freeze = bool(freeze_reasons)

    # ── Status + lane_state ───────────────────────────────────────────────────
    status, threshold_msg = _eval_gates(label, n, roi, fr)

    if freeze:
        lane_state = "LANE_FROZEN"
        status = f"LANE_FROZEN — {' | '.join(freeze_reasons)}"
    elif n < 10:
        lane_state = "LOW_SAMPLE"
    elif status == "SHADOW_BUILDING":
        lane_state = "LANE_ACTIVE"
    elif status in ("WATCHLIST", "SHADOW_CANDIDATE", "PAPER_EXECUTION", "LIVE_DISCUSSION"):
        lane_state = "WATCHLIST" if status == "WATCHLIST" else "SHADOW_ROUTER_CANDIDATE"
    else:
        lane_state = "LANE_ACTIVE"

    # ── Class breakdown ───────────────────────────────────────────────────────
    class_bd = {}
    for cls in sorted(sub["class_num"].dropna().unique()):
        b = sub[sub["class_num"] == cls]
        b_pl = float(_pl_series(b).sum())
        class_bd[f"CL{cls:.0f}"] = {
            "n": len(b), "wins": int(b["won"].sum()),
            "sr": b["won"].mean() * 100, "pl": b_pl,
        }

    # ── Field size breakdown ──────────────────────────────────────────────────
    fs_bd = {}
    for lo, hi, lbl in [(2, 5, "2-5"), (6, 8, "6-8"), (9, 12, "9-12"), (13, 20, "13+")]:
        b = sub[(sub["field_size"] >= lo) & (sub["field_size"] <= hi)]
        if len(b):
            b_pl = float(_pl_series(b).sum())
            fs_bd[lbl] = {
                "n": len(b), "wins": int(b["won"].sum()),
                "sr": b["won"].mean() * 100, "pl": b_pl,
            }

    # ── Winners / losers ──────────────────────────────────────────────────────
    winners_list = [
        {
            "horse": row["horse"], "sp": row["sp_decimal"],
            "vp": row["model_probability"], "class": row["class_num"],
            "fs": row["field_size"], "date": row.get("date", ""),
        }
        for _, row in sub[sub["won"] == 1].sort_values("sp_decimal", ascending=False).iterrows()
    ]

    losers_list = [
        {
            "horse": row["horse"], "pos": row["result_position"],
            "sp": row["sp_decimal"], "vp": row["model_probability"],
            "class": row["class_num"], "fs": row["field_size"],
            "date": row.get("date", ""),
        }
        for _, row in sub[sub["won"] == 0].sort_values("model_probability", ascending=False).head(12).iterrows()
    ]

    return {
        "label": label, "total_cands": total_cands, "n": n, "wins": wins,
        "sr": sr, "fr": fr, "pl": pl, "roi": roi,
        "avg_sp": avg_sp, "avg_vp": avg_vp,
        "max_drawdown": mdd, "longest_losing_run": llr,
        "status": status, "lane_state": lane_state,
        "freeze": freeze, "freeze_reasons": freeze_reasons,
        "threshold_msg": threshold_msg,
        "class_breakdown": class_bd, "fs_breakdown": fs_bd,
        "winners": winners_list, "losers": losers_list,
    }


# ── Prev comparison ───────────────────────────────────────────────────────────

def load_prev(prev_path: str | None) -> dict:
    if not prev_path or not Path(prev_path).exists():
        return {}
    try:
        prev_df = pd.read_csv(prev_path, low_memory=False)
        return {
            row["label"]: {"n": row["n"], "roi": row["roi"], "pl": row["pl"]}
            for _, row in prev_df.iterrows()
        }
    except Exception:
        return {}


# ── Markdown builder ──────────────────────────────────────────────────────────

def build_md(results: list[dict], total_rows: int, total_results: int,
             prev: dict, run_ts: str) -> str:
    lines = [
        "# VÉLØ Execution Router Shadow Audit",
        f"Generated: {run_ts}",
        f"Dataset: {total_rows} rows | {total_results} with results",
        "",
        "**No live betting. No staking. Shadow annotation only.**",
        "",
        "## Summary",
        "",
        "| Lane | State | n | SR | Frame | P&L | ROI | DD | LLR | Status |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        p = prev.get(r["label"], {})
        roi_delta = f" ({r['roi'] - p['roi']:+.1f}%)" if p else ""
        lines.append(
            f"| {r['label']} | {r['lane_state']} | {r['n']} | {r['sr']:.1f}% | {r['fr']:.1f}% | "
            f"£{r['pl']:+.2f} | {r['roi']:+.1f}%{roi_delta} | "
            f"£{r['max_drawdown']:.2f} | {r['longest_losing_run']} | {r['status'][:45]} |"
        )
    lines.append("")

    # Delta vs previous
    if prev:
        lines += ["## Change vs Previous Run", ""]
        for r in results:
            p = prev.get(r["label"], {})
            if p:
                n_d   = r["n"] - p.get("n", r["n"])
                roi_d = r["roi"] - p.get("roi", r["roi"])
                pl_d  = r["pl"] - p.get("pl", r["pl"])
                lines.append(
                    f"**{r['label']}**: n {p.get('n','?')} → {r['n']} (+{n_d}) | "
                    f"ROI {p.get('roi', 0):.1f}% → {r['roi']:.1f}% ({roi_d:+.1f}%) | "
                    f"P&L £{p.get('pl', 0):.2f} → £{r['pl']:.2f} ({pl_d:+.2f})"
                )
        lines.append("")

    # Per-lane detail
    for r in results:
        low_warn = "  *** LOW SAMPLE ***" if r["n"] < 30 else ""
        lines += [
            f"## {r['label']}",
            "",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Lane state | **{r['lane_state']}** |",
            f"| n (with results) | {r['n']}{low_warn} |",
            f"| Wins | {r['wins']} |",
            f"| Strike rate | {r['sr']:.1f}% |",
            f"| Frame/placed rate | {r['fr']:.1f}% |",
            f"| Flat 1pt P&L | £{r['pl']:+.2f} |",
            f"| ROI | {r['roi']:+.1f}% |",
            f"| Avg SP | {r['avg_sp']:.2f} |",
            f"| Avg VP | {r['avg_vp']:.3f} |",
            f"| Max drawdown | £{r['max_drawdown']:.2f} |",
            f"| Longest losing run | {r['longest_losing_run']} |",
            f"| Status | **{r['status']}** |",
            f"| Freeze active | {'YES — ' + ' | '.join(r['freeze_reasons']) if r['freeze'] else 'NO'} |",
            f"| Next threshold | {r['threshold_msg']} |",
            "",
        ]

        if r["class_breakdown"]:
            lines += ["**Class breakdown:**", "", "| Class | n | SR | P&L |", "|---|---|---|---|"]
            for cls, b in r["class_breakdown"].items():
                lines.append(f"| {cls} | {b['n']} | {b['sr']:.0f}% | £{b['pl']:+.2f} |")
            lines.append("")

        if r["fs_breakdown"]:
            lines += ["**Field size breakdown:**", "", "| FS | n | SR | P&L |", "|---|---|---|---|"]
            for fs_lbl, b in r["fs_breakdown"].items():
                lines.append(f"| {fs_lbl} | {b['n']} | {b['sr']:.0f}% | £{b['pl']:+.2f} |")
            lines.append("")

        if r["winners"]:
            lines += ["**Winners:**", "", "| Horse | Date | SP | VP | Class | FS |", "|---|---|---|---|---|---|"]
            for w in r["winners"]:
                lines.append(f"| {w['horse']} | {w['date']} | {w['sp']:.1f} | {w['vp']:.3f} | CL{w['class']:.0f} | {w['fs']:.0f} |")
            lines.append("")

        if r["losers"]:
            lines += ["**Top losers (by VP):**", "", "| Horse | Date | Pos | SP | VP | Class | FS |", "|---|---|---|---|---|---|---|"]
            for lo in r["losers"]:
                lines.append(f"| {lo['horse']} | {lo['date']} | {lo['pos']} | {lo['sp']:.1f} | {lo['vp']:.3f} | CL{lo['class']:.0f} | {lo['fs']:.0f} |")
            lines.append("")

    # Promotion gates table
    lines += ["## Promotion Gates", "", "| Lane | Gate | Needs n | Current n | Remaining | ROI gate | Frame gate |", "|---|---|---|---|---|---|---|"]
    for label, gates in PROMOTION_GATES.items():
        res = next((r for r in results if r["label"] == label), None)
        curr_n = res["n"] if res else 0
        for gate_name, cfg in gates:
            remaining = max(0, cfg["n"] - curr_n)
            lines.append(
                f"| {label} | {gate_name} | {cfg['n']} | {curr_n} | "
                f"{'REACHED' if not remaining else remaining} | "
                f"≥{cfg['roi_min']:.0f}% | ≥{cfg['fr_min']:.0f}% |"
            )
    lines.append("")

    # Freeze rules
    lines += ["## Freeze Rules (always active)", ""]
    for rule, desc in FREEZE_RULES.items():
        lines.append(f"- **{rule}**: {desc}")
    lines += [
        "",
        "---",
        "*No live betting. No staking. Shadow annotation only.*",
        "*Safety: SQPE untouched | Playbook E untouched | model_probability read-only*",
    ]
    return "\n".join(lines)


# ── Ledger append ─────────────────────────────────────────────────────────────

def append_ledger(results: list[dict], run_ts: str,
                  total_rows: int, total_results: int) -> int:
    new_rows = []
    for r in results:
        new_rows.append({
            "run_ts": run_ts,
            "dataset_rows": total_rows,
            "result_rows": total_results,
            "lane": r["label"],
            "n": r["n"],
            "wins": r["wins"],
            "strike_rate": round(r["sr"], 2),
            "frame_rate": round(r["fr"], 2),
            "pnl": round(r["pl"], 2),
            "roi": round(r["roi"], 2),
            "max_drawdown": round(r["max_drawdown"], 2),
            "longest_losing_run": r["longest_losing_run"],
            "status": r["lane_state"],
            "freeze_flag": r["freeze"],
            "threshold_message": r["threshold_msg"],
        })
    new_df = pd.DataFrame(new_rows, columns=LEDGER_COLS)

    if LEDGER_PATH.exists():
        existing = pd.read_csv(LEDGER_PATH, low_memory=False)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_csv(LEDGER_PATH, index=False)
    return len(combined)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Router shadow lane audit — evidence ledger")
    parser.add_argument("--prev-csv", help="Previous audit CSV for delta comparison")
    parser.add_argument("--input", default=str(DEDUPED_PATH), help="Deduped dataset path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input not found: {input_path}")
        sys.exit(1)

    df = pd.read_csv(input_path, low_memory=False)
    has_res = df["result_position"].notna() & (df["sp_decimal"] > 0)
    total_rows = len(df)
    total_results = int(has_res.sum())

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ts_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(f"Dataset: {total_rows} rows | {total_results} with results")
    print(f"Run timestamp: {run_ts}")
    print(f"Running audit on {len(LANES)} lanes...\n")

    # ── Analyse each lane ─────────────────────────────────────────────────────
    results = []
    for label in LANES:
        r = analyse_lane(label, df, has_res)
        results.append(r)

        state_tag = "*** FROZEN ***" if r["freeze"] else r["lane_state"]
        print(f"  {label}")
        print(f"    State:  {state_tag}")
        print(f"    n={r['n']}  SR={r['sr']:.1f}%  Frame={r['fr']:.1f}%  "
              f"ROI={r['roi']:+.1f}%  DD=£{r['max_drawdown']:.2f}  LLR={r['longest_losing_run']}")
        print(f"    Status: {r['status']}")
        if r["freeze"]:
            print(f"    FREEZE: {' | '.join(r['freeze_reasons'])}")
        print(threshold_detail(label, r["n"]))
        print()

    prev = load_prev(args.prev_csv)

    # ── Build outputs ─────────────────────────────────────────────────────────
    md = build_md(results, total_rows, total_results, prev, run_ts)

    csv_rows = []
    for r in results:
        csv_rows.append({
            "label": r["label"], "total_cands": r["total_cands"],
            "n": r["n"], "wins": r["wins"],
            "sr": round(r["sr"], 2), "fr": round(r["fr"], 2),
            "pl": round(r["pl"], 2), "roi": round(r["roi"], 2),
            "avg_sp": round(r["avg_sp"], 3), "avg_vp": round(r["avg_vp"], 3),
            "max_drawdown": round(r["max_drawdown"], 2),
            "longest_losing_run": r["longest_losing_run"],
            "lane_state": r["lane_state"], "status": r["status"],
            "freeze": r["freeze"], "threshold_msg": r["threshold_msg"],
            "run_ts": run_ts,
        })
    audit_df = pd.DataFrame(csv_rows)

    # 1. Latest (overwritten each run)
    audit_df.to_csv(AUDIT_CSV, index=False)
    AUDIT_MD.write_text(md, encoding="utf-8")

    # 2. Timestamped snapshot (immutable)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    snap_csv = RUNS_DIR / f"router_shadow_audit_{ts_tag}.csv"
    snap_md  = RUNS_DIR / f"router_shadow_audit_{ts_tag}.md"
    audit_df.to_csv(snap_csv, index=False)
    snap_md.write_text(md, encoding="utf-8")

    # 3. Append-only ledger
    ledger_rows = append_ledger(results, run_ts, total_rows, total_results)

    # ── Console summary ───────────────────────────────────────────────────────
    print(f"{'='*60}")
    print(f"EXECUTION ROUTER EVIDENCE ENGINE — {run_ts}")
    print(f"{'='*60}")
    print(f"{'Lane':<22} {'State':<22} {'n':>4} {'SR':>6} {'Frame':>6} {'P&L':>8} {'ROI':>7}")
    print(f"{'-'*22} {'-'*22} {'-'*4} {'-'*6} {'-'*6} {'-'*8} {'-'*7}")
    for r in results:
        print(f"{r['label']:<22} {r['lane_state']:<22} {r['n']:>4} {r['sr']:>5.1f}% "
              f"{r['fr']:>5.1f}% {r['pl']:>+8.2f} {r['roi']:>+6.1f}%")

    any_frozen = any(r["freeze"] for r in results)
    print()
    if any_frozen:
        print("*** WARNING: ONE OR MORE LANES FROZEN — NO FURTHER PROMOTION UNTIL RESOLVED ***")
    else:
        print("All lanes healthy. No freeze conditions triggered.")

    print(f"\nOutputs:")
    print(f"  Latest:     {AUDIT_CSV.name}")
    print(f"              {AUDIT_MD.name}")
    print(f"  Snapshot:   {snap_csv.name}")
    print(f"              {snap_md.name}")
    print(f"  Ledger:     {LEDGER_PATH.name}  ({ledger_rows} total rows)")


if __name__ == "__main__":
    main()
