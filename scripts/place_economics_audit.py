"""
Place Economics Audit
=====================

Tests approved confluence stacks under place / each-way / frame economics.

The confluence audit showed:
  VP30 + MDS:        SR=54.3%, Frame=100%, ROI=-23.8%  (short prices)
  Tier A + VP30+MDS: SR=64.3%, Frame=100%, ROI=-9.0%
  VP30 + IMPROVE:    SR=50.0%, Frame=87.0%, ROI=-9.8%

The key question: at what place odds does Frame=100% become profitable?

This script answers it by simulating place / each-way returns at known
and estimated odds across all approved confluence stacks.

Usage:
    python scripts/place_economics_audit.py

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

# ── Thresholds (locked from confluence audit) ─────────────────────────────────

VP30_T        = 0.30
MDS_HIGH_T    = 0.50
IMPROVE_HIGH_T= 0.40
PLACE_HIGH_T  = 0.80

# ── Simulated place odds to test ──────────────────────────────────────────────
# Net odds (e.g. 1.20 = £1 returned + £0.20 profit per £1 staked on place leg)
PLACE_ODDS_TO_TEST = [1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.40, 1.50, 1.75, 2.00]

# Each-way terms (fractional reduction of win odds for place portion)
EW_TERMS = [("1/4", 0.25), ("1/5", 0.20), ("1/6", 0.167)]

# SP bands
SP_BANDS = [
    ("odds_on",  0.0,  2.0),
    ("2.0–3.0",  2.0,  3.0),
    ("3.0–4.0",  3.0,  4.0),
    ("4.0–6.0",  4.0,  6.0),
    ("6.0–10.0", 6.0, 10.0),
    ("10.0+",   10.0, 999.0),
]

FIELD_BANDS = [
    ("≤6",   0,  7),
    ("7–9",  7, 10),
    ("10–12",10, 13),
    ("13+",  13,999),
]


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Row:
    race_id: str
    date: str
    tier: str
    outcome: str          # WIN / PLACED / MISS
    winner_sp: Optional[float]   # SP of the actual race winner
    our_sp: Optional[float]      # estimated SP of our pick
    field_size: Optional[int]
    vp: float
    imp: float
    mds: float
    place_p: float

    @property
    def vp30(self)  -> bool: return self.vp >= VP30_T
    @property
    def mds_high(self) -> bool: return self.mds > MDS_HIGH_T
    @property
    def imp_high(self) -> bool: return self.imp > IMPROVE_HIGH_T
    @property
    def place_high(self)-> bool: return self.place_p > PLACE_HIGH_T
    @property
    def is_win(self)    -> bool: return self.outcome == "WIN"
    @property
    def is_frame(self)  -> bool: return self.outcome in ("WIN", "PLACED")

    def sp_band(self) -> str:
        sp = self.our_sp or self.winner_sp
        if sp is None:
            return "unknown"
        for label, lo, hi in SP_BANDS:
            if lo <= sp < hi:
                return label
        return "10.0+"

    def field_band(self) -> str:
        if self.field_size is None:
            return "unknown"
        for label, lo, hi in FIELD_BANDS:
            if lo <= self.field_size < hi:
                return label
        return "13+"


@dataclass
class StackEcon:
    label: str
    badge: str            # ELITE_STACK / STRONG_STACK etc.
    predicate_desc: str
    n: int = 0
    wins: int = 0
    frames: int = 0
    pnl_win_flat: float = 0.0
    sp_sum: float = 0.0
    sp_count: int = 0
    win_sp_sum: float = 0.0
    win_sp_count: int = 0
    placed_sp_sum: float = 0.0
    placed_sp_count: int = 0
    loss_sp_sum: float = 0.0
    loss_sp_count: int = 0
    # Per-place-odds P&L (keyed by odds string e.g. "1.20")
    place_pnl: dict = field(default_factory=dict)
    # Per EW-terms P&L
    ew_pnl: dict = field(default_factory=dict)
    # SP band breakdown
    sp_bands: dict = field(default_factory=dict)
    # Field size breakdown
    field_bands: dict = field(default_factory=dict)
    # Streak tracking
    _cur_streak: int = field(default=0, repr=False)
    losing_streak: int = 0
    max_drawdown_win: float = 0.0
    _peak_win: float = field(default=0.0, repr=False)
    _equity_win: float = field(default=0.0, repr=False)

    @property
    def win_sr(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def frame_rate(self) -> float:
        return self.frames / self.n if self.n else 0.0

    @property
    def roi_win_flat(self) -> float:
        return self.pnl_win_flat / self.n if self.n else 0.0

    @property
    def avg_sp(self) -> float:
        return self.sp_sum / self.sp_count if self.sp_count else 0.0

    @property
    def avg_win_sp(self) -> float:
        return self.win_sp_sum / self.win_sp_count if self.win_sp_count else 0.0

    @property
    def avg_placed_sp(self) -> float:
        return self.placed_sp_sum / self.placed_sp_count if self.placed_sp_count else 0.0

    @property
    def avg_loss_sp(self) -> float:
        return self.loss_sp_sum / self.loss_sp_count if self.loss_sp_count else 0.0

    def breakeven_place_odds(self) -> float:
        """Minimum place odds for breakeven given current frame rate."""
        if self.frame_rate <= 0:
            return 99.0
        return 1.0 / self.frame_rate

    def roi_at_place_odds(self, odds: float) -> float:
        """ROI if we got `odds` (decimal net) on every frame hit."""
        key = f"{odds:.2f}"
        pl = self.place_pnl.get(key, 0.0)
        return pl / self.n if self.n else 0.0

    def best_place_odds_for_profit(self) -> Optional[float]:
        """Lowest place odds at which ROI turns positive."""
        for odds in PLACE_ODDS_TO_TEST:
            if self.roi_at_place_odds(odds) > 0:
                return odds
        return None

    def classify(self) -> str:
        if self.n < 10:
            return "LOW_SAMPLE"
        if self.roi_win_flat > 0.05:
            return "WIN_VALUE"
        best = self.best_place_odds_for_profit()
        if best and best <= 1.20:
            return "PLACE_VALUE"
        if best and best <= 1.50:
            return "PLACE_VALUE_MODERATE"
        if self.frame_rate >= 0.65:
            return "FRAME_ONLY"
        if self.roi_win_flat < -0.20 and self.frame_rate < 0.55:
            return "SUPPRESS"
        return "WATCH"


# ── Load data ─────────────────────────────────────────────────────────────────

def _estimate_our_sp(row_outcome: str, winner_sp: Optional[float]) -> Optional[float]:
    """
    Estimate our pick's SP.
    - WIN: winner_sp IS our horse's SP.
    - PLACED: estimate as ~1.8x winner SP (favourites often win, placed horses run longer).
    - MISS: no useful estimate; use winner SP as the race 'average' proxy for band classification.
    """
    if winner_sp is None:
        return None
    if row_outcome == "WIN":
        return winner_sp
    if row_outcome == "PLACED":
        return round(winner_sp * 1.8, 2)   # rough proxy — placed horse tends to be longer
    return winner_sp  # MISS: use winner as proxy for SP band context only


def load_rows() -> list[Row]:
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    print("  sigma_audits...", end="", flush=True)
    sigma: list[dict] = []
    pg = 0
    while True:
        r = sb.table("sigma_audits").select(
            "race_id,date,outcome,actual_winner_sp,decision_tier"
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
            "place_prob,decision_tier,predicted_field_size"
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
        outcome = sv.get("outcome", "MISS")
        sp_raw = sv.get("actual_winner_sp")
        winner_sp = float(sp_raw) if sp_raw else None
        our_sp = _estimate_our_sp(outcome, winner_sp)
        rows.append(Row(
            race_id=sv["race_id"],
            date=sv.get("date", "") or "",
            tier=sv.get("decision_tier") or v.get("decision_tier") or "?",
            outcome=outcome,
            winner_sp=winner_sp,
            our_sp=our_sp,
            field_size=v.get("predicted_field_size"),
            vp=float(v.get("velo_prime_prob") or 0),
            imp=float(v.get("improvement_score") or 0),
            mds=float(v.get("market_deception_score") or 0),
            place_p=float(v.get("place_prob") or 0),
        ))
    return rows


# ── Evaluate stack ────────────────────────────────────────────────────────────

def _ew_place_return(our_sp: Optional[float], terms_fraction: float, outcome: str) -> float:
    """
    Each-way place return (place leg only, £1 staked).
    Returns net profit/loss on place leg.
    Assumes 'places' = WIN or PLACED (top-3 proxy).
    """
    if our_sp is None:
        return -1.0
    place_net_odds = (our_sp - 1.0) * terms_fraction  # e.g. (4-1)*0.25 = 0.75
    if outcome in ("WIN", "PLACED"):
        return place_net_odds   # profit on place leg
    return -1.0                 # lose place stake


def eval_stack(rows: list[Row], label: str, badge: str,
               pred_desc: str, predicate: Callable[[Row], bool]) -> StackEcon:
    se = StackEcon(label=label, badge=badge, predicate_desc=pred_desc)
    # Initialise place P&L accumulators
    for odds in PLACE_ODDS_TO_TEST:
        se.place_pnl[f"{odds:.2f}"] = 0.0
    for term_label, _ in EW_TERMS:
        se.ew_pnl[term_label] = 0.0

    filtered = sorted((r for r in rows if predicate(r)), key=lambda r: r.date)

    for row in filtered:
        se.n += 1
        sp = row.our_sp  # use estimated SP for our pick
        wsp = row.winner_sp  # winner's SP for win-flat ROI

        # Win-flat ROI
        if row.is_win:
            se.wins += 1
            se.pnl_win_flat += (wsp - 1.0) if wsp else 0.0
            se._cur_streak = 0
            if sp:
                se.win_sp_sum += sp
                se.win_sp_count += 1
        else:
            se.pnl_win_flat -= 1.0
            se._cur_streak += 1
            se.losing_streak = max(se.losing_streak, se._cur_streak)
            if row.is_frame and sp:
                se.placed_sp_sum += sp
                se.placed_sp_count += 1
            elif sp:
                se.loss_sp_sum += sp
                se.loss_sp_count += 1

        # Win equity for drawdown
        gain = (wsp - 1.0) if (row.is_win and wsp) else -1.0
        se._equity_win += gain
        if se._equity_win > se._peak_win:
            se._peak_win = se._equity_win
        dd = se._peak_win - se._equity_win
        se.max_drawdown_win = max(se.max_drawdown_win, dd)

        if row.is_frame:
            se.frames += 1
        if sp:
            se.sp_sum += sp
            se.sp_count += 1

        # Place ROI at simulated fixed odds
        for odds in PLACE_ODDS_TO_TEST:
            key = f"{odds:.2f}"
            if row.is_frame:
                se.place_pnl[key] += (odds - 1.0)   # net profit
            else:
                se.place_pnl[key] -= 1.0             # lose stake

        # Each-way place return (place leg only)
        for term_label, term_frac in EW_TERMS:
            se.ew_pnl[term_label] += _ew_place_return(sp, term_frac, row.outcome)

        # SP band breakdown
        band = row.sp_band()
        if band not in se.sp_bands:
            se.sp_bands[band] = {"n": 0, "wins": 0, "frames": 0, "sp_sum": 0.0}
        se.sp_bands[band]["n"] += 1
        if row.is_win:  se.sp_bands[band]["wins"] += 1
        if row.is_frame: se.sp_bands[band]["frames"] += 1
        if sp: se.sp_bands[band]["sp_sum"] += sp

        # Field size breakdown
        fb = row.field_band()
        if fb not in se.field_bands:
            se.field_bands[fb] = {"n": 0, "wins": 0, "frames": 0}
        se.field_bands[fb]["n"] += 1
        if row.is_win:   se.field_bands[fb]["wins"] += 1
        if row.is_frame: se.field_bands[fb]["frames"] += 1

    # Normalise EW P&L to per-stake (place leg only, £1)
    if se.n:
        for k in se.ew_pnl:
            se.ew_pnl[k] = se.ew_pnl[k] / se.n

    return se


# ── Report helpers ────────────────────────────────────────────────────────────

def _pct(v: float) -> str: return f"{v*100:.1f}%"
def _roi(v: float) -> str:
    s = "+" if v >= 0 else ""
    return f"{s}{v*100:.1f}%"
def _odds(v: float) -> str: return f"{v:.2f}"


# ── Report ────────────────────────────────────────────────────────────────────

def write_md(stacks: list[StackEcon], out_path: Path) -> None:
    lines = [
        "# VÉLØ PLACE ECONOMICS AUDIT",
        "",
        "**Read-only. No scoring, model, router, or staking changes.**",
        "",
        "> Confluence stacks show 100% frame rates but short prices mean flat-win ROI is negative.",
        "> This audit answers: at what place odds do these stacks become profitable?",
        "",
        f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "---",
        "",
        "## PLACE ECONOMICS TABLE — Core stacks",
        "",
        "| Stack | Badge | n | Win SR | Frame | Win ROI | Avg SP | Breakeven Place | Best Place Odds (profit) | Classification |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for se in stacks:
        be = se.breakeven_place_odds()
        best = se.best_place_odds_for_profit()
        lines.append(
            f"| {se.label} | {se.badge} | {se.n} | {_pct(se.win_sr)} | "
            f"{_pct(se.frame_rate)} | {_roi(se.roi_win_flat)} | "
            f"{se.avg_sp:.1f}x | {_odds(be)} | "
            f"{'≥'+_odds(best) if best else 'never in test range'} | **{se.classify()}** |"
        )

    lines += [
        "",
        "---",
        "",
        "## SIMULATED PLACE ROI — At fixed odds (flat £1 place bet per horse)",
        "",
        "Positive = profitable at that place price.",
        "",
        "| Stack | n | Frame | " + " | ".join(f"{o:.2f}" for o in PLACE_ODDS_TO_TEST) + " |",
        "|---|---:|---:|" + "---:|" * len(PLACE_ODDS_TO_TEST),
    ]
    for se in stacks:
        rois = " | ".join(_roi(se.roi_at_place_odds(o)) for o in PLACE_ODDS_TO_TEST)
        lines.append(f"| {se.label} | {se.n} | {_pct(se.frame_rate)} | {rois} |")

    lines += [
        "",
        "---",
        "",
        "## EACH-WAY SIMULATION (place leg only, £1)",
        "",
        "Uses estimated SP for our pick. WIN/PLACED = placed. Bookmaker terms simulated.",
        "Note: PLACED outcome SP estimated as ~1.8x winner SP (proxy — actual pick SP unavailable).",
        "",
        "| Stack | n | Frame | Avg SP | " + " | ".join(f"E/W {t}" for t, _ in EW_TERMS) + " |",
        "|---|---:|---:|---:|" + "---:|" * len(EW_TERMS),
    ]
    for se in stacks:
        ew = " | ".join(_roi(se.ew_pnl.get(t, 0.0)) for t, _ in EW_TERMS)
        lines.append(f"| {se.label} | {se.n} | {_pct(se.frame_rate)} | {se.avg_sp:.1f}x | {ew} |")

    lines += [
        "",
        "---",
        "",
        "## SP BAND BREAKDOWN — VP30 + MDS (STRONG_STACK) and Tier A + VP30 + MDS (ELITE_STACK)",
        "",
    ]
    for se in [s for s in stacks if "MDS" in s.label]:
        lines.append(f"### {se.label}")
        lines.append("")
        lines.append("| SP band | n | Win SR | Frame |")
        lines.append("|---|---:|---:|---:|")
        for band, bd in sorted(se.sp_bands.items()):
            bn = bd["n"]
            if bn:
                lines.append(f"| {band} | {bn} | {_pct(bd['wins']/bn)} | {_pct(bd['frames']/bn)} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## FIELD SIZE BREAKDOWN — VP30 alone vs VP30 + MDS",
        "",
    ]
    vp30_s  = next((s for s in stacks if s.predicate_desc == "vp30"), None)
    vp30mds = next((s for s in stacks if s.predicate_desc == "vp30+mds"), None)
    for se in [s for s in [vp30_s, vp30mds] if s]:
        lines.append(f"### {se.label}")
        lines.append("")
        lines.append("| Field size | n | Win SR | Frame |")
        lines.append("|---|---:|---:|---:|")
        for fb, fd in sorted(se.field_bands.items()):
            fn = fd["n"]
            if fn:
                lines.append(f"| {fb} | {fn} | {_pct(fd['wins']/fn)} | {_pct(fd['frames']/fn)} |")
        lines.append("")

    # Required answers
    vp30    = next((s for s in stacks if s.predicate_desc == "vp30"), None)
    elite   = next((s for s in stacks if "tier_a" in s.predicate_desc), None)
    vp_mds  = next((s for s in stacks if s.predicate_desc == "vp30+mds"), None)
    vp_imp  = next((s for s in stacks if s.predicate_desc == "vp30+imp"), None)
    suppress= next((s for s in stacks if s.predicate_desc == "b_low_vp"), None)

    lines += [
        "---",
        "",
        "## REQUIRED ANSWERS",
        "",
    ]
    if elite:
        best = elite.best_place_odds_for_profit()
        ew14 = _roi(elite.ew_pnl.get("1/4", 0))
        ew15 = _roi(elite.ew_pnl.get("1/5", 0))
        lines.append(f"**1. Does Tier A + VP30 + MDS become profitable as place framework?**")
        lines.append(f"  n={elite.n}, Frame={_pct(elite.frame_rate)}, Win ROI={_roi(elite.roi_win_flat)}")
        lines.append(f"  Breakeven place odds needed: {_odds(elite.breakeven_place_odds())}")
        lines.append(f"  Profitable at: {'≥'+_odds(best) if best else 'not in test range'}")
        lines.append(f"  E/W 1/4 place leg ROI: {ew14}  |  E/W 1/5 place leg ROI: {ew15}")
        lines.append(f"  → {'YES at low odds — PLACE_VALUE' if best and best <= 1.20 else 'NEEDS ODDS ≥'+_odds(best) if best else 'HIGH PRICE NEEDED'}")
        lines.append("")

    if vp_mds and vp_imp:
        lines.append("**4. VP30 + MDS vs VP30 + IMPROVE — which is better value?**")
        lines.append(f"  VP30+MDS:    Frame={_pct(vp_mds.frame_rate)}, PlaceROI@1.20={_roi(vp_mds.roi_at_place_odds(1.20))}, AvgSP={vp_mds.avg_sp:.1f}")
        lines.append(f"  VP30+IMPROVE:Frame={_pct(vp_imp.frame_rate)}, PlaceROI@1.20={_roi(vp_imp.roi_at_place_odds(1.20))}, AvgSP={vp_imp.avg_sp:.1f}")
        mds_best = vp_mds.best_place_odds_for_profit()
        imp_best = vp_imp.best_place_odds_for_profit()
        if mds_best and imp_best:
            better = "VP30+MDS (lower odds needed)" if mds_best <= imp_best else "VP30+IMPROVE (lower odds needed)"
            lines.append(f"  → {better}")
        lines.append("")

    if suppress:
        lines.append("**7. Suppress stack confirmation:**")
        lines.append(f"  B-tier + VP<0.30: n={suppress.n}, SR={_pct(suppress.win_sr)}, Frame={_pct(suppress.frame_rate)}, WinROI={_roi(suppress.roi_win_flat)}")
        lines.append(f"  → {suppress.classify()} — confirmed, do not upgrade with sidecars")
        lines.append("")

    lines += [
        "---",
        "",
        "## FINAL OPERATOR BADGE RECOMMENDATIONS",
        "",
        "| Stack | Badge | Place Economics | Recommendation |",
        "|---|---|---|---|",
    ]
    for se in stacks:
        best = se.best_place_odds_for_profit()
        best_str = f"Profitable at ≥{_odds(best)}" if best else "Not profitable in test range"
        lines.append(f"| {se.label} | **{se.badge}** | {best_str} | {se.classify()} |")

    lines += [
        "",
        "---",
        "",
        "**J. No live code changed. No scoring/SQPE/model/router/staking changes.**",
        "",
        "*PLACE ECONOMICS AUDIT — operator intelligence only.*",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_json(stacks: list[StackEcon], out_path: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stacks": [
            {
                "label": se.label,
                "badge": se.badge,
                "predicate": se.predicate_desc,
                "n": se.n,
                "wins": se.wins,
                "frames": se.frames,
                "win_sr": round(se.win_sr, 4),
                "frame_rate": round(se.frame_rate, 4),
                "roi_win_flat": round(se.roi_win_flat, 4),
                "avg_sp": round(se.avg_sp, 2),
                "avg_win_sp": round(se.avg_win_sp, 2),
                "avg_placed_sp": round(se.avg_placed_sp, 2),
                "avg_loss_sp": round(se.avg_loss_sp, 2),
                "breakeven_place_odds": round(se.breakeven_place_odds(), 3),
                "best_place_odds_for_profit": se.best_place_odds_for_profit(),
                "place_roi_by_odds": {k: round(v / se.n, 4) if se.n else 0 for k, v in se.place_pnl.items()},
                "ew_place_roi": {k: round(v, 4) for k, v in se.ew_pnl.items()},
                "classification": se.classify(),
                "max_drawdown_win": round(se.max_drawdown_win, 2),
                "longest_losing_run": se.losing_streak,
                "sp_bands": se.sp_bands,
                "field_bands": se.field_bands,
            }
            for se in stacks
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

STACK_DEFS = [
    # label, badge, pred_desc, predicate
    ("Tier A + VP30 + MDS",       "ELITE_STACK",        "tier_a+vp30+mds",
     lambda r: r.tier == "A" and r.vp30 and r.mds_high),
    ("VP30 + MDS",                "STRONG_STACK",       "vp30+mds",
     lambda r: r.vp30 and r.mds_high),
    ("VP30 + MDS + IMPROVE",      "STRONG_STACK_PLUS",  "vp30+mds+imp",
     lambda r: r.vp30 and r.mds_high and r.imp_high),
    ("VP30 + MDS + IMP + PLACE",  "STRONG_STACK_PLUS",  "vp30+mds+imp+place",
     lambda r: r.vp30 and r.mds_high and r.imp_high and r.place_high),
    ("VP30 + IMPROVE",            "STRONG_STACK",       "vp30+imp",
     lambda r: r.vp30 and r.imp_high),
    ("VP30 + PLACE only",         "WATCH_STACK",        "vp30+place",
     lambda r: r.vp30 and r.place_high),
    ("VP30 alone",                "BASE_TRUST_SIGNAL",  "vp30",
     lambda r: r.vp30),
    ("B-tier + VP < 0.30",        "SUPPRESS_STACK",     "b_low_vp",
     lambda r: r.tier == "B" and not r.vp30),
    ("All verdicts (baseline)",   "BASELINE",           "all",
     lambda r: True),
]


def main() -> None:
    print("VÉLØ PLACE ECONOMICS AUDIT")
    print("=" * 50)
    print()
    print("Loading data...")
    rows = load_rows()
    print(f"  Rows: {len(rows)} | Wins: {sum(1 for r in rows if r.is_win)} | "
          f"Frames: {sum(1 for r in rows if r.is_frame)}")
    print()

    print("Evaluating place economics...")
    stacks: list[StackEcon] = []
    for label, badge, pred_desc, predicate in STACK_DEFS:
        se = eval_stack(rows, label, badge, pred_desc, predicate)
        stacks.append(se)
        be = se.breakeven_place_odds()
        best = se.best_place_odds_for_profit()
        best_str = f"≥{_odds(best)}" if best else "none"
        print(f"  {label:<34}  n={se.n:4d}  SR={_pct(se.win_sr):6}  "
              f"Frame={_pct(se.frame_rate):6}  WinROI={_roi(se.roi_win_flat):8}  "
              f"AvgSP={se.avg_sp:4.1f}  BEplace={_odds(be)}  ProfitAt={best_str}  → {se.classify()}")

    print()
    # Detailed place ROI for elite stacks
    print("PLACE ROI BY ODDS — Elite stacks:")
    for se in stacks[:4]:
        roi_row = "  ".join(f"{o:.2f}→{_roi(se.roi_at_place_odds(o))}" for o in [1.05,1.10,1.15,1.20,1.25,1.30,1.50])
        print(f"  {se.label}: {roi_row}")

    print()
    print("EACH-WAY PLACE LEG ROI (place leg only, £1):")
    for se in stacks[:7]:
        ew = "  ".join(f"{t}→{_roi(se.ew_pnl.get(t,0))}" for t, _ in EW_TERMS)
        print(f"  {se.label:<34}  {ew}")

    md_path   = DATA / "place_economics_audit_latest.md"
    json_path = DATA / "place_economics_audit_latest.json"
    print()
    write_md(stacks, md_path)
    write_json(stacks, json_path)
    print(f"MD:   {md_path}")
    print(f"JSON: {json_path}")

    print()
    print("FINAL ANSWERS:")
    elite = next(s for s in stacks if "tier_a" in s.predicate_desc)
    vp_mds = next(s for s in stacks if s.predicate_desc == "vp30+mds")
    vp_imp = next(s for s in stacks if s.predicate_desc == "vp30+imp")
    vp30   = next(s for s in stacks if s.predicate_desc == "vp30")
    supp   = next(s for s in stacks if s.predicate_desc == "b_low_vp")
    best_elite = elite.best_place_odds_for_profit()
    best_vpmds = vp_mds.best_place_odds_for_profit()

    print(f"  1. Tier A+VP30+MDS profitable as place? → odds needed: "
          f"{'≥'+_odds(best_elite) if best_elite else 'none in range'}"
          f"  E/W 1/4: {_roi(elite.ew_pnl.get('1/4',0))}")
    print(f"  2. Min place odds needed (ELITE): {_odds(elite.breakeven_place_odds())}")
    print(f"  3. VP30+MDS: place min odds = {_odds(vp_mds.breakeven_place_odds())}  "
          f"E/W 1/4: {_roi(vp_mds.ew_pnl.get('1/4',0))}")
    print(f"  4. VP30+IMP vs VP30+MDS: IMP frame={_pct(vp_imp.frame_rate)} "
          f"MDS frame={_pct(vp_mds.frame_rate)}  "
          f"→ {'MDS better frame' if vp_mds.frame_rate > vp_imp.frame_rate else 'IMP better frame'}")
    print(f"  6. Best operator priority: "
          f"{'Tier A+VP30+MDS' if elite.frame_rate >= vp_mds.frame_rate else 'VP30+MDS'}")
    print(f"  7. Suppress confirmed: B-tier+low VP  SR={_pct(supp.win_sr)}  "
          f"Frame={_pct(supp.frame_rate)}  ROI={_roi(supp.roi_win_flat)}")
    print()
    print("K. SYSTEM INTEGRITY CONFIRMATION")
    print("   Scoring/SQPE/model/router/staking/live execution: unchanged")
    print()
    print("PLACE ECONOMICS AUDIT complete. Operator intelligence only.")


if __name__ == "__main__":
    main()
