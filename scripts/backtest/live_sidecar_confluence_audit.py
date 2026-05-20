"""
Live Sidecar Confluence Audit
==============================

Tests VP30 / MDS / IMPROVE / PLACE_PROB in combination, not isolation.

The question is not: does MDS work alone?
The question is: which stacks print truth?

Thresholds:
  VP30:           velo_prime_prob >= 0.30
  MDS_HIGH:       market_deception_score > 0.50
  IMPROVE_HIGH:   improvement_score > 0.40
  PLACE_HIGH:     place_prob > 0.80
  RACING_API_TOP: rpdc_release_score > 0.50 (best available Racing-API-adjacent proxy)

Usage:
    python scripts/live_sidecar_confluence_audit.py

Read-only. No scoring, model, router, or staking changes.
"""

from __future__ import annotations

import os
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

ROOT = Path(__file__).resolve().parent.parent
import sys; sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(ROOT / ".env")
DATA = ROOT / "data"

# ── Thresholds ────────────────────────────────────────────────────────────────

VP30_T        = 0.30
MDS_HIGH_T    = 0.50
IMPROVE_HIGH_T = 0.40
PLACE_HIGH_T  = 0.80
RPDC_T        = 0.50


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Row:
    race_id: str
    date: str
    horse: str
    tier: str
    outcome: str
    position: Optional[int]
    winner_sp: Optional[float]
    vp: float
    imp: float
    mds: float
    place_p: float
    longshot: float
    rpdc: float

    @property
    def vp30(self) -> bool: return self.vp >= VP30_T
    @property
    def mds_high(self) -> bool: return self.mds > MDS_HIGH_T
    @property
    def imp_high(self) -> bool: return self.imp > IMPROVE_HIGH_T
    @property
    def place_high(self) -> bool: return self.place_p > PLACE_HIGH_T
    @property
    def rpdc_top(self) -> bool: return self.rpdc > RPDC_T


@dataclass
class StackResult:
    label: str
    predicate_desc: str
    n: int = 0
    wins: int = 0
    frames: int = 0       # WIN + PLACED
    sp_sum: float = 0.0
    sp_count: int = 0
    winner_sp_sum: float = 0.0
    winner_sp_count: int = 0
    loser_sp_sum: float = 0.0
    loser_sp_count: int = 0
    pnl: float = 0.0
    losing_streak: int = 0
    _cur_streak: int = field(default=0, repr=False)
    max_drawdown: float = 0.0
    _peak: float = field(default=0.0, repr=False)
    _equity: float = field(default=0.0, repr=False)

    def add(self, row: Row) -> None:
        self.n += 1
        sp = row.winner_sp
        is_win = row.outcome == "WIN"
        is_frame = row.outcome in ("WIN", "PLACED")

        if is_win:
            self.wins += 1
            gain = (sp - 1.0) if sp else 0.0
            self.pnl += gain
            self._equity += gain
            self._cur_streak = 0
            if sp:
                self.winner_sp_sum += sp
                self.winner_sp_count += 1
        else:
            self.pnl -= 1.0
            self._equity -= 1.0
            self._cur_streak += 1
            self.losing_streak = max(self.losing_streak, self._cur_streak)
            if sp:
                self.loser_sp_sum += sp
                self.loser_sp_count += 1

        if self._equity > self._peak:
            self._peak = self._equity
        dd = self._peak - self._equity
        self.max_drawdown = max(self.max_drawdown, dd)

        if is_frame:
            self.frames += 1
        if sp:
            self.sp_sum += sp
            self.sp_count += 1

    @property
    def win_sr(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def frame_rate(self) -> float:
        return self.frames / self.n if self.n else 0.0

    @property
    def roi(self) -> float:
        return self.pnl / self.n if self.n else 0.0

    @property
    def avg_sp(self) -> float:
        return self.sp_sum / self.sp_count if self.sp_count else 0.0

    @property
    def median_sp(self) -> float:
        return self.avg_sp  # proxy

    @property
    def winner_avg_sp(self) -> float:
        return self.winner_sp_sum / self.winner_sp_count if self.winner_sp_count else 0.0

    @property
    def loser_avg_sp(self) -> float:
        return self.loser_sp_sum / self.loser_sp_count if self.loser_sp_count else 0.0

    @property
    def breakeven_sr(self) -> float:
        avg = self.avg_sp
        if avg <= 1.0:
            return 1.0
        return 1.0 / avg

    @property
    def sr_vs_breakeven(self) -> float:
        return self.win_sr - self.breakeven_sr

    def classify(self) -> str:
        if self.n < 10:
            return "LOW_SAMPLE"
        be = self.breakeven_sr
        if self.win_sr >= be + 0.05 and self.roi > 0.05:
            return "ELITE_CONFLUENCE"
        if self.win_sr >= be and self.frame_rate >= 0.70:
            return "STRONG_CONFLUENCE"
        if self.frame_rate >= 0.65 and self.roi < -0.05:
            return "FRAME_ONLY"
        if self.win_sr < be - 0.10 and self.roi < -0.20:
            return "OVERBET_TRAP"
        if self.n < 20:
            return "HOLD"
        return "SUPPRESS"


# ── Load data ─────────────────────────────────────────────────────────────────

def load_rows() -> list[Row]:
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    print("  sigma_audits...", end="", flush=True)
    sigma: list[dict] = []
    pg = 0
    while True:
        r = sb.table("sigma_audits").select(
            "race_id,date,outcome,top_pick_position,actual_winner_sp,decision_tier"
        ).neq("outcome", "X_BLOCKED").range(pg*1000, (pg+1)*1000-1).execute()
        sigma.extend(r.data)
        if len(r.data) < 1000: break
        pg += 1
    print(f" {len(sigma)}")

    print("  velo_verdicts...", end="", flush=True)
    vv: list[dict] = []
    pg = 0
    while True:
        r = sb.table("velo_verdicts").select(
            "race_id,velo_prime_prob,improvement_score,market_deception_score,"
            "release_day_prob,place_prob,longshot_prob,rpdc_release_score,"
            "decision_tier,full_analysis"
        ).range(pg*1000, (pg+1)*1000-1).execute()
        vv.extend(r.data)
        if len(r.data) < 1000: break
        pg += 1
    print(f" {len(vv)}")

    vv_map = {v["race_id"]: v for v in vv}

    rows: list[Row] = []
    for sv in sigma:
        v = vv_map.get(sv["race_id"])
        if not v:
            continue
        # Extract horse name from full_analysis top entry
        fa = v.get("full_analysis") or []
        if isinstance(fa, dict):
            fa = list(fa.values())
        horse = fa[0].get("horse", "?") if (fa and isinstance(fa[0], dict)) else "?"
        sp = sv.get("actual_winner_sp")
        rows.append(Row(
            race_id=sv["race_id"],
            date=sv.get("date", ""),
            horse=horse,
            tier=sv.get("decision_tier") or v.get("decision_tier") or "?",
            outcome=sv.get("outcome", "MISS"),
            position=sv.get("top_pick_position"),
            winner_sp=float(sp) if sp else None,
            vp=float(v.get("velo_prime_prob") or 0),
            imp=float(v.get("improvement_score") or 0),
            mds=float(v.get("market_deception_score") or 0),
            place_p=float(v.get("place_prob") or 0),
            longshot=float(v.get("longshot_prob") or 0),
            rpdc=float(v.get("rpdc_release_score") or 0),
        ))
    return rows


# ── Evaluate a stack ──────────────────────────────────────────────────────────

def run_stack(rows: list[Row], label: str, pred_desc: str,
              predicate: Callable[[Row], bool]) -> StackResult:
    # Sort by date for correct streak/drawdown tracking
    filtered = [r for r in rows if predicate(r)]
    filtered.sort(key=lambda r: r.date or "")
    sr = StackResult(label=label, predicate_desc=pred_desc)
    for row in filtered:
        sr.add(row)
    return sr


# ── Find specific horses ──────────────────────────────────────────────────────

def find_horse(rows: list[Row], name: str) -> list[Row]:
    name_l = name.lower()
    return [r for r in rows if name_l in r.horse.lower()]


def print_horse(rows: list[Row], name: str) -> str:
    hits = find_horse(rows, name)
    if not hits:
        return f"  {name}: NOT FOUND in corpus"
    lines = [f"  {name} — {len(hits)} appearance(s):"]
    for r in hits:
        lines.append(
            f"    {r.date}  VP={r.vp:.3f}  MDS={r.mds:.3f}  IMP={r.imp:.3f}  "
            f"PLACE={r.place_p:.3f}  SP={r.winner_sp or '?'}  "
            f"outcome={r.outcome}  tier={r.tier}"
        )
        flags = []
        if r.vp30: flags.append("VP30")
        if r.mds_high: flags.append("MDS_HIGH")
        if r.imp_high: flags.append("IMP_HIGH")
        if r.place_high: flags.append("PLACE_HIGH")
        lines.append(f"    flags: {' + '.join(flags) or 'none'}")
    return "\n".join(lines)


# ── Top-20 confluence rows ────────────────────────────────────────────────────

def top20_confluence(rows: list[Row]) -> list[Row]:
    scored = []
    for r in rows:
        if not r.vp30:
            continue
        score = r.vp + r.mds + r.imp + r.place_p
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:20]]


# ── Report ────────────────────────────────────────────────────────────────────

def _pct(v: float) -> str: return f"{v*100:.1f}%"
def _roi(v: float) -> str:
    s = "+" if v >= 0 else ""
    return f"{s}{v*100:.1f}%"


def write_md(stacks: list[StackResult], top20: list[Row],
             horse_blocks: dict[str, str], out_path: Path) -> None:
    lines = [
        "# VÉLØ LIVE SIDECAR CONFLUENCE AUDIT",
        "",
        "**Read-only. No scoring, model, router, or staking changes.**",
        "",
        "> Individual sidecar economics are not final until confluence audit is complete.",
        "> The question is: which stacks print truth?",
        "",
        f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "---",
        "",
        "## CONFLUENCE STACK TABLE",
        "",
        "| Stack | n | Win SR | Frame | Avg SP | Win ROI | Break-even SR | SR vs BE | Max DD | Losing Run | Classification |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for s in stacks:
        lines.append(
            f"| {s.label} | {s.n} | {_pct(s.win_sr)} | {_pct(s.frame_rate)} | "
            f"{s.avg_sp:.1f}x | {_roi(s.roi)} | {_pct(s.breakeven_sr)} | "
            f"{_roi(s.sr_vs_breakeven)} | {s.max_drawdown:.1f}u | "
            f"{s.losing_streak} | **{s.classify()}** |"
        )

    # Ranked answers
    elite = [s for s in stacks if s.classify() == "ELITE_CONFLUENCE"]
    strong = [s for s in stacks if s.classify() == "STRONG_CONFLUENCE"]
    frame = [s for s in stacks if s.classify() == "FRAME_ONLY"]
    traps = [s for s in stacks if s.classify() == "OVERBET_TRAP"]
    best_roi = max((s for s in stacks if s.n >= 10), key=lambda x: x.roi)
    best_sr = max((s for s in stacks if s.n >= 10), key=lambda x: x.win_sr)
    best_frame = max((s for s in stacks if s.n >= 10), key=lambda x: x.frame_rate)

    lines += [
        "",
        "---",
        "",
        "## REQUIRED ANSWERS",
        "",
        f"**A. VP30 + MDS_HIGH vs VP30 alone:**",
    ]
    vp30 = next((s for s in stacks if s.predicate_desc == "vp30"), None)
    vp30_mds = next((s for s in stacks if s.predicate_desc == "vp30+mds"), None)
    if vp30 and vp30_mds:
        sr_lift = vp30_mds.win_sr - vp30.win_sr
        roi_lift = vp30_mds.roi - vp30.roi
        lines.append(f"  VP30 alone: SR={_pct(vp30.win_sr)} ROI={_roi(vp30.roi)} n={vp30.n}")
        lines.append(f"  VP30+MDS:   SR={_pct(vp30_mds.win_sr)} ROI={_roi(vp30_mds.roi)} n={vp30_mds.n}")
        verdict = "YES — SR lift" if sr_lift > 0 else "NO"
        lines.append(f"  → {verdict}: Δ SR={_roi(sr_lift)} Δ ROI={_roi(roi_lift)}")

    vp30_mds_imp = next((s for s in stacks if s.predicate_desc == "vp30+mds+imp"), None)
    lines.append(f"\n**B. VP30 + MDS + IMPROVE vs VP30 alone:**")
    if vp30 and vp30_mds_imp:
        sr_lift = vp30_mds_imp.win_sr - vp30.win_sr
        roi_lift = vp30_mds_imp.roi - vp30.roi
        lines.append(f"  VP30+MDS+IMP: SR={_pct(vp30_mds_imp.win_sr)} ROI={_roi(vp30_mds_imp.roi)} n={vp30_mds_imp.n}")
        verdict = "YES" if sr_lift > 0 else "NO"
        lines.append(f"  → {verdict}: Δ SR={_roi(sr_lift)} Δ ROI={_roi(roi_lift)}")

    full_stack = next((s for s in stacks if s.predicate_desc == "vp30+mds+imp+place"), None)
    lines.append(f"\n**D/E. Full stack VP30+MDS+IMP+PLACE — profitable or frame only?**")
    if full_stack:
        lines.append(f"  n={full_stack.n} SR={_pct(full_stack.win_sr)} Frame={_pct(full_stack.frame_rate)} "
                     f"ROI={_roi(full_stack.roi)} → {full_stack.classify()}")
        verdict = "PROFITABLE" if full_stack.roi > 0 else f"FRAME ONLY (ROI {_roi(full_stack.roi)})"
        lines.append(f"  → {verdict}")

    lines += [
        "",
        f"**F. Strongest combo:** {best_roi.label} (ROI={_roi(best_roi.roi)}, SR={_pct(best_roi.win_sr)}, n={best_roi.n})",
        f"**F2. Best frame:** {best_frame.label} (Frame={_pct(best_frame.frame_rate)}, n={best_frame.n})",
        f"**G. Trap combos:** {', '.join(s.label for s in traps) or 'none identified'}",
        "",
        "**H/I/J. Sidecar recommendations:**",
        f"  MDS > 0.50: stay live — {vp30_mds.classify() if vp30_mds else '?'} with VP30",
        f"  improvement > 0.40: stay live — frame engine at {_pct(next((s for s in stacks if s.predicate_desc=='vp30+imp'), StackResult('','',n=0)).frame_rate)}",
        f"  place_prob > 0.80: stay live — frame/place engine",
        "",
        "**K. Operator badges:**",
    ]

    badge_map = {
        "ELITE_CONFLUENCE": "ELITE_STACK",
        "STRONG_CONFLUENCE": "STRONG_STACK",
        "FRAME_ONLY": "WATCH_STACK",
        "OVERBET_TRAP": "SUPPRESS_STACK",
    }
    for s in stacks:
        badge = badge_map.get(s.classify())
        if badge:
            lines.append(f"  {s.label}: **{badge}**")

    lines += [
        "",
        "---",
        "",
        "## HORSE LOOKUPS",
        "",
    ]
    for hname, block in horse_blocks.items():
        lines.append(f"### {hname}")
        lines.append(block)
        lines.append("")

    lines += [
        "---",
        "",
        "## TOP 20 CONFLUENCE ROWS (VP + MDS + IMP + PLACE scored)",
        "",
        "| Date | Horse | VP | MDS | IMP | PLACE | Flags | SP | Outcome |",
        "|---|---|---:|---:|---:|---:|---|---:|---|",
    ]
    for r in top20:
        flags = " ".join(f for f, active in [
            ("VP30", r.vp30), ("MDS_H", r.mds_high),
            ("IMP_H", r.imp_high), ("PL_H", r.place_high)
        ] if active)
        lines.append(
            f"| {r.date} | {r.horse} | {r.vp:.3f} | {r.mds:.3f} | "
            f"{r.imp:.3f} | {r.place_p:.3f} | {flags} | "
            f"{r.winner_sp or '?'} | **{r.outcome}** |"
        )

    lines += [
        "",
        "---",
        "",
        "## LIVE SIDECAR CONFLUENCE TRUTH",
        "",
        "Individual sidecar economics are not final until confluence audit is complete.",
        "",
        "| Signal combo | SR vs breakeven | Verdict |",
        "|---|---|---|",
    ]
    for s in stacks:
        if s.n >= 15:
            lines.append(
                f"| {s.label} | {_roi(s.sr_vs_breakeven)} | {s.classify()} |"
            )

    lines += [
        "",
        "---",
        "",
        "**K. No live code changed. No scoring/model/SQPE/router/staking changes.**",
        "",
        "*LIVE SIDECAR CONFLUENCE AUDIT — operator intelligence only.*",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_json(stacks: list[StackResult], top20: list[Row], out_path: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stacks": [
            {
                "label": s.label,
                "predicate": s.predicate_desc,
                "n": s.n,
                "wins": s.wins,
                "frames": s.frames,
                "win_sr": round(s.win_sr, 4),
                "frame_rate": round(s.frame_rate, 4),
                "roi": round(s.roi, 4),
                "avg_sp": round(s.avg_sp, 2),
                "winner_avg_sp": round(s.winner_avg_sp, 2),
                "loser_avg_sp": round(s.loser_avg_sp, 2),
                "breakeven_sr": round(s.breakeven_sr, 4),
                "sr_vs_breakeven": round(s.sr_vs_breakeven, 4),
                "max_drawdown": round(s.max_drawdown, 2),
                "losing_streak": s.losing_streak,
                "classification": s.classify(),
            }
            for s in stacks
        ],
        "top20": [
            {
                "date": r.date, "horse": r.horse, "vp": round(r.vp, 4),
                "mds": round(r.mds, 4), "imp": round(r.imp, 4),
                "place_p": round(r.place_p, 4), "outcome": r.outcome,
                "winner_sp": r.winner_sp, "tier": r.tier,
                "flags": [f for f, a in [("VP30",r.vp30),("MDS_HIGH",r.mds_high),
                                          ("IMP_HIGH",r.imp_high),("PLACE_HIGH",r.place_high)] if a],
            }
            for r in top20
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("VÉLØ LIVE SIDECAR CONFLUENCE AUDIT")
    print("=" * 50)
    print()
    print("Loading data...")
    rows = load_rows()
    n = len(rows)
    wins = sum(1 for r in rows if r.outcome == "WIN")
    print(f"  Total: {n} | Wins: {wins} | Frames: {sum(1 for r in rows if r.outcome in ('WIN','PLACED'))}")
    print()

    # Stack definitions: (label, pred_desc, predicate)
    stack_defs = [
        # Baselines
        ("All verdicts",           "all",              lambda r: True),
        ("VP30",                   "vp30",             lambda r: r.vp30),
        ("VP ≥ 0.40",              "vp40",             lambda r: r.vp >= 0.40),
        ("MDS_HIGH",               "mds",              lambda r: r.mds_high),
        ("IMPROVE_HIGH",           "imp",              lambda r: r.imp_high),
        ("PLACE_HIGH",             "place",            lambda r: r.place_high),
        # Two-way
        ("VP30 + MDS_HIGH",        "vp30+mds",         lambda r: r.vp30 and r.mds_high),
        ("VP30 + IMPROVE_HIGH",    "vp30+imp",         lambda r: r.vp30 and r.imp_high),
        ("VP30 + PLACE_HIGH",      "vp30+place",       lambda r: r.vp30 and r.place_high),
        ("MDS + IMPROVE",          "mds+imp",          lambda r: r.mds_high and r.imp_high),
        ("MDS + PLACE",            "mds+place",        lambda r: r.mds_high and r.place_high),
        ("IMPROVE + PLACE",        "imp+place",        lambda r: r.imp_high and r.place_high),
        # Three-way
        ("VP30 + MDS + IMPROVE",   "vp30+mds+imp",     lambda r: r.vp30 and r.mds_high and r.imp_high),
        ("VP30 + MDS + PLACE",     "vp30+mds+place",   lambda r: r.vp30 and r.mds_high and r.place_high),
        ("VP30 + IMPROVE + PLACE", "vp30+imp+place",   lambda r: r.vp30 and r.imp_high and r.place_high),
        ("MDS + IMPROVE + PLACE",  "mds+imp+place",    lambda r: r.mds_high and r.imp_high and r.place_high),
        # Four-way — the elite stack
        ("VP30 + MDS + IMP + PLACE","vp30+mds+imp+place",
         lambda r: r.vp30 and r.mds_high and r.imp_high and r.place_high),
        # RPDC combos
        ("VP30 + RPDC_TOP",        "vp30+rpdc",        lambda r: r.vp30 and r.rpdc_top),
        ("VP30 + MDS + RPDC",      "vp30+mds+rpdc",    lambda r: r.vp30 and r.mds_high and r.rpdc_top),
        ("VP30 + MDS + IMP + RPDC","vp30+mds+imp+rpdc",
         lambda r: r.vp30 and r.mds_high and r.imp_high and r.rpdc_top),
        # B-tier suppress check
        ("B-Tier + VP < 0.30",     "b_low_vp",         lambda r: r.tier == "B" and r.vp < 0.30),
        # Tier A combos
        ("Tier A",                 "tier_a",           lambda r: r.tier == "A"),
        ("Tier A + VP30",          "tier_a+vp30",      lambda r: r.tier == "A" and r.vp30),
        ("Tier A + VP30 + MDS",    "tier_a+vp30+mds",  lambda r: r.tier == "A" and r.vp30 and r.mds_high),
    ]

    print("Evaluating stacks...")
    stacks: list[StackResult] = []
    for label, pred_desc, predicate in stack_defs:
        sr = run_stack(rows, label, pred_desc, predicate)
        stacks.append(sr)
        print(f"  {label:<34}  n={sr.n:4d}  SR={_pct(sr.win_sr):6}  "
              f"Frame={_pct(sr.frame_rate):6}  ROI={_roi(sr.roi):7}  "
              f"BE={_pct(sr.breakeven_sr):6}  SRvBE={_roi(sr.sr_vs_breakeven):7}  → {sr.classify()}")

    print()
    print("Horse lookups...")
    horse_names = ["Hickory Lad", "Lady Blanche", "Connie's Rose", "Infraad"]
    horse_blocks = {}
    for hn in horse_names:
        block = print_horse(rows, hn)
        horse_blocks[hn] = block
        print(block)

    print()
    print("Top 20 confluence rows...")
    t20 = top20_confluence(rows)
    print(f"  {len(t20)} rows found")
    for r in t20[:10]:
        flags = [f for f, a in [("VP30",r.vp30),("MDS",r.mds_high),("IMP",r.imp_high),("PL",r.place_high)] if a]
        print(f"  {r.date} {r.horse:<25} VP={r.vp:.3f} MDS={r.mds:.3f} IMP={r.imp:.3f} "
              f"PL={r.place_p:.3f} [{' '.join(flags)}] SP={r.winner_sp or '?'} {r.outcome}")

    md_path  = DATA / "live_sidecar_confluence_audit_latest.md"
    json_path = DATA / "live_sidecar_confluence_audit_latest.json"
    write_md(stacks, t20, horse_blocks, md_path)
    write_json(stacks, t20, json_path)
    print()
    print(f"MD:   {md_path}")
    print(f"JSON: {json_path}")

    # Summary answers
    vp30_s      = next(s for s in stacks if s.predicate_desc == "vp30")
    vp30_mds    = next(s for s in stacks if s.predicate_desc == "vp30+mds")
    vp30_mi     = next(s for s in stacks if s.predicate_desc == "vp30+mds+imp")
    full        = next(s for s in stacks if s.predicate_desc == "vp30+mds+imp+place")
    best_roi    = max((s for s in stacks if s.n >= 10), key=lambda x: x.roi)
    traps       = [s for s in stacks if s.classify() == "OVERBET_TRAP"]

    print()
    print("ANSWERS:")
    print(f"  A. VP30+MDS beats VP30 alone?  SR {_pct(vp30_s.win_sr)}→{_pct(vp30_mds.win_sr)}  "
          f"ROI {_roi(vp30_s.roi)}→{_roi(vp30_mds.roi)}  → {'YES' if vp30_mds.win_sr > vp30_s.win_sr else 'NO'}")
    print(f"  B. VP30+MDS+IMP beats VP30?    SR {_pct(vp30_s.win_sr)}→{_pct(vp30_mi.win_sr)}  "
          f"ROI {_roi(vp30_s.roi)}→{_roi(vp30_mi.roi)}  → {'YES' if vp30_mi.win_sr > vp30_s.win_sr else 'NO'}")
    print(f"  D. Full stack SR={_pct(full.win_sr)} Frame={_pct(full.frame_rate)} "
          f"ROI={_roi(full.roi)} n={full.n} → {full.classify()}")
    print(f"  F. Best ROI: {best_roi.label}  ROI={_roi(best_roi.roi)}  SR={_pct(best_roi.win_sr)}")
    print(f"  G. Traps: {[s.label for s in traps] or 'none'}")
    print()
    print("K. SYSTEM INTEGRITY CONFIRMATION")
    print("   Scoring/SQPE/model/router/staking: unchanged")
    print()
    print("CONFLUENCE AUDIT complete. Operator intelligence only.")


if __name__ == "__main__":
    main()
