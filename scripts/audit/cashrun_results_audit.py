"""
CASHRUN Results Audit
======================

Runs the CASHRUN detector across every date that has both per-venue
merged racecard JSON and a Racing API racecard, then matches each scored
horse against closed results.

Rules:
  Read-only. No scoring, model, router, staking, or execution changes.
  Audit and evidence only.

Usage:
    python scripts/cashrun_results_audit.py
    python scripts/cashrun_results_audit.py --dates 2026-04-27,2026-05-01

Outputs:
    data/cashrun_results_audit_latest.md
    data/cashrun_results_audit_latest.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median, mean
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.cashrun_detector import load_horses, CashrunResult

DATA = ROOT / "data"
MERGED = DATA / "racecard_merged"

# ── Venue code → result course name mapping ───────────────────────────────────
# Maps 3-letter venue code from per-venue JSON to Racing API result course string

VENUE_TO_COURSE = {
    "ASC": ["Ascot"],
    "AYR": ["Ayr"],
    "BAT": ["Bath"],
    "BEV": ["Beverley"],
    "BRI": ["Brighton"],
    "CAR": ["Carlisle"],
    "CAT": ["Catterick"],
    "CHE": ["Chester"],
    "CHP": ["Cheltenham"],
    "COR": ["Cork (IRE)", "Cork"],
    "CUR": ["Curragh (IRE)", "Curragh"],
    "DON": ["Doncaster"],
    "DUN": ["Dundalk (IRE)", "Dundalk"],
    "EPS": ["Epsom"],
    "ESS": ["Essex"],
    "FFO": ["Ffos Las"],
    "FON": ["Fontwell"],
    "GOO": ["Goodwood"],
    "GOW": ["Gowran Park (IRE)", "Gowran Park"],
    "HAM": ["Hamilton"],
    "HAY": ["Haydock"],
    "HEX": ["Hexham"],
    "HUN": ["Huntingdon"],
    "KEM": ["Kempton (AW)", "Kempton"],
    "KLB": ["Kilbeggan (IRE)", "Kilbeggan"],
    "LEI": ["Leicester"],
    "LIM": ["Limerick (IRE)", "Limerick"],
    "LIN": ["Lingfield (AW)", "Lingfield"],
    "LUD": ["Ludlow"],
    "MUS": ["Musselburgh"],
    "NAA": ["Naas (IRE)", "Naas"],
    "NAV": ["Navan (IRE)", "Navan"],
    "NCS": ["Newcastle (AW)", "Newcastle"],
    "NEW": ["Newcastle (AW)", "Newcastle"],
    "NMK": ["Newmarket"],
    "NOT": ["Nottingham"],
    "PER": ["Perth"],
    "PLU": ["Plumpton"],
    "PON": ["Pontefract"],
    "PUN": ["Punchestown (IRE)", "Punchestown"],
    "RIP": ["Ripon"],
    "SAN": ["Sandown"],
    "SAL": ["Salisbury"],
    "STH": ["Southwell (AW)", "Southwell"],
    "TAU": ["Taunton"],
    "THI": ["Thirsk"],
    "TIP": ["Tipperary (IRE)", "Tipperary"],
    "WAR": ["Warwick"],
    "WIN": ["Windsor"],
    "WOL": ["Wolverhampton (AW)", "Wolverhampton"],
    "WOR": ["Worcester"],
    "YAR": ["Yarmouth"],
    "YOR": ["York"],
}


def _norm_name(s: str) -> str:
    # Strip country suffix (IRE), (GB), (FR), (USA) etc. before normalising
    s = re.sub(r"\s*\([A-Z]{2,4}\)\s*$", "", (s or "").strip())
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _is_placed(position: str, field_size: int) -> bool:
    """Placed = finished in top 3 (or top 2 if field ≤ 4). Non-finishers = False."""
    try:
        pos = int(position)
        if field_size <= 4:
            return pos <= 2
        return pos <= 3
    except (ValueError, TypeError):
        return False


def _is_win(position: str) -> bool:
    try:
        return int(position) == 1
    except (ValueError, TypeError):
        return False


def _sp(runner: dict) -> Optional[float]:
    try:
        return float(runner.get("sp_dec") or 0) or None
    except (ValueError, TypeError):
        return None


# ── Load results for a date ───────────────────────────────────────────────────

def load_results(date_str: str) -> dict[tuple[str, str], dict]:
    """
    Returns a dict keyed by (norm_horse_name, norm_course) → runner result dict.
    Includes field_size on each runner.
    Only UK/IRE races included.
    """
    date_tag = date_str.replace("-", "_")
    path = DATA / f"results_{date_tag}.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    index: dict[tuple[str, str], dict] = {}
    for race in raw.get("results", []):
        if race.get("region") not in ("GB", "IRE"):
            continue
        course = race.get("course", "")
        runners = race.get("runners") or []
        field_size = len(runners)
        for runner in runners:
            horse_norm = _norm_name(runner.get("horse", ""))
            course_norm = _norm_name(course)
            key = (horse_norm, course_norm)
            index[key] = {**runner, "_course": course, "_field_size": field_size}
    return index


# ── Match cashrun horse to result ─────────────────────────────────────────────

def match_result(h: CashrunResult, result_index: dict) -> Optional[dict]:
    horse_norm = _norm_name(h.horse)
    # Try all known course name variants for this venue
    venue_courses = VENUE_TO_COURSE.get(h.venue.upper(), [h.venue])
    for course_name in venue_courses:
        key = (horse_norm, _norm_name(course_name))
        if key in result_index:
            return result_index[key]
    # Fallback: try just horse name across any course at this venue
    for (hn, cn), runner in result_index.items():
        if hn == horse_norm and h.venue.upper()[:3] in runner.get("_course", "").upper()[:3]:
            return runner
    return None


# ── Audit stats accumulator ───────────────────────────────────────────────────

@dataclass
class ClassStats:
    label: str
    total: int = 0
    matched: int = 0
    wins: int = 0
    placed: int = 0
    sp_list: list[float] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    positions: list[int] = field(default_factory=list)
    pnl: float = 0.0

    @property
    def sr(self) -> float:
        return self.wins / self.matched if self.matched else 0.0

    @property
    def frame(self) -> float:
        return self.placed / self.matched if self.matched else 0.0

    @property
    def roi(self) -> float:
        if not self.matched:
            return 0.0
        stake = float(self.matched)
        return self.pnl / stake

    @property
    def avg_sp(self) -> float:
        return mean(self.sp_list) if self.sp_list else 0.0

    @property
    def median_sp(self) -> float:
        return median(self.sp_list) if self.sp_list else 0.0

    @property
    def avg_score(self) -> float:
        return mean(self.scores) if self.scores else 0.0

    @property
    def winner_avg_sp(self) -> float:
        winner_sps = [sp for sp, win in zip(self.sp_list, [r == 1 for r in self.positions]) if win]
        return mean(winner_sps) if winner_sps else 0.0


@dataclass
class HorseRecord:
    date: str
    venue: str
    race_time: str
    horse: str
    cashrun_class: str
    cashrun_score: float
    mark_compression: float
    hidden_form: float
    setup_run: float
    trainer_intent: float
    spotlight_intent: float
    current_or: Optional[int]
    last_winning_or: Optional[int]
    current_ts: Optional[int]
    current_rpr: Optional[int]
    trainer: str
    matched: bool
    position: Optional[str]
    sp: Optional[float]
    won: bool
    placed: bool
    field_size: int
    pnl: float


# ── Per-date runner ───────────────────────────────────────────────────────────

def audit_date(date_str: str) -> tuple[list[HorseRecord], dict]:
    """Score all horses for a date and match against results. Returns (records, meta)."""
    try:
        horses = load_horses(date_str)
    except Exception as e:
        return [], {"date": date_str, "error": str(e), "venues": 0, "horses": 0}

    if not horses:
        return [], {"date": date_str, "error": "no horses loaded", "venues": 0, "horses": 0}

    result_index = load_results(date_str)
    venues = len(set(h.venue for h in horses))

    records: list[HorseRecord] = []
    for h in horses:
        result = match_result(h, result_index)
        matched = result is not None

        if matched:
            pos_str = str(result.get("position", ""))
            sp_val = _sp(result)
            field_size = result.get("_field_size", 10)
            won = _is_win(pos_str)
            placed = _is_placed(pos_str, field_size)
            pnl = (sp_val - 1.0) if won and sp_val else (-1.0 if not won else 0.0)
        else:
            pos_str = None
            sp_val = None
            field_size = 0
            won = False
            placed = False
            pnl = 0.0

        sig = h.signals
        records.append(HorseRecord(
            date=date_str,
            venue=h.venue,
            race_time=h.race_time,
            horse=h.horse,
            cashrun_class=h.cashrun_class,
            cashrun_score=h.cashrun_score or 0.0,
            mark_compression=sig.mark_compression if sig else 0.0,
            hidden_form=sig.hidden_form if sig else 0.0,
            setup_run=sig.setup_run if sig else 0.0,
            trainer_intent=sig.trainer_intent if sig else 0.0,
            spotlight_intent=sig.spotlight_intent if sig else 0.0,
            current_or=h.current_or,
            last_winning_or=h.last_winning_or,
            current_ts=h.current_ts,
            current_rpr=h.current_rpr,
            trainer=h.trainer,
            matched=matched,
            position=pos_str if matched else None,
            sp=sp_val,
            won=won,
            placed=placed,
            field_size=field_size,
            pnl=pnl,
        ))

    meta = {
        "date": date_str,
        "venues": venues,
        "horses": len(horses),
        "matched": sum(1 for r in records if r.matched),
        "ready": sum(1 for r in records if r.cashrun_class == "CASHRUN_READY"),
        "watch": sum(1 for r in records if r.cashrun_class == "CASHRUN_WATCH"),
    }
    return records, meta


# ── Aggregate stats ───────────────────────────────────────────────────────────

def aggregate(records: list[HorseRecord]) -> dict[str, ClassStats]:
    stats = {
        "CASHRUN_READY": ClassStats("CASHRUN_READY"),
        "CASHRUN_WATCH": ClassStats("CASHRUN_WATCH"),
        "WEAK_SIGNAL":   ClassStats("WEAK_SIGNAL"),
        "SUPPRESS":      ClassStats("SUPPRESS"),
    }
    for r in records:
        cls = r.cashrun_class
        if cls not in stats:
            continue
        s = stats[cls]
        s.total += 1
        if not r.matched:
            continue
        s.matched += 1
        s.scores.append(r.cashrun_score)
        if r.sp:
            s.sp_list.append(r.sp)
        try:
            s.positions.append(int(r.position))
        except (TypeError, ValueError):
            pass
        if r.won:
            s.wins += 1
        if r.placed:
            s.placed += 1
        s.pnl += r.pnl

    return stats


# ── Score correlation ─────────────────────────────────────────────────────────

def score_correlation(records: list[HorseRecord]) -> str:
    matched = [r for r in records if r.matched and r.sp]
    if len(matched) < 10:
        return "insufficient data for correlation (n<10)"

    # Bucket by score band and compute SR/frame
    bands = [(75, 100), (55, 74), (35, 54), (0, 34)]
    lines = ["Score band | n | SR | Frame | Avg SP | ROI"]
    lines.append("---|---|---|---|---|---")
    for lo, hi in bands:
        bucket = [r for r in matched if lo <= r.cashrun_score <= hi]
        if not bucket:
            continue
        wins = sum(1 for r in bucket if r.won)
        placed = sum(1 for r in bucket if r.placed)
        sp_vals = [r.sp for r in bucket if r.sp]
        pnl = sum(r.pnl for r in bucket)
        n = len(bucket)
        sr = f"{100*wins//n}%" if n else "—"
        fr = f"{100*placed//n}%" if n else "—"
        avgsp = f"{mean(sp_vals):.1f}" if sp_vals else "—"
        roi = f"{100*pnl/n:+.0f}%" if n else "—"
        lines.append(f"{lo}–{hi} | {n} | {sr} | {fr} | {avgsp} | {roi}")
    return "\n".join(lines)


# ── Suppress miss analysis ────────────────────────────────────────────────────

def suppress_winners(records: list[HorseRecord]) -> list[HorseRecord]:
    return [r for r in records if r.cashrun_class == "SUPPRESS" and r.won]


def high_score_losers(records: list[HorseRecord], threshold: float = 65.0) -> list[HorseRecord]:
    return sorted(
        [r for r in records if r.cashrun_score >= threshold and r.matched and not r.placed],
        key=lambda r: -r.cashrun_score
    )


def low_score_winners(records: list[HorseRecord], threshold: float = 35.0) -> list[HorseRecord]:
    return sorted(
        [r for r in records if r.cashrun_score < threshold and r.matched and r.won],
        key=lambda r: r.cashrun_score
    )


# ── Output formatters ─────────────────────────────────────────────────────────

def _pct(n: int, d: int) -> str:
    return f"{100*n//d}%" if d else "—"


def _fmt_result(r: HorseRecord) -> str:
    pos = r.position or "?"
    sp = f"{r.sp:.2f}" if r.sp else "?"
    outcome = "WIN" if r.won else ("PLACED" if r.placed else "MISS")
    pnl = f"{r.pnl:+.2f}" if r.matched else "—"
    return f"{r.date} {r.venue} {r.race_time} | {r.horse} | score={r.cashrun_score:.0f} | pos={pos} | SP={sp} | {outcome} | P&L={pnl}"


def build_report(all_records: list[HorseRecord], date_metas: list[dict]) -> str:
    lines = [
        "# VÉLØ CASHRUN Results Audit",
        "",
        "**Read-only audit. No betting instruction. No scoring change. No execution.**",
        "",
        "---",
        "",
        "## Dates Audited",
        "",
        "| Date | Venues | Horses | Matched | READY | WATCH |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for m in date_metas:
        err = m.get("error", "")
        if err:
            lines.append(f"| {m['date']} | — | — | — | — | — | ERROR: {err} |")
        else:
            lines.append(
                f"| {m['date']} | {m['venues']} | {m['horses']} "
                f"| {m['matched']} | {m['ready']} | {m['watch']} |"
            )

    total_horses = len(all_records)
    total_matched = sum(1 for r in all_records if r.matched)
    lines += [
        "",
        f"**Total horses scored:** {total_horses}",
        f"**Total result-matched:** {total_matched}",
        f"**Unmatched (result not in file):** {total_horses - total_matched}",
        "",
        "---",
        "",
        "## Signal Class Results",
        "",
        "| Class | Total | Matched | Wins | Placed | SR | Frame | Avg SP | Median SP | ROI | Avg Score |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    stats = aggregate(all_records)
    for cls in ["CASHRUN_READY", "CASHRUN_WATCH", "WEAK_SIGNAL", "SUPPRESS"]:
        s = stats[cls]
        lines.append(
            f"| {cls} | {s.total} | {s.matched} | {s.wins} | {s.placed} "
            f"| {_pct(s.wins, s.matched)} | {_pct(s.placed, s.matched)} "
            f"| {s.avg_sp:.1f} | {s.median_sp:.1f} | {s.roi*100:+.0f}% | {s.avg_score:.0f} |"
        )

    # Sample size warning
    ready_n = stats["CASHRUN_READY"].matched
    if ready_n < 10:
        lines += [
            "",
            f"> ⚠ CASHRUN_READY matched sample = {ready_n} — LOW_SAMPLE. "
            "Do not draw conclusions from SR/ROI until n≥10.",
        ]

    # Score correlation
    lines += [
        "",
        "---",
        "",
        "## Score Band Correlation",
        "",
        score_correlation(all_records),
        "",
        "---",
        "",
    ]

    # CASHRUN_READY detail
    ready_records = [r for r in all_records if r.cashrun_class == "CASHRUN_READY"]
    lines += [
        "## CASHRUN_READY — Full Detail",
        "",
        f"n={len(ready_records)} total | {sum(1 for r in ready_records if r.matched)} result-matched",
        "",
    ]
    for r in sorted(ready_records, key=lambda x: (-x.cashrun_score, x.date)):
        lines.append(f"- {_fmt_result(r)}")
        lines.append(
            f"  Signals: mark={r.mark_compression:.0f} | form={r.hidden_form:.0f} "
            f"| setup={r.setup_run:.0f} | trainer={r.trainer_intent:.0f} | spot={r.spotlight_intent:.0f}"
        )

    # Police Academy specific audit
    pa_records = [r for r in all_records if _norm_name(r.horse) == _norm_name("Police Academy")]
    if pa_records:
        lines += [
            "",
            "---",
            "",
            "## Police Academy — Specific Audit",
            "",
        ]
        for r in pa_records:
            pos = r.position or "no result"
            sp = f"{r.sp:.2f}" if r.sp else "?"
            outcome = "WIN" if r.won else ("PLACED" if r.placed else ("MISS" if r.matched else "NO RESULT"))
            pnl = f"{r.pnl:+.2f}" if r.matched else "—"
            lines += [
                f"| Field | Value |",
                f"|---|---|",
                f"| Date | {r.date} |",
                f"| Race | {r.venue} {r.race_time} |",
                f"| CASHRUN class | **{r.cashrun_class}** |",
                f"| CASHRUN score | **{r.cashrun_score:.0f}/100** |",
                f"| SP | {sp} |",
                f"| Finishing position | {pos} |",
                f"| Field size | {r.field_size} |",
                f"| Outcome | **{outcome}** |",
                f"| P&L (flat 1pt) | {pnl} |",
                f"| Mark compression | {r.mark_compression:.0f}/30 |",
                f"| TS/RPR hidden form | {r.hidden_form:.0f}/20 |",
                f"| Setup run pattern | {r.setup_run:.0f}/20 |",
                f"| Trainer/jockey intent | {r.trainer_intent:.0f}/15 |",
                f"| Spotlight/postdata | {r.spotlight_intent:.0f}/15 |",
                "",
            ]

    # Top 20 by score with result
    matched_sorted = sorted(
        [r for r in all_records if r.matched],
        key=lambda r: -r.cashrun_score
    )[:20]
    lines += [
        "",
        "---",
        "",
        "## Top 20 Scores — With Result",
        "",
        "| Horse | Date | Venue | Score | Class | SP | Pos | Outcome |",
        "|---|---|---|---:|---|---:|---:|---|",
    ]
    for r in matched_sorted:
        pos = r.position or "?"
        sp = f"{r.sp:.2f}" if r.sp else "?"
        outcome = "WIN" if r.won else ("PLC" if r.placed else "MISS")
        lines.append(f"| {r.horse} | {r.date} | {r.venue} | {r.cashrun_score:.0f} | {r.cashrun_class} | {sp} | {pos} | {outcome} |")

    # CASHRUN_WATCH summary
    watch_matched = [r for r in all_records if r.cashrun_class == "CASHRUN_WATCH" and r.matched]
    lines += [
        "",
        "---",
        "",
        "## CASHRUN_WATCH — Summary",
        "",
        f"n_total={stats['CASHRUN_WATCH'].total} | matched={stats['CASHRUN_WATCH'].matched} "
        f"| SR={_pct(stats['CASHRUN_WATCH'].wins, stats['CASHRUN_WATCH'].matched)} "
        f"| Frame={_pct(stats['CASHRUN_WATCH'].placed, stats['CASHRUN_WATCH'].matched)} "
        f"| ROI={stats['CASHRUN_WATCH'].roi*100:+.0f}%",
        "",
        "**CASHRUN_WATCH winners:**",
    ]
    watch_winners = [r for r in watch_matched if r.won]
    if watch_winners:
        for r in sorted(watch_winners, key=lambda r: r.cashrun_score, reverse=True):
            lines.append(f"- {_fmt_result(r)}")
    else:
        lines.append("- none")

    # Suppress winners
    s_winners = suppress_winners(all_records)
    lines += [
        "",
        "---",
        "",
        f"## SUPPRESS Winners — Detector Misses ({len(s_winners)})",
        "",
        "These won despite being SUPPRESS. Each is a detector blind spot.",
        "",
    ]
    if s_winners:
        for r in sorted(s_winners, key=lambda r: r.cashrun_score):
            lines.append(f"- {_fmt_result(r)}")
            lines.append(
                f"  Signals: mark={r.mark_compression:.0f} | form={r.hidden_form:.0f} "
                f"| setup={r.setup_run:.0f} | trainer={r.trainer_intent:.0f} | spot={r.spotlight_intent:.0f}"
            )
    else:
        lines.append("- none")

    # High-score losers
    hs_losers = high_score_losers(all_records)
    lines += [
        "",
        "---",
        "",
        f"## High-Score Losers (score≥65, unplaced) — False Positives ({len(hs_losers)})",
        "",
    ]
    if hs_losers:
        for r in hs_losers[:15]:
            lines.append(f"- {_fmt_result(r)}")
    else:
        lines.append("- none")

    # Low-score winners
    ls_winners = low_score_winners(all_records)
    lines += [
        "",
        "---",
        "",
        f"## Low-Score Winners (score<35, won) — Blind Spots ({len(ls_winners)})",
        "",
    ]
    if ls_winners:
        for r in ls_winners[:10]:
            lines.append(f"- {_fmt_result(r)}")
    else:
        lines.append("- none")

    # Per-date breakdown
    lines += [
        "",
        "---",
        "",
        "## Per-Date Breakdown",
        "",
        "| Date | READY SR | READY Frame | WATCH SR | WATCH Frame | SUPPRESS SR |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    by_date: dict[str, list[HorseRecord]] = defaultdict(list)
    for r in all_records:
        by_date[r.date].append(r)
    for d in sorted(by_date.keys()):
        date_records = by_date[d]
        date_stats = aggregate(date_records)
        rs = date_stats["CASHRUN_READY"]
        ws = date_stats["CASHRUN_WATCH"]
        ss = date_stats["SUPPRESS"]
        lines.append(
            f"| {d} "
            f"| {_pct(rs.wins, rs.matched)} (n={rs.matched}) "
            f"| {_pct(rs.placed, rs.matched)} "
            f"| {_pct(ws.wins, ws.matched)} (n={ws.matched}) "
            f"| {_pct(ws.placed, ws.matched)} "
            f"| {_pct(ss.wins, ss.matched)} (n={ss.matched}) |"
        )

    # Classification verdict
    ready_s = stats["CASHRUN_READY"]
    watch_s = stats["CASHRUN_WATCH"]
    if ready_s.matched < 10:
        verdict = "CASHRUN_NEEDS_MORE_DATA"
        verdict_reason = f"CASHRUN_READY matched sample = {ready_s.matched} (need ≥10)"
    elif ready_s.sr >= 0.25 and ready_s.frame >= 0.60:
        if ready_s.roi > 0:
            verdict = "CASHRUN_SIGNAL_CONFIRMED"
            verdict_reason = f"SR={ready_s.sr*100:.0f}% Frame={ready_s.frame*100:.0f}% ROI={ready_s.roi*100:+.0f}%"
        else:
            verdict = "CASHRUN_FRAME_SIGNAL_ONLY"
            verdict_reason = f"Frame={ready_s.frame*100:.0f}% positive but ROI={ready_s.roi*100:+.0f}%"
    elif ready_s.sr < 0.10 and ready_s.matched >= 10:
        verdict = "CASHRUN_BROKEN"
        verdict_reason = f"SR={ready_s.sr*100:.0f}% — detector not separating signal from noise"
    elif watch_s.frame >= 0.55 and watch_s.matched >= 15:
        verdict = "CASHRUN_FRAME_SIGNAL_ONLY"
        verdict_reason = f"WATCH frame={watch_s.frame*100:.0f}% at n={watch_s.matched} — place signal present"
    else:
        verdict = "CASHRUN_NEEDS_MORE_DATA"
        verdict_reason = f"Matched n={ready_s.matched} READY, {watch_s.matched} WATCH — not enough for verdict"

    lines += [
        "",
        "---",
        "",
        "## CASHRUN Classification Verdict",
        "",
        f"**{verdict}**",
        "",
        f"Reason: {verdict_reason}",
        "",
        "| Label | Meaning |",
        "|---|---|",
        "| CASHRUN_SIGNAL_CONFIRMED | SR≥25% + Frame≥60% + ROI positive on READY class |",
        "| CASHRUN_FRAME_SIGNAL_ONLY | Frame present but win ROI negative — place/EW angle only |",
        "| CASHRUN_OVERBET_RISK | Signal fires but negative ROI at all price levels |",
        "| CASHRUN_NEEDS_MORE_DATA | Matched READY sample too small for verdict |",
        "| CASHRUN_BROKEN | SR below chance baseline, detector not separating |",
        "",
        "---",
        "",
        "## System Integrity",
        "",
        "- Scoring: **unchanged**",
        "- SQPE / model: **unchanged**",
        "- Router rules: **unchanged**",
        "- Staking: **none**",
        "- Live execution: **none**",
        "- Playbook E: **not activated**",
        "",
        "*CASHRUN results audit — operator intelligence only.*",
    ]

    return "\n".join(lines)


def build_csv(all_records: list[HorseRecord]) -> str:
    rows = []
    for r in all_records:
        rows.append({
            "date": r.date, "venue": r.venue, "race_time": r.race_time,
            "horse": r.horse, "cashrun_class": r.cashrun_class,
            "cashrun_score": round(r.cashrun_score, 1),
            "mark_compression": r.mark_compression, "hidden_form": r.hidden_form,
            "setup_run": r.setup_run, "trainer_intent": r.trainer_intent,
            "spotlight_intent": r.spotlight_intent,
            "current_or": r.current_or, "last_winning_or": r.last_winning_or,
            "current_ts": r.current_ts, "current_rpr": r.current_rpr,
            "trainer": r.trainer, "matched": r.matched,
            "position": r.position, "sp": r.sp, "won": r.won,
            "placed": r.placed, "field_size": r.field_size, "pnl": round(r.pnl, 2),
        })
    if not rows:
        return ""
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CASHRUN closed-result audit")
    parser.add_argument("--dates", default=None,
                        help="Comma-separated YYYY-MM-DD list. Default: auto-detect from merged JSON.")
    args = parser.parse_args()

    if args.dates:
        dates = [d.strip() for d in args.dates.split(",")]
    else:
        # Auto-detect: dates with both merged JSON files AND results JSON
        merged_dates = set()
        for f in MERGED.glob("racecard_*_????-??-??.json"):
            m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
            if m:
                merged_dates.add(m.group(1))
        result_dates = set()
        for f in DATA.glob("results_????_??_??.json"):
            m = re.search(r"(\d{4})_(\d{2})_(\d{2})", f.name)
            if m:
                result_dates.add(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        dates = sorted(merged_dates & result_dates)

    print(f"VÉLØ CASHRUN RESULTS AUDIT")
    print(f"Dates to audit: {dates}")
    print("=" * 60)

    all_records: list[HorseRecord] = []
    date_metas: list[dict] = []

    for date_str in dates:
        print(f"\n  Auditing {date_str}...")
        records, meta = audit_date(date_str)
        all_records.extend(records)
        date_metas.append(meta)
        if meta.get("error"):
            print(f"    ERROR: {meta['error']}")
        else:
            matched = meta["matched"]
            total = meta["horses"]
            ready = meta["ready"]
            watch = meta["watch"]
            print(f"    {total} horses | {matched} matched | READY={ready} WATCH={watch}")

    if not all_records:
        print("\nNo records to audit. Check merged JSON and results files.")
        sys.exit(1)

    stats = aggregate(all_records)
    print("\n" + "=" * 60)
    print("AGGREGATE RESULTS")
    print("=" * 60)
    for cls in ["CASHRUN_READY", "CASHRUN_WATCH", "WEAK_SIGNAL", "SUPPRESS"]:
        s = stats[cls]
        if s.matched == 0:
            continue
        print(f"  {cls:<20} n={s.matched:<4} SR={_pct(s.wins, s.matched):<5} "
              f"Frame={_pct(s.placed, s.matched):<5} ROI={s.roi*100:+.0f}%")

    # Police Academy
    pa = [r for r in all_records if _norm_name(r.horse) == _norm_name("Police Academy")]
    if pa:
        r = pa[0]
        outcome = "WIN" if r.won else ("PLACED" if r.placed else ("MISS" if r.matched else "NO RESULT"))
        print(f"\n  Police Academy ({r.date} {r.venue} {r.race_time}):")
        print(f"    Score={r.cashrun_score:.0f} Class={r.cashrun_class} SP={r.sp} Pos={r.position} → {outcome}")

    md = build_report(all_records, date_metas)
    md_path = DATA / "cashrun_results_audit_latest.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"\n  MD: {md_path}")

    csv_text = build_csv(all_records)
    csv_path = DATA / "cashrun_results_audit_latest.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    print(f"  CSV: {csv_path}")

    print("\nK. SYSTEM INTEGRITY CONFIRMATION")
    print("   Scoring:         unchanged")
    print("   SQPE/model:      unchanged")
    print("   Router rules:    unchanged")
    print("   Staking:         unchanged")
    print("   Live execution:  unchanged")
    print("   Playbook E:      not activated")


if __name__ == "__main__":
    main()
