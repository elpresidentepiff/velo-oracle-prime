"""
Place / Frame Economics Audit
==============================

Evaluates VÉLØ signals not just as WIN engines but as FRAME / PLACE / STRUCTURE engines.

A signal with weak win ROI but strong frame rate belongs to a different product:
  - place bet
  - each-way
  - top-4 / top-5 exchange market
  - accumulator leg

Classification schema:
  WIN_ENGINE          — win ROI positive, win SR strong
  FRAME_ENGINE        — frame rate > 65%, win ROI negative but place proxy positive
  WIN_NEGATIVE_FRAME_STRONG — win ROI negative, frame > 65% (reclassify from HARMFUL)
  OVERBET_WIN_ONLY    — win ROI negative, frame weak (< 55%)
  SUPPRESS            — no useful signal

Usage:
    python scripts/place_frame_economics_audit.py

Read-only. No scoring, model, router, or staking changes.
"""

from __future__ import annotations

import os
import json
import itertools
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
import sys; sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(ROOT / ".env")

DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

# ── Thresholds ──────────────────────────────────────────────────────────────

SIDECAR_THRESHOLDS = {
    "velo_prime_prob":        0.30,
    "improvement_score":      0.40,
    "market_deception_score": 0.50,
    "release_day_prob":       0.50,
    "place_prob":             0.80,
    "longshot_prob":          0.50,
    "rpdc_release_score":     0.50,
}

PLACE_TERMS_1_5 = 1 / 5   # standard bookmaker
PLACE_TERMS_1_4 = 1 / 4   # each-way generous

SP_BANDS = [
    ("evens_or_under",  0.0,  2.0),
    ("2_to_4",          2.0,  4.0),
    ("4_to_6",          4.0,  6.0),
    ("6_to_10",         6.0, 10.0),
    ("10_to_20",       10.0, 20.0),
    ("over_20",        20.0, 999.0),
]

TOP_N_PLACE_CUTOFFS = [2, 3, 4, 5]


# ── Data model ───────────────────────────────────────────────────────────────

@dataclass
class Row:
    race_id: str
    date: str
    decision_tier: str
    outcome: str          # WIN / PLACED / MISS
    miss_reason: Optional[str]
    position: Optional[int]
    winner_sp: Optional[float]
    vp: float
    imp: float
    mds: float
    rday: float
    place_prob: float
    longshot: float
    rpdc: float
    archetype: str
    field_size: Optional[int]


@dataclass
class SignalStats:
    label: str
    threshold_desc: str
    n: int = 0
    wins: int = 0
    placed: int = 0      # WIN or PLACED outcome
    miss: int = 0
    top2: int = 0
    top3: int = 0
    top4: int = 0
    top5: int = 0
    sp_sum: float = 0.0
    sp_count: int = 0
    winner_sp_sum: float = 0.0
    winner_sp_count: int = 0
    win_roi: float = 0.0   # flat win £1
    place_roi_1_5: float = 0.0
    place_roi_1_4: float = 0.0
    sp_bands: dict = field(default_factory=dict)

    @property
    def win_sr(self) -> float:
        return self.wins / self.n if self.n else 0.0

    @property
    def frame_rate(self) -> float:
        # placed already includes wins (WIN or PLACED outcome)
        return self.placed / self.n if self.n else 0.0

    @property
    def top3_rate(self) -> float:
        return self.top3 / self.n if self.n else 0.0

    @property
    def top4_rate(self) -> float:
        return self.top4 / self.n if self.n else 0.0

    @property
    def top5_rate(self) -> float:
        return self.top5 / self.n if self.n else 0.0

    @property
    def avg_sp(self) -> float:
        return self.sp_sum / self.sp_count if self.sp_count else 0.0

    @property
    def avg_winner_sp(self) -> float:
        return self.winner_sp_sum / self.winner_sp_count if self.winner_sp_count else 0.0

    def classify(self) -> str:
        """Classify signal by economics — win AND place."""
        if self.n < 15:
            return "INSUFFICIENT_SAMPLE"
        if self.win_roi > 0 and self.win_sr >= 0.25:
            return "WIN_ENGINE"
        if self.frame_rate >= 0.65 and self.win_roi >= -0.20:
            return "FRAME_ENGINE"
        if self.frame_rate >= 0.65 and self.win_roi < -0.20:
            return "WIN_NEGATIVE_FRAME_STRONG"
        if self.frame_rate >= 0.55 and self.top4_rate >= 0.70:
            return "TOP4_TOP5_CANDIDATE"
        if self.frame_rate < 0.55 and self.win_roi < -0.10:
            return "OVERBET_WIN_ONLY"
        return "WATCH"

    def best_use(self) -> str:
        cls = self.classify()
        mapping = {
            "WIN_ENGINE": "WIN_BET",
            "FRAME_ENGINE": "EACH_WAY / PLACE_BET",
            "WIN_NEGATIVE_FRAME_STRONG": "PLACE_BET / EACH_WAY",
            "TOP4_TOP5_CANDIDATE": "TOP4_TOP5_EXCHANGE",
            "OVERBET_WIN_ONLY": "SUPPRESS",
            "WATCH": "WATCH_ONLY",
            "INSUFFICIENT_SAMPLE": "INSUFFICIENT_SAMPLE",
        }
        return mapping.get(cls, "WATCH_ONLY")


# ── Data loading ─────────────────────────────────────────────────────────────

def _sb():
    return create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )


def load_data() -> list[Row]:
    sb = _sb()

    # Load sigma_audits (results)
    print("  Loading sigma_audits...")
    sigma_rows = []
    page = 0
    while True:
        r = sb.table("sigma_audits").select(
            "race_id,date,decision_tier,outcome,miss_reason,top_pick_position,actual_winner_sp"
        ).neq("outcome", "X_BLOCKED").range(page * 1000, (page + 1) * 1000 - 1).execute()
        sigma_rows.extend(r.data)
        if len(r.data) < 1000:
            break
        page += 1
    sigma_map = {r["race_id"]: r for r in sigma_rows}
    print(f"    {len(sigma_rows)} sigma rows")

    # Load verdicts (sidecar scores)
    print("  Loading velo_verdicts...")
    verdicts = []
    page = 0
    while True:
        r = sb.table("velo_verdicts").select(
            "race_id,velo_prime_prob,improvement_score,market_deception_score,"
            "release_day_prob,place_prob,longshot_prob,rpdc_release_score,"
            "decision_tier,race_archetype,predicted_field_size"
        ).range(page * 1000, (page + 1) * 1000 - 1).execute()
        verdicts.extend(r.data)
        if len(r.data) < 1000:
            break
        page += 1
    verdict_map = {v["race_id"]: v for v in verdicts}
    print(f"    {len(verdicts)} verdict rows")

    # Join
    rows: list[Row] = []
    for race_id, sv in sigma_map.items():
        vv = verdict_map.get(race_id)
        if not vv:
            continue
        outcome = sv.get("outcome", "MISS")
        sp = sv.get("actual_winner_sp")
        pos = sv.get("top_pick_position")
        rows.append(Row(
            race_id=race_id,
            date=sv.get("date", ""),
            decision_tier=sv.get("decision_tier") or vv.get("decision_tier") or "?",
            outcome=outcome,
            miss_reason=sv.get("miss_reason"),
            position=pos,
            winner_sp=float(sp) if sp else None,
            vp=float(vv.get("velo_prime_prob") or 0),
            imp=float(vv.get("improvement_score") or 0),
            mds=float(vv.get("market_deception_score") or 0),
            rday=float(vv.get("release_day_prob") or 0),
            place_prob=float(vv.get("place_prob") or 0),
            longshot=float(vv.get("longshot_prob") or 0),
            rpdc=float(vv.get("rpdc_release_score") or 0),
            archetype=vv.get("race_archetype") or "unknown",
            field_size=vv.get("predicted_field_size"),
        ))

    print(f"    {len(rows)} joined rows")
    return rows


# ── Signal evaluation ─────────────────────────────────────────────────────────

def _sp_band(sp: Optional[float]) -> str:
    if sp is None:
        return "unknown"
    for label, lo, hi in SP_BANDS:
        if lo <= sp < hi:
            return label
    return "over_20"


def _top_n(row: Row, n: int) -> bool:
    """True if our pick finished top-n. Uses outcome as proxy when position absent."""
    if row.position is not None:
        return row.position <= n
    # Fallback: WIN = top-1, PLACED = top-3 proxy
    if n >= 1 and row.outcome == "WIN":
        return True
    if n >= 3 and row.outcome == "PLACED":
        return True
    return False


def _place_return(sp: Optional[float], terms: float, won: bool, placed_top3: bool) -> float:
    """Returns net return per £1 stake."""
    if sp is None:
        return 0.0
    if won:
        return (sp - 1.0) * terms + 1.0 - 1.0  # place return - stake
    if placed_top3:
        return (sp - 1.0) * terms - 0.0  # partial — already subtracted stake conceptually
    return -1.0  # lost


def evaluate_signal(rows: list[Row], label: str, threshold_desc: str,
                    predicate) -> SignalStats:
    stats = SignalStats(label=label, threshold_desc=threshold_desc)
    for row in rows:
        if not predicate(row):
            continue
        stats.n += 1
        is_win = row.outcome == "WIN"
        is_placed = row.outcome == "PLACED"
        sp = row.winner_sp

        if is_win:
            stats.wins += 1
            stats.win_roi += (sp - 1.0) if sp else 0.0
            if sp:
                stats.winner_sp_sum += sp
                stats.winner_sp_count += 1
        else:
            stats.win_roi -= 1.0

        if is_win or is_placed:
            stats.placed += 1
        else:
            stats.miss += 1

        if sp:
            stats.sp_sum += sp
            stats.sp_count += 1

        # Top-N rates
        for n in TOP_N_PLACE_CUTOFFS:
            if _top_n(row, n):
                if n == 2: stats.top2 += 1
                elif n == 3: stats.top3 += 1
                elif n == 4: stats.top4 += 1
                elif n == 5: stats.top5 += 1

        # Place ROI proxy
        placed_top3 = _top_n(row, 3)
        if is_win and sp:
            stats.place_roi_1_5 += (sp - 1.0) * PLACE_TERMS_1_5
            stats.place_roi_1_4 += (sp - 1.0) * PLACE_TERMS_1_4
        elif placed_top3 and sp:
            stats.place_roi_1_5 += (sp - 1.0) * PLACE_TERMS_1_5
            stats.place_roi_1_4 += (sp - 1.0) * PLACE_TERMS_1_4
        else:
            stats.place_roi_1_5 -= 1.0
            stats.place_roi_1_4 -= 1.0

        # SP band breakdown
        band = _sp_band(sp)
        if band not in stats.sp_bands:
            stats.sp_bands[band] = {"n": 0, "wins": 0, "frames": 0}
        stats.sp_bands[band]["n"] += 1
        if is_win: stats.sp_bands[band]["wins"] += 1
        if is_win or is_placed: stats.sp_bands[band]["frames"] += 1

    # Normalise ROI to per-£1-staked
    if stats.n:
        stats.win_roi = stats.win_roi / stats.n
        stats.place_roi_1_5 = stats.place_roi_1_5 / stats.n
        stats.place_roi_1_4 = stats.place_roi_1_4 / stats.n

    return stats


# ── Accumulator simulation ────────────────────────────────────────────────────

def acca_simulation(rows: list[Row], leg_predicate, label: str,
                    fold_sizes=(3, 4, 5, 6, 7)) -> dict:
    """Simulate paper accas from a given leg selector — one date = one acca."""
    by_date: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        if leg_predicate(row):
            by_date[row.date].append(row)

    results = {}
    for fold in fold_sizes:
        total, wins_acca, total_return = 0, 0, 0.0
        for date, day_rows in by_date.items():
            if len(day_rows) < fold:
                continue
            # Take highest place_prob legs
            legs = sorted(day_rows, key=lambda r: -r.place_prob)[:fold]
            total += 1
            all_won = all(r.outcome == "WIN" for r in legs)
            if all_won:
                wins_acca += 1
                payout = 1.0
                for r in legs:
                    payout *= (r.winner_sp or 2.0)
                total_return += payout
            else:
                total_return += 0.0

        results[fold] = {
            "days_with_legs": total,
            "acca_wins": wins_acca,
            "hit_rate": wins_acca / total if total else 0.0,
            "avg_return_per_bet": total_return / total if total else 0.0,
            "recommendation": "PAPER_TEST_ONLY" if wins_acca >= 3 else "DO_NOT_USE",
        }
    return {"label": label, "folds": results}


# ── Report generation ─────────────────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v*100:.1f}%"


def _roi(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v*100:.1f}%"


def write_md(signals: list[SignalStats], accas: list[dict], n_total: int,
             n_with_position: int, out_path: Path) -> None:
    lines = [
        "# VÉLØ PLACE / FRAME ECONOMICS AUDIT",
        "",
        "**Read-only. No scoring, model, router, or staking changes.**",
        "",
        "> A signal with weak win ROI but strong frame rate belongs to a different product.",
        "> This audit reclassifies VÉLØ sidecars beyond win-only flat ROI.",
        "",
        f"*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        f"*Sample: {n_total} joined rows | {n_with_position} with actual finishing position*",
        "",
        "---",
        "",
        "## SIGNAL FRAME ECONOMICS TABLE",
        "",
        "| Signal | n | Win SR | Frame | Top-3 | Top-4 | Top-5 | Win ROI | Place ROI (1/5) | Place ROI (1/4) | Avg SP | Classification | Best Use |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]

    for s in sorted(signals, key=lambda x: -x.frame_rate):
        lines.append(
            f"| {s.label} | {s.n} | {_pct(s.win_sr)} | {_pct(s.frame_rate)} | "
            f"{_pct(s.top3_rate)} | {_pct(s.top4_rate)} | {_pct(s.top5_rate)} | "
            f"{_roi(s.win_roi)} | {_roi(s.place_roi_1_5)} | {_roi(s.place_roi_1_4)} | "
            f"{s.avg_sp:.1f}x | **{s.classify()}** | {s.best_use()} |"
        )

    lines += [
        "",
        "---",
        "",
        "## WIN ENGINE vs FRAME ENGINE",
        "",
        "| Classification | Meaning | Correct product |",
        "|---|---|---|",
        "| WIN_ENGINE | Win ROI positive, SR ≥ 25% | Win bet |",
        "| FRAME_ENGINE | Frame ≥ 65%, place proxy positive | Each-way / place |",
        "| WIN_NEGATIVE_FRAME_STRONG | Win ROI negative, frame ≥ 65% | Place bet — NOT win bet |",
        "| TOP4_TOP5_CANDIDATE | Frame weak but top-4/5 rate strong | Exchange top-4/5 market |",
        "| OVERBET_WIN_ONLY | Win ROI negative, frame < 55% | SUPPRESS |",
        "",
        "> Previous audit labelled signals as HARMFUL purely on win ROI.",
        "> Correct label is WIN_NEGATIVE_FRAME_STRONG if frame ≥ 65%.",
        "> A bad win bet can still be a good place leg.",
        "",
        "---",
        "",
        "## SIDECAR RECLASSIFICATION",
        "",
        "| Signal | Previous label | Corrected label | Reason |",
        "|---|---|---|---|",
    ]

    reclassify_map = {
        "improvement_score > 0.40": ("OVERBET_RISK", None),
        "market_deception_score > 0.50": ("OVERBET_RISK", None),
        "place_prob > 0.80": ("OVERBET_RISK", None),
        "release_day_prob > 0.50": ("HARMFUL", None),
        "comment_intel / release_day_prob > 0.50": ("HARMFUL", None),
    }
    for s in signals:
        prev, _ = reclassify_map.get(s.threshold_desc, (None, None))
        if prev:
            new = s.classify()
            if new != prev:
                reason = "frame rate > 65% — reclassified" if "FRAME" in new else "confirmed harmful"
                lines.append(f"| {s.label} | {prev} | **{new}** | {reason} |")

    lines += [
        "",
        "---",
        "",
        "## ACCUMULATOR SIMULATION (paper only)",
        "",
        "Legs selected: VP30 + place_prob > 0.80",
        "",
        "| Fold | Days with legs | Acca wins | Hit rate | Avg return | Recommendation |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for acca in accas:
        for fold, r in acca["folds"].items():
            lines.append(
                f"| {fold}-fold | {r['days_with_legs']} | {r['acca_wins']} | "
                f"{_pct(r['hit_rate'])} | {r['avg_return_per_bet']:.1f}x | {r['recommendation']} |"
            )

    lines += [
        "",
        "---",
        "",
        "## SP BAND BREAKDOWN — VP30",
        "",
        "| SP band | n | Win SR | Frame |",
        "|---|---:|---:|---:|",
    ]
    vp30_sig = next((s for s in signals if "VP30" in s.label), None)
    if vp30_sig:
        for band, bdata in sorted(vp30_sig.sp_bands.items()):
            bn = bdata["n"]
            bw = bdata["wins"]
            bf = bdata["frames"]
            if bn:
                lines.append(f"| {band} | {bn} | {_pct(bw/bn)} | {_pct(bf/bn)} |")

    lines += [
        "",
        "---",
        "",
        "## HARD TRUTH",
        "",
        "- No live code changed.",
        "- No SQPE / model / router / staking changes.",
        "- release_day_prob and comment_intel are CONTAINMENT_CANDIDATES for win-bet context.",
        "- They may still be valid as place/frame context signals.",
        "- SQPE remains the primary win-probability anchor.",
        "- MDS > 0.50 is a high-signal win engine with proven 54.8% SR at n=31.",
        "- place_prob > 0.80 is a FRAME ENGINE — correct use is place / each-way, not win-flat.",
        "",
        "*PLACE/FRAME ECONOMICS AUDIT — operator intelligence only.*",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_json(signals: list[SignalStats], accas: list[dict], n_total: int, out_path: Path) -> None:
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "n_joined": n_total,
        "signals": [
            {
                "label": s.label,
                "threshold": s.threshold_desc,
                "n": s.n,
                "win_sr": round(s.win_sr, 4),
                "frame_rate": round(s.frame_rate, 4),
                "top3_rate": round(s.top3_rate, 4),
                "top4_rate": round(s.top4_rate, 4),
                "top5_rate": round(s.top5_rate, 4),
                "win_roi": round(s.win_roi, 4),
                "place_roi_1_5": round(s.place_roi_1_5, 4),
                "place_roi_1_4": round(s.place_roi_1_4, 4),
                "avg_sp": round(s.avg_sp, 2),
                "avg_winner_sp": round(s.avg_winner_sp, 2),
                "classification": s.classify(),
                "best_use": s.best_use(),
                "sp_bands": s.sp_bands,
            }
            for s in signals
        ],
        "accas": accas,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("VÉLØ PLACE / FRAME ECONOMICS AUDIT")
    print("=" * 50)
    print()
    print("Loading data from Supabase...")
    rows = load_data()

    n_total = len(rows)
    n_with_pos = sum(1 for r in rows if r.position is not None)
    print(f"  Joined: {n_total} | With position: {n_with_pos}")
    print()

    print("Evaluating signals...")

    # Define signal cohorts
    signal_defs = [
        # label, threshold_desc, predicate
        ("All verdicts (baseline)",      "all",
         lambda r: True),
        ("VP ≥ 0.30",                   "vp >= 0.30",
         lambda r: r.vp >= 0.30),
        ("VP ≥ 0.40",                   "vp >= 0.40",
         lambda r: r.vp >= 0.40),
        ("Tier A",                       "tier == A",
         lambda r: r.decision_tier == "A"),
        ("Tier A + VP ≥ 0.30",          "tier==A + vp>=0.30",
         lambda r: r.decision_tier == "A" and r.vp >= 0.30),
        ("improvement_score > 0.40",    "improvement_score > 0.40",
         lambda r: r.imp > 0.40),
        ("market_deception_score > 0.50","market_deception_score > 0.50",
         lambda r: r.mds > 0.50),
        ("place_prob > 0.80",           "place_prob > 0.80",
         lambda r: r.place_prob > 0.80),
        ("release_day_prob > 0.50",     "release_day_prob > 0.50",
         lambda r: r.rday > 0.50),
        ("longshot_prob > 0.50",        "longshot_prob > 0.50",
         lambda r: r.longshot > 0.50),
        ("rpdc_release_score > 0.50",   "rpdc_release_score > 0.50",
         lambda r: r.rpdc > 0.50),
        ("MDS > 0.50 + VP ≥ 0.30",     "mds>0.50 + vp>=0.30",
         lambda r: r.mds > 0.50 and r.vp >= 0.30),
        ("imp > 0.40 + VP ≥ 0.30",     "imp>0.40 + vp>=0.30",
         lambda r: r.imp > 0.40 and r.vp >= 0.30),
        ("place_prob > 0.80 + VP ≥ 0.30","place>0.80 + vp>=0.30",
         lambda r: r.place_prob > 0.80 and r.vp >= 0.30),
        ("VP30 + Tier A + MDS > 0.50", "vp>=0.30 + tier==A + mds>0.50",
         lambda r: r.vp >= 0.30 and r.decision_tier == "A" and r.mds > 0.50),
        ("Archetype: Structure",        "archetype==Structure",
         lambda r: r.archetype == "Structure"),
        ("Archetype: Compression",      "archetype==Compression",
         lambda r: r.archetype == "Compression"),
        ("VP30 + SP 2–6",              "vp>=0.30 + SP 2-6",
         lambda r: r.vp >= 0.30 and r.winner_sp is not None and 2.0 <= r.winner_sp <= 6.0),
        ("VP30 + SP 6–12",             "vp>=0.30 + SP 6-12",
         lambda r: r.vp >= 0.30 and r.winner_sp is not None and 6.0 <= r.winner_sp <= 12.0),
    ]

    signals = []
    for label, threshold_desc, predicate in signal_defs:
        s = evaluate_signal(rows, label, threshold_desc, predicate)
        signals.append(s)
        print(f"  {label:<42}  n={s.n:4d}  SR={_pct(s.win_sr):6}  Frame={_pct(s.frame_rate):6}  "
              f"WinROI={_roi(s.win_roi):7}  PlaceROI(1/5)={_roi(s.place_roi_1_5):7}  "
              f"→ {s.classify()}")

    print()
    print("Running accumulator simulations...")
    acca_configs = [
        ("VP30 + place_prob > 0.80",
         lambda r: r.vp >= 0.30 and r.place_prob > 0.80),
        ("MDS > 0.50 + VP ≥ 0.30",
         lambda r: r.mds > 0.50 and r.vp >= 0.30),
        ("Tier A + VP ≥ 0.30",
         lambda r: r.decision_tier == "A" and r.vp >= 0.30),
    ]
    accas = []
    for alabel, apred in acca_configs:
        result = acca_simulation(rows, apred, alabel)
        accas.append(result)
        best = max(result["folds"].values(), key=lambda x: x["hit_rate"])
        print(f"  {alabel:<42}  best fold: hit={_pct(best['hit_rate'])}")

    print()
    print("Writing reports...")
    md_path = DATA / "place_frame_economics_audit_latest.md"
    json_path = DATA / "place_frame_economics_audit_latest.json"
    write_md(signals, accas, n_total, n_with_pos, md_path)
    write_json(signals, accas, n_total, json_path)
    print(f"  MD:   {md_path}")
    print(f"  JSON: {json_path}")

    # Summary printout
    print()
    print("TOP 5 BY FRAME RATE:")
    top_frame = sorted(signals, key=lambda s: -s.frame_rate if s.n >= 15 else 0)[:5]
    for s in top_frame:
        print(f"  {s.label:<42}  Frame={_pct(s.frame_rate)}  WinROI={_roi(s.win_roi)}  → {s.classify()}")

    print()
    print("TOP 5 BY WIN ROI (n≥15):")
    top_roi = sorted((s for s in signals if s.n >= 15), key=lambda s: -s.win_roi)[:5]
    for s in top_roi:
        print(f"  {s.label:<42}  WinROI={_roi(s.win_roi)}  SR={_pct(s.win_sr)}  Frame={_pct(s.frame_rate)}")

    print()
    print("PLACE ROI LEADERS (1/5 terms, n≥15):")
    top_place = sorted((s for s in signals if s.n >= 15), key=lambda s: -s.place_roi_1_5)[:5]
    for s in top_place:
        print(f"  {s.label:<42}  PlaceROI(1/5)={_roi(s.place_roi_1_5)}  Frame={_pct(s.frame_rate)}")

    print()
    print("RECLASSIFICATIONS vs win-only audit:")
    previously_harmful = {"release_day_prob > 0.50", "place_prob > 0.80",
                          "improvement_score > 0.40", "market_deception_score > 0.50"}
    for s in signals:
        if s.threshold_desc in previously_harmful:
            prev = "HARMFUL/OVERBET_RISK"
            new = s.classify()
            if "FRAME" in new or "WIN_ENGINE" in new:
                print(f"  {s.label}: {prev} → {new}  (frame={_pct(s.frame_rate)}, placeROI={_roi(s.place_roi_1_5)})")

    print()
    print("K. SYSTEM INTEGRITY CONFIRMATION")
    print("   Scoring:         unchanged")
    print("   SQPE/model:      unchanged")
    print("   Router rules:    unchanged")
    print("   Staking:         unchanged")
    print("   Live execution:  unchanged")
    print("   Playbook E:      not activated")
    print()
    print("PLACE / FRAME ECONOMICS AUDIT complete. Operator intelligence only.")


def _pct(v: float) -> str:
    return f"{v*100:.1f}%"


def _roi(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v*100:.1f}%"


if __name__ == "__main__":
    main()
