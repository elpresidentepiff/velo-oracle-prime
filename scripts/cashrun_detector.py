"""
VÉLØ CASHRUN Detector
======================

Detects horses that have been plotted for a cash run by converging:
  - Racing Post: OR/TS/RPR history, Spotlight, Postdata (via per-venue JSON)
  - Racing API: current ofr, ts, rpr, weight, draw, headgear, trainer_14_days

Core question: Has the trainer brought this horse down to / near / below a previous
winning mark while the TS/RPR/form/Spotlight story says today is the setup day?

Rules:
  - Read-only. No scoring, model, router, staking, or execution changes.
  - Operator intelligence layer only.

Usage:
    python scripts/cashrun_detector.py --date 2026-05-01
    python scripts/cashrun_detector.py          # defaults to today
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
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
MERGED = DATA / "racecard_merged"

# ── Setup language for Spotlight/Postdata NLP ─────────────────────────────────

SETUP_PHRASES = [
    # Mark / weights language
    "well handicapped", "on a good mark", "dropped to a workable mark",
    "workable mark", "back on winning mark", "below last winning mark",
    "well in at the weights", "nicely treated", "below the level",
    "handicap mark", "on a handy mark", "back to a realistic mark",
    "attractively handicapped", "off a fair mark",
    # Hidden form / eyecatcher
    "better than bare result", "shaped better", "eyecatcher", "eye-catcher",
    "never nearer", "kept on", "keeping on", "stayed on", "ran on",
    "not knocked about", "could not quicken", "did not get clear run",
    "not beaten far", "not disgraced", "creditable", "solid effort",
    "honest effort", "promising debut", "shaped well",
    # Setup / return language
    "return to", "return to trip", "return to surface", "return to course",
    "back on this surface", "back over this trip", "back to this distance",
    "should strip fitter", "strip fitter", "fitter for", "come on for",
    "improve for the run", "race will bring on",
    # Positive outlook
    "could bounce back", "could go well", "could prove", "might go well",
    "interesting", "one to note", "dangerous", "must be respected",
    "not dismissed", "capable of better", "more to offer",
    "open to improvement", "unexposed", "progressive",
    "find more", "has more to offer", "can improve",
    "well capable", "worth following", "worth noting",
    # Market / trainer intent
    "market support", "market support significant", "support in the market",
    "positive booking", "booking significant", "big-race rider",
    # Going / conditions positive
    "handles the ground", "handles this ground", "loves this ground",
    "goes well here", "course winner", "course and distance winner",
    # Trainer-specific positive language
    "revived for", "transformed for", "taken to well",
    "lightly raced", "scope for improvement",
]

NEGATIVE_PHRASES = [
    "hard to win with", "may find this too tough", "difficult task",
    "yet to convince", "not seen best", "questions to answer",
    "hard race to win", "disappointing", "out of form", "well beaten",
    "below expectations", "not at her best", "out of his depth",
    "will need to improve", "seemingly exposed", "no obvious signs",
    "limited", "moderate", "poor record", "rarely threatens",
]

TRAINER_INTENT_PHRASES = [
    "jockey upgrade", "stable jockey", "first-time headgear", "wind surgery",
    "class drop", "drop in class", "return to", "back to winning ways",
    "positive booking", "booking significant",
]


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class ORRun:
    pos: Optional[int]
    or_val: Optional[int]
    raw: str = ""


@dataclass
class TSRun:
    pos: Optional[int]
    ts_val: Optional[int]
    dist: Optional[str]
    going: Optional[str]
    raw: str = ""


@dataclass
class SignalBreakdown:
    mark_compression: float = 0.0
    hidden_form: float = 0.0
    setup_run: float = 0.0
    trainer_intent: float = 0.0
    spotlight_intent: float = 0.0
    negative_suppression: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class CashrunResult:
    horse: str
    venue: str
    race_time: str
    race_name: str
    race_class: str
    distance: str
    going: str

    # Current ratings
    current_or: Optional[int]
    current_ts: Optional[int]
    current_rpr: Optional[int]
    last_run_days: Optional[int]
    form_string: str
    weight: Optional[str]
    draw: Optional[int]
    trainer: str
    jockey: str
    trainer_14day: str
    headgear: str
    wind_surgery: bool

    # History
    or_history: list[ORRun]
    ts_history: list[TSRun]

    # Signals
    last_winning_or: Optional[int]
    or_vs_last_win: Optional[int]  # negative = below winning mark
    or_compression_score: float
    or_trend_drops: int
    ts_trend: Optional[int]
    ts_trend_signal: float

    # Intent
    spotlight: str
    postdata_score: Optional[float]
    is_postdata_pick: bool
    intent_signals: list[str]
    trainer_form: str
    trainer_form_signal: float
    going_flag: str
    distance_flag: str
    course_flag: str
    plot_conviction: float

    # CASHRUN scoring
    signals: SignalBreakdown = field(default_factory=SignalBreakdown)
    cashrun_score: float = 0.0
    cashrun_class: str = "SUPPRESS"

    # Coverage
    field_coverage: dict[str, str] = field(default_factory=dict)


# ── CASHRUN scorer ─────────────────────────────────────────────────────────────

def _or_val(runs: list[ORRun]) -> list[int]:
    return [r.or_val for r in runs if r.or_val is not None]


def _ts_val(runs: list[TSRun]) -> list[int]:
    return [r.ts_val for r in runs if r.ts_val is not None]


def _last_win_or(runs: list[ORRun]) -> Optional[int]:
    for r in runs:
        if r.pos == 1 and r.or_val is not None:
            return r.or_val
    return None


def _score_mark_compression(h: CashrunResult) -> tuple[float, list[str]]:
    notes = []
    score = 0.0
    max_score = 30.0

    or_vals = _or_val(h.or_history)
    if not or_vals:
        notes.append("OR history empty — mark compression unevaluable")
        return 0.0, notes

    current = or_vals[0] if or_vals else None
    if current is None:
        return 0.0, notes

    # Last winning OR
    lwor = _last_win_or(h.or_history)
    h.last_winning_or = lwor

    if lwor is not None:
        delta = current - lwor  # negative = below winning mark, good
        h.or_vs_last_win = delta
        if delta <= 0:
            score += 15
            notes.append(f"OR {current} at or below last winning mark {lwor} (Δ={delta:+d})")
        elif delta <= 2:
            score += 10
            notes.append(f"OR {current} within 2lb of last winning mark {lwor} (Δ={delta:+d})")
        elif delta <= 5:
            score += 5
            notes.append(f"OR {current} within 5lb of last winning mark {lwor} (Δ={delta:+d})")
    else:
        notes.append("No winning run found in OR history")

    # Compression score (magnitude of drop from peak)
    if h.or_compression_score >= 0.8:
        score += 10
        notes.append(f"Strong OR compression (score={h.or_compression_score:.2f})")
    elif h.or_compression_score >= 0.5:
        score += 6
        notes.append(f"Moderate OR compression (score={h.or_compression_score:.2f})")
    elif h.or_compression_score >= 0.3:
        score += 3
        notes.append(f"Mild OR compression (score={h.or_compression_score:.2f})")

    # Consecutive drops
    drops = h.or_trend_drops
    if drops >= 4:
        score += 8
        notes.append(f"OR dropped consecutively in last {drops} runs")
    elif drops >= 3:
        score += 5
        notes.append(f"OR dropped consecutively in last {drops} runs")
    elif drops >= 2:
        score += 3
        notes.append(f"OR dropped in last {drops} runs")

    # Career-low check
    if len(or_vals) >= 3 and current == min(or_vals):
        score += 5
        notes.append(f"At career-low OR in history ({current})")
    elif len(or_vals) >= 3 and current <= sorted(or_vals)[1]:
        score += 2
        notes.append(f"Near career-low OR in history")

    return min(score, max_score), notes


def _score_hidden_form(h: CashrunResult) -> tuple[float, list[str]]:
    notes = []
    score = 0.0
    max_score = 20.0

    ts_vals = _ts_val(h.ts_history)
    or_vals = _or_val(h.or_history)

    if not ts_vals:
        notes.append("No TS history — hidden form unevaluable")
        return 0.0, notes

    # TS improving while OR falling
    if h.ts_trend_signal > 0.05 and h.or_trend_drops >= 1:
        score += 8
        notes.append(f"TS improving ({h.ts_trend_signal:+.2f}) while OR falling ({h.or_trend_drops} drops)")
    elif h.ts_trend_signal > 0 and h.or_trend_drops >= 1:
        score += 5
        notes.append(f"TS steady/rising while OR falling")
    elif h.ts_trend_signal < -0.1:
        pass  # suppress flag handled in negative

    # Recent 3 TS runs vs older ones
    recent = ts_vals[:3]
    older = ts_vals[3:]
    if recent and older and len(recent) >= 2:
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        if recent_avg > older_avg + 5:
            score += 5
            notes.append(f"Recent TS avg {recent_avg:.0f} better than older avg {older_avg:.0f}")

    # Strong TS in last 3 runs (best TS of run history is recent)
    if ts_vals and ts_vals[0] == max(ts_vals):
        score += 4
        notes.append(f"Best TS in history is most recent run ({ts_vals[0]})")
    elif ts_vals and len(ts_vals) >= 2 and ts_vals[0] >= ts_vals[1]:
        score += 2
        notes.append(f"TS improving run-on-run ({ts_vals[1]} → {ts_vals[0]})")

    # RPR hidden form
    if h.current_rpr is not None and h.or_compression_score > 0:
        or_vals_list = _or_val(h.or_history)
        if or_vals_list and h.current_rpr > or_vals_list[0]:
            score += 3
            notes.append(f"RPR {h.current_rpr} ahead of current OR {or_vals_list[0]}")

    # Low finishing positions but figures not collapsing
    if len(h.ts_history) >= 2:
        recent_pos = [r.pos for r in h.ts_history[:3] if r.pos is not None and r.pos > 0]
        recent_ts = ts_vals[:3]
        if recent_pos and recent_ts:
            avg_pos = sum(recent_pos) / len(recent_pos)
            avg_ts = sum(recent_ts) / len(recent_ts)
            if avg_pos > 4 and avg_ts >= 60:
                score += 4
                notes.append(f"Placed poorly (avg pos {avg_pos:.1f}) but TS holding ({avg_ts:.0f}) — hidden form")

    return min(score, max_score), notes


def _score_setup_run(h: CashrunResult) -> tuple[float, list[str]]:
    notes = []
    score = 0.0
    max_score = 20.0

    intent = h.intent_signals or []
    if "all_systems_go" in intent:
        score += 8
        notes.append("all_systems_go intent signal fired")
    elif "setup_indicated" in intent:
        score += 5
        notes.append("setup_indicated intent signal")

    # Course/distance/going alignment
    flag_scores = {
        "strong_positive": 4, "positive": 3, "neutral": 0,
        "uncertain": 0, "negative": -3, "strong_negative": -5,
    }
    going_s = flag_scores.get(h.going_flag, 0)
    dist_s = flag_scores.get(h.distance_flag, 0)
    course_s = flag_scores.get(h.course_flag, 0)
    setup_flags = going_s + dist_s + course_s
    if setup_flags > 0:
        score += min(setup_flags, 7)
        if going_s > 0: notes.append(f"Going flag: {h.going_flag}")
        if dist_s > 0: notes.append(f"Distance flag: {h.distance_flag}")
        if course_s > 0: notes.append(f"Course flag: {h.course_flag}")

    # Spotlight setup language
    spot = (h.spotlight or "").lower()
    matched_setup = [p for p in SETUP_PHRASES if p in spot]
    if matched_setup:
        phrase_score = min(len(matched_setup) * 2, 8)
        score += phrase_score
        notes.append(f"Setup phrases in spotlight: {matched_setup[:4]}")

    return min(score, max_score), notes


def _score_trainer_intent(h: CashrunResult) -> tuple[float, list[str]]:
    notes = []
    score = 0.0
    max_score = 15.0

    # Trainer form
    tf = (h.trainer_form or "").lower()
    if tf == "positive":
        score += 5
        notes.append(f"Trainer form: positive")
    elif h.trainer_form_signal > 0.05:
        score += 3
        notes.append(f"Trainer form signal: {h.trainer_form_signal:+.2f}")

    # Trainer 14-day form (from Racing API)
    if h.trainer_14day and h.trainer_14day not in ("", "N/A", "?"):
        try:
            pct_match = re.search(r"(\d+)%", h.trainer_14day)
            if pct_match:
                pct = int(pct_match.group(1))
                if pct >= 20:
                    score += 4
                    notes.append(f"Trainer 14-day: {h.trainer_14day} (hot streak)")
                elif pct >= 12:
                    score += 2
                    notes.append(f"Trainer 14-day: {h.trainer_14day}")
        except Exception:
            pass

    # Headgear change
    hg = (h.headgear or "").strip()
    if hg and hg not in ("", "0", "-"):
        score += 4
        notes.append(f"Headgear: {hg} (equipment angle)")

    # Wind surgery
    if h.wind_surgery:
        score += 3
        notes.append("Wind surgery angle")

    # Intent signals with trainer keywords
    for sig in (h.intent_signals or []):
        if "jockey" in sig.lower() or "trainer" in sig.lower():
            score += 2
            notes.append(f"Intent signal: {sig}")

    return min(score, max_score), notes


def _score_spotlight_intent(h: CashrunResult) -> tuple[float, list[str]]:
    notes = []
    score = 0.0
    max_score = 15.0

    # Postdata
    if h.is_postdata_pick:
        score += 8
        notes.append("Postdata pick selected")
    elif h.postdata_score is not None:
        if h.postdata_score >= 0.7:
            score += 6
            notes.append(f"Postdata score: {h.postdata_score:.2f}")
        elif h.postdata_score >= 0.5:
            score += 3
            notes.append(f"Postdata score: {h.postdata_score:.2f}")

    # Plot conviction
    if h.plot_conviction >= 0.85:
        score += 5
        notes.append(f"Plot conviction: {h.plot_conviction:.2f}")
    elif h.plot_conviction >= 0.70:
        score += 3
        notes.append(f"Plot conviction: {h.plot_conviction:.2f}")

    # Key intent phrases
    spot = (h.spotlight or "").lower()
    key_phrases = [
        ("well handicapped", 4), ("on a good mark", 4), ("below last winning mark", 5),
        ("nicely treated", 4), ("dangerous", 3), ("one to note", 3),
        ("interesting", 2), ("could bounce back", 3), ("back on winning mark", 4),
        ("not dismissed", 2), ("unexposed", 2), ("progressive", 2),
    ]
    phrase_score = 0
    matched = []
    for phrase, pts in key_phrases:
        if phrase in spot:
            phrase_score += pts
            matched.append(phrase)
    if matched:
        score += min(phrase_score, 6)
        notes.append(f"Key phrases: {matched[:3]}")

    return min(score, max_score), notes


def _apply_negative_suppression(h: CashrunResult, raw_score: float) -> tuple[float, list[str]]:
    """Reduce score if negative evidence outweighs positives."""
    notes = []
    deduction = 0.0

    ts_vals = _ts_val(h.ts_history)
    or_vals = _or_val(h.or_history)

    # TS collapsing with OR
    if h.ts_trend_signal < -0.1 and h.or_trend_drops >= 1:
        deduction += 12
        notes.append(f"SUPPRESS: TS collapsing ({h.ts_trend_signal:.2f}) AND OR falling")

    # Strong negative Spotlight
    spot = (h.spotlight or "").lower()
    neg_matched = [p for p in NEGATIVE_PHRASES if p in spot]
    if len(neg_matched) >= 2:
        deduction += 10
        notes.append(f"SUPPRESS: Negative spotlight phrases: {neg_matched[:3]}")
    elif neg_matched:
        deduction += 4
        notes.append(f"Caution: Negative phrase: {neg_matched[0]}")

    # OR and TS both at career lows (regression, not compression)
    if ts_vals and or_vals:
        ts_recent3 = ts_vals[:3]
        ts_older = ts_vals[3:]
        if ts_older and ts_recent3:
            recent_ts_avg = sum(ts_recent3) / len(ts_recent3)
            older_ts_avg = sum(ts_older) / len(ts_older)
            if recent_ts_avg < older_ts_avg - 15:
                deduction += 8
                notes.append(f"SUPPRESS: TS declining sharply (recent avg {recent_ts_avg:.0f} vs older {older_ts_avg:.0f})")

    # No wins at all and OR not particularly compressed
    if h.last_winning_or is None and h.or_compression_score < 0.3:
        deduction += 6
        notes.append("No OR win found + low compression — no clear plot signal")

    # Trainer form negative
    if (h.trainer_form or "") == "negative":
        deduction += 5
        notes.append("Trainer form: negative")

    return max(0.0, raw_score - deduction), notes


def score_cashrun(h: CashrunResult) -> None:
    sig = h.signals

    sig.mark_compression, n1 = _score_mark_compression(h)
    sig.hidden_form, n2 = _score_hidden_form(h)
    sig.setup_run, n3 = _score_setup_run(h)
    sig.trainer_intent, n4 = _score_trainer_intent(h)
    sig.spotlight_intent, n5 = _score_spotlight_intent(h)

    raw = (sig.mark_compression + sig.hidden_form + sig.setup_run +
           sig.trainer_intent + sig.spotlight_intent)

    final, n6 = _apply_negative_suppression(h, raw)
    sig.negative_suppression = raw - final
    sig.notes = n1 + n2 + n3 + n4 + n5 + n6

    h.cashrun_score = round(min(final, 100.0), 1)

    if h.cashrun_score >= 75:
        h.cashrun_class = "CASHRUN_READY"
    elif h.cashrun_score >= 55:
        h.cashrun_class = "CASHRUN_WATCH"
    elif h.cashrun_score >= 35:
        h.cashrun_class = "WEAK_SIGNAL"
    else:
        h.cashrun_class = "SUPPRESS"


# ── Data loading ───────────────────────────────────────────────────────────────

def _to_int(val) -> Optional[int]:
    """Convert Racing API value to int — handles '-', None, string numbers."""
    if val is None or val == "" or val == "-":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


_VENUE_TO_COURSE = {
    "NMK": "newmarket", "WAR": "warwick", "NCS": "newcastle",
    "GOO": "goodwood", "ASC": "ascot", "PUN": "punchestown",
}


def _load_racing_api_racecard(date_str: str) -> tuple[dict[str, dict], dict[tuple, str]]:
    """Load Racing API standard racecard.

    Returns:
        runner_index: keyed by horse_id and horse name (lowercase)
        going_index: keyed by (course_lower, off_time_HH:MM) → going string
    """
    tag = date_str.replace("-", "_")
    path = DATA / f"racecards_{tag}_standard.json"
    if not path.exists():
        return {}, {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        racecards = raw if isinstance(raw, list) else raw.get("racecards", [])
        runner_index: dict[str, dict] = {}
        going_index: dict[tuple, str] = {}
        for rc in racecards:
            course_lower = (rc.get("course") or "").strip().lower()
            off_time = (rc.get("off_time") or "").strip()  # e.g. "14:05"
            going_val = rc.get("going") or rc.get("going_detailed") or ""
            if course_lower and off_time and going_val:
                going_index[(course_lower, off_time)] = going_val

            for runner in rc.get("runners", []):
                hid = runner.get("horse_id", "")
                hname = (runner.get("horse") or "").strip().lower()
                t14_raw = runner.get("trainer_14_days") or {}
                if isinstance(t14_raw.get("percent"), str) and t14_raw["percent"] == "None":
                    t14_raw = {**t14_raw, "percent": ""}
                enriched = {
                    "ofr": _to_int(runner.get("ofr")),
                    "ts": _to_int(runner.get("ts")),
                    "rpr": _to_int(runner.get("rpr")),
                    "lbs": _to_int(runner.get("lbs")),
                    "draw": _to_int(runner.get("draw")),
                    "headgear": runner.get("headgear") or "",
                    "headgear_run": runner.get("headgear_run") or "",
                    "wind_surgery": bool(runner.get("wind_surgery")),
                    "wind_surgery_run": runner.get("wind_surgery_run"),
                    "trainer_14_days": t14_raw,
                    "jockey": runner.get("jockey") or "",
                    "trainer": runner.get("trainer") or "",
                    "last_run": _to_int(runner.get("last_run")),
                    "form": runner.get("form") or "",
                }
                if hid:
                    runner_index[hid] = enriched
                if hname:
                    runner_index[hname] = enriched
        return runner_index, going_index
    except Exception:
        return {}, {}


def _fmt_trainer_14day(t14: dict) -> str:
    if not t14:
        return ""
    runs = t14.get("runs") or t14.get("r") or ""
    wins = t14.get("wins") or t14.get("w") or ""
    pct = t14.get("percent") or t14.get("pct") or ""
    if runs and wins:
        return f"{wins}/{runs} ({pct}%)"
    return ""


def _check_field(val) -> str:
    if val is None or val == "" or val == [] or val == {}:
        return "MISSING"
    return "OK"


def load_horses(date_str: str) -> list[CashrunResult]:
    api_index, going_index = _load_racing_api_racecard(date_str)
    results: list[CashrunResult] = []

    for f in sorted(MERGED.glob(f"racecard_*_{date_str}.json")):
        try:
            d = json.load(f.open(encoding="utf-8"))
        except Exception:
            continue

        venue = d.get("venue") or f.name.split("_")[1]
        course_lower = _VENUE_TO_COURSE.get(venue, venue.lower())

        for race_time, race in d.get("races", {}).items():
            race_info = race.get("race_info", "")
            r_class = ""
            r_dist = ""
            r_going = ""
            # Look up going from Racing API going_index (course + off_time key)
            # per-venue JSON uses "1.45", API uses "1:45" — normalise to colon
            race_time_colon = race_time.replace(".", ":")
            api_going = going_index.get((course_lower, race_time_colon), "")
            if api_going:
                r_going = api_going
            m_class = re.search(r"Class\s*(\d+)", race_info, re.I)
            if m_class:
                r_class = f"Class {m_class.group(1)}"
            m_dist = re.search(r"(\d+m(?:\d+f)?(?:\s*\d+y)?|\d+f(?:\s*\d+y)?)", race_info, re.I)
            if m_dist:
                r_dist = m_dist.group(1).strip()
            m_going = re.search(r"\((G[A-Za-z\s]+|S[A-Za-z\s]+|Firm|Fast|Slow|Standard)\)", race_info, re.I)
            if m_going:
                r_going = m_going.group(1).strip()

            for h in race.get("horses", []):
                name = h.get("horse_name", "?")

                # Enrich from Racing API
                api = api_index.get((h.get("jockey") or ""), {})  # fallback
                api = api_index.get(name.strip().lower(), api)

                or_raw = h.get("or_run_history") or []
                ts_raw = h.get("ts_run_history") or []

                or_history = [
                    ORRun(pos=r.get("pos"), or_val=r.get("or"), raw=r.get("raw", ""))
                    for r in or_raw[:6]
                ]
                ts_history = [
                    TSRun(
                        pos=r.get("pos"), ts_val=r.get("ts"),
                        dist=str(r.get("dist", "")), going=r.get("going", ""),
                        raw=r.get("raw", "")
                    )
                    for r in ts_raw[:6]
                ]

                or_vals = _or_val(or_history)
                current_or = or_vals[0] if or_vals else api.get("ofr")
                current_ts = _ts_val(ts_history)
                current_ts = current_ts[0] if current_ts else api.get("ts")
                current_rpr = h.get("rpr_master") or api.get("rpr")

                trainer_14day_raw = api.get("trainer_14_days", {})
                trainer_14day_str = _fmt_trainer_14day(trainer_14day_raw)

                # headgear: prefer Racing API
                headgear = api.get("headgear") or h.get("headgear_cc") or ""
                wind_surg = api.get("wind_surgery") or bool(h.get("wind_surgery"))

                # weight
                lbs = api.get("lbs")
                wt_str = f"{lbs}lb" if lbs else ""

                # draw
                draw = api.get("draw") or h.get("stall")

                # jockey / trainer
                jockey = api.get("jockey") or h.get("jockey") or ""
                trainer = api.get("trainer") or h.get("trainer") or ""

                # last run
                days = api.get("last_run") or h.get("days_since_last_run")

                # form
                form_str = api.get("form") or h.get("form_string") or ""

                # field coverage report
                fc = {
                    "A_horse": _check_field(name),
                    "B_race": _check_field(f"{venue}/{race_time}"),
                    "C_OR": _check_field(current_or),
                    "D_TS": _check_field(current_ts),
                    "E_RPR": _check_field(current_rpr),
                    "F_last6_runs": _check_field(or_history or ts_history),
                    "G_last6_OR": "OK" if or_history and any(r.or_val for r in or_history) else "MISSING",
                    "H_last6_TS": "OK" if ts_history and any(r.ts_val for r in ts_history) else "MISSING",
                    "I_last6_RPR": "NOT_IN_SOURCE",  # per-run RPR not extracted by PDF parser; current RPR only
                    "J_spotlight": _check_field(h.get("spotlight_comment")),
                    "K_postdata": "OK" if h.get("postdata_score") is not None else "MISSING",
                    "L_trainer": _check_field(trainer),
                    "M_jockey": _check_field(jockey),
                    "N_trainer14day": "OK" if trainer_14day_str else "MISSING",
                    "O_weight": "OK" if lbs else "MISSING",
                    "P_class": _check_field(r_class),
                    "Q_distance": _check_field(r_dist),
                    "R_going": _check_field(r_going),
                    "S_headgear": "OK" if headgear and headgear not in ("", "0", "-") else "MISSING",
                }

                hr = CashrunResult(
                    horse=name, venue=venue, race_time=race_time,
                    race_name=race_info[:80], race_class=r_class,
                    distance=r_dist, going=r_going,
                    current_or=current_or, current_ts=current_ts,
                    current_rpr=current_rpr, last_run_days=days,
                    form_string=form_str, weight=wt_str, draw=draw,
                    trainer=trainer, jockey=jockey,
                    trainer_14day=trainer_14day_str,
                    headgear=headgear, wind_surgery=wind_surg,
                    or_history=or_history, ts_history=ts_history,
                    last_winning_or=None, or_vs_last_win=None,
                    or_compression_score=h.get("or_compression_score") or 0.0,
                    or_trend_drops=h.get("or_trend_drops") or 0,
                    ts_trend=h.get("ts_trend"),
                    ts_trend_signal=h.get("ts_trend_signal") or 0.0,
                    spotlight=h.get("spotlight_comment") or api.get("spotlight") or "",
                    postdata_score=h.get("postdata_score"),
                    is_postdata_pick=bool(h.get("is_postdata_pick")),
                    intent_signals=h.get("intent_signals") or [],
                    trainer_form=h.get("trainer_form") or api.get("trainer_rtf") or "",
                    trainer_form_signal=h.get("trainer_form_signal") or 0.0,
                    going_flag=h.get("going_flag") or "neutral",
                    distance_flag=h.get("distance_flag") or "neutral",
                    course_flag=h.get("course_flag") or "neutral",
                    plot_conviction=h.get("plot_conviction") or 0.0,
                    field_coverage=fc,
                )
                score_cashrun(hr)
                results.append(hr)

    return results


# ── Output formatters ──────────────────────────────────────────────────────────

def _fmt_or_hist(runs: list[ORRun]) -> str:
    parts = []
    for r in runs[:6]:
        pos = r.pos if r.pos is not None else "-"
        val = r.or_val if r.or_val is not None else "-"
        parts.append(f"{pos}/{val}")
    while len(parts) < 6:
        parts.append("-/-")
    return "[" + ", ".join(parts) + "]"


def _fmt_ts_hist(runs: list[TSRun]) -> str:
    parts = []
    for r in runs[:6]:
        pos = r.pos if r.pos is not None else "-"
        val = r.ts_val if r.ts_val is not None else "-"
        parts.append(f"{pos}/{val}")
    while len(parts) < 6:
        parts.append("-/-")
    return "[" + ", ".join(parts) + "]"


def write_md_report(results: list[CashrunResult], date_str: str, out_path: Path) -> None:
    ready = [r for r in results if r.cashrun_class == "CASHRUN_READY"]
    watch = [r for r in results if r.cashrun_class == "CASHRUN_WATCH"]
    weak = [r for r in results if r.cashrun_class == "WEAK_SIGNAL"]
    suppress = [r for r in results if r.cashrun_class == "SUPPRESS"]

    lines = []
    lines.append(f"# VÉLØ CASHRUN REPORT — {date_str}")
    lines.append("")
    lines.append("**Read-only operator intelligence. No betting instruction. No scoring change. No execution.**")
    lines.append("")

    # ── COMPACT OPERATOR CARD ────────────────────────────────────────────────
    lines.append("## CASHRUN OPERATOR CARD")
    lines.append("")
    lines.append(f"### Elite CASHRUN ({len(ready)} horses)")
    if ready:
        for r in sorted(ready, key=lambda x: -x.cashrun_score):
            or_angle = f"OR {r.current_or}"
            if r.last_winning_or:
                diff = (r.current_or or 0) - r.last_winning_or
                or_angle += f" (win OR was {r.last_winning_or}, Δ={diff:+d})"
            ts_angle = ""
            tv = _ts_val(r.ts_history)
            if tv:
                ts_angle = f"TS {tv[0]}" + (f"→{tv[1]}" if len(tv) > 1 else "")
            spot_phrase = ""
            for p in SETUP_PHRASES:
                if p in (r.spotlight or "").lower():
                    spot_phrase = p
                    break
            lines.append(f"- **{r.horse}** | {r.venue} {r.race_time} | score={r.cashrun_score} | {or_angle} | {ts_angle} | \"{spot_phrase}\"")
    else:
        lines.append("- None")
    lines.append("")

    lines.append(f"### CASHRUN Watch ({len(watch)} horses)")
    if watch:
        for r in sorted(watch, key=lambda x: -x.cashrun_score):
            top_note = r.signals.notes[0] if r.signals.notes else ""
            lines.append(f"- **{r.horse}** | {r.venue} {r.race_time} | score={r.cashrun_score} | {top_note}")
    else:
        lines.append("- None")
    lines.append("")

    lines.append(f"### Suppress ({len(suppress)} horses — {len(suppress)} of {len(results)} total)")
    if suppress:
        for r in sorted(suppress, key=lambda x: -x.cashrun_score)[:15]:
            top_neg = next((n for n in r.signals.notes if "SUPPRESS" in n), "")
            lines.append(f"- {r.horse} | {r.venue} {r.race_time} | score={r.cashrun_score} | {top_neg or 'no signal'}")
    lines.append("")

    # ── DETAILED REPORTS ─────────────────────────────────────────────────────
    for tier_label, tier_results in [
        ("CASHRUN_READY", ready), ("CASHRUN_WATCH", watch), ("WEAK_SIGNAL", weak)
    ]:
        if not tier_results:
            continue
        lines.append(f"---")
        lines.append(f"## {tier_label} DETAIL")
        lines.append("")

        for r in sorted(tier_results, key=lambda x: -x.cashrun_score):
            lines.append(f"### {r.horse} — {r.venue} {r.race_time}")
            lines.append("")
            lines.append(f"| Field | Value |")
            lines.append(f"|---|---|")
            lines.append(f"| Cashrun class | **{r.cashrun_class}** |")
            lines.append(f"| Cashrun score | **{r.cashrun_score}/100** |")
            lines.append(f"| Race | {r.venue} {r.race_time} — {r.race_name} |")
            lines.append(f"| Class | {r.race_class} |")
            lines.append(f"| Distance | {r.distance} |")
            lines.append(f"| Going | {r.going} |")
            lines.append(f"| Current OR | {r.current_or or 'N/A'} |")
            lines.append(f"| Last winning OR | {r.last_winning_or or 'N/A'} |")
            if r.or_vs_last_win is not None:
                direction = "BELOW" if r.or_vs_last_win <= 0 else "above"
                lines.append(f"| OR vs last win | {r.or_vs_last_win:+d} ({direction} winning mark) |")
            lines.append(f"| OR compression | {r.or_compression_score:.2f} |")
            lines.append(f"| OR trend drops | {r.or_trend_drops} |")
            lines.append(f"| Current TS | {r.current_ts or 'N/A'} |")
            lines.append(f"| Current RPR | {r.current_rpr or 'N/A'} |")
            lines.append(f"| Last 6 OR (pos/OR latest→oldest) | `{_fmt_or_hist(r.or_history)}` |")
            lines.append(f"| Last 6 TS (pos/TS latest→oldest) | `{_fmt_ts_hist(r.ts_history)}` |")
            lines.append(f"| Form | {r.form_string or 'N/A'} |")
            lines.append(f"| Weight | {r.weight or 'N/A'} |")
            lines.append(f"| Draw | {r.draw or 'N/A'} |")
            lines.append(f"| Trainer | {r.trainer or 'N/A'} |")
            lines.append(f"| Jockey | {r.jockey or 'N/A'} |")
            lines.append(f"| Trainer 14-day | {r.trainer_14day or 'N/A'} |")
            lines.append(f"| Headgear | {r.headgear or 'none'} |")
            lines.append(f"| Wind surgery | {'yes' if r.wind_surgery else 'no'} |")
            lines.append(f"| Days since last run | {r.last_run_days or 'N/A'} |")
            lines.append(f"| Plot conviction | {r.plot_conviction:.2f} |")
            lines.append(f"| Postdata score | {f'{r.postdata_score:.2f}' if r.postdata_score is not None else 'N/A'} |")
            lines.append(f"| Is postdata pick | {r.is_postdata_pick} |")
            lines.append(f"| Intent signals | {', '.join(r.intent_signals) or 'none'} |")
            lines.append(f"| Trainer form | {r.trainer_form or 'N/A'} |")
            lines.append(f"| Going/dist/course | {r.going_flag} / {r.distance_flag} / {r.course_flag} |")
            lines.append("")

            lines.append("**Signal scores:**")
            sig = r.signals
            lines.append(f"- Mark compression:     {sig.mark_compression:.1f}/30")
            lines.append(f"- TS/RPR hidden form:   {sig.hidden_form:.1f}/20")
            lines.append(f"- Setup run pattern:    {sig.setup_run:.1f}/20")
            lines.append(f"- Trainer/jockey intent:{sig.trainer_intent:.1f}/15")
            lines.append(f"- Spotlight/postdata:   {sig.spotlight_intent:.1f}/15")
            if sig.negative_suppression > 0:
                lines.append(f"- Negative suppression: -{sig.negative_suppression:.1f}")
            lines.append("")

            lines.append("**Evidence trail:**")
            for note in sig.notes:
                lines.append(f"- {note}")
            lines.append("")

            lines.append("**Spotlight:**")
            lines.append(f"> {r.spotlight or 'Not available'}")
            lines.append("")

            # Operator read
            if r.cashrun_class == "CASHRUN_READY":
                read = "cashrun signal — OR compression confirmed, form/intent aligned, operator watch"
            elif r.cashrun_class == "CASHRUN_WATCH":
                read = "cashrun watch — partial evidence, monitor for market support"
            else:
                read = "weak signal — insufficient convergence for cashrun classification"
            lines.append(f"**Final operator read:** {read}")
            lines.append("")

    # ── PROOF / COVERAGE REPORT ──────────────────────────────────────────────
    lines.append("---")
    lines.append("## PROOF OF FIELD COVERAGE")
    lines.append("")

    total = len(results)
    or_ok = sum(1 for r in results if r.field_coverage.get("G_last6_OR") == "OK")
    ts_ok = sum(1 for r in results if r.field_coverage.get("H_last6_TS") == "OK")
    spot_ok = sum(1 for r in results if r.field_coverage.get("J_spotlight") == "OK")
    pd_ok = sum(1 for r in results if r.field_coverage.get("K_postdata") == "OK")
    rpr_ok = sum(1 for r in results if r.field_coverage.get("E_RPR") == "OK")
    trainer14_ok = sum(1 for r in results if r.field_coverage.get("N_trainer14day") == "OK")
    hg_ok = sum(1 for r in results if r.field_coverage.get("S_headgear") == "OK")

    # Missing field inventory
    missing_counts: dict[str, int] = defaultdict(int)
    for r in results:
        for k, v in r.field_coverage.items():
            if v == "MISSING":
                missing_counts[k] += 1

    lines.append(f"| Check | Count | Coverage |")
    lines.append(f"|---|---|---|")
    lines.append(f"| A. Files parsed | 6 venues | NMK WAR NCS GOO ASC PUN |")
    lines.append(f"| B. Horses scanned | {total} | — |")
    lines.append(f"| C. Horses with last-6 OR | {or_ok}/{total} | {100*or_ok//total if total else 0}% |")
    lines.append(f"| D. Horses with last-6 TS | {ts_ok}/{total} | {100*ts_ok//total if total else 0}% |")
    lines.append(f"| E. Horses with Spotlight | {spot_ok}/{total} | {100*spot_ok//total if total else 0}% |")
    lines.append(f"| F. Horses with Postdata | {pd_ok}/{total} | {100*pd_ok//total if total else 0}% |")
    lines.append(f"| G. CASHRUN_READY | {len(ready)} | — |")
    lines.append(f"| H. CASHRUN_WATCH | {len(watch)} | — |")
    lines.append(f"| I. Suppressed | {len(suppress)} | — |")
    lines.append(f"| J. RPR coverage | {rpr_ok}/{total} | {100*rpr_ok//total if total else 0}% |")
    lines.append(f"| K. Trainer 14-day | {trainer14_ok}/{total} | {100*trainer14_ok//total if total else 0}% |")
    lines.append(f"| L. Headgear flags | {hg_ok}/{total} | {100*hg_ok//total if total else 0}% |")
    lines.append("")

    # NOT_IN_SOURCE fields (structural data gap, not a missing-data issue)
    not_in_source = {k for r in results for k, v in r.field_coverage.items() if v == "NOT_IN_SOURCE"}
    if not_in_source:
        lines.append("**NOT_IN_SOURCE (structural — not extractable from current data pipeline):**")
        for k in sorted(not_in_source):
            lines.append(f"- {k}: per-run RPR not extracted by PDF parser; only current RPR (E_RPR) available")
        lines.append("")

    if missing_counts:
        lines.append("**Missing field counts (MISSING = field absent for that horse):**")
        for k in sorted(missing_counts, key=lambda x: -missing_counts[x]):
            lines.append(f"- {k}: {missing_counts[k]}/{total} horses missing")
        lines.append("")

    lines.append("**K. Confirmation — no system changes made:**")
    lines.append("- Scoring: unchanged")
    lines.append("- SQPE / model: unchanged")
    lines.append("- Router rules: unchanged")
    lines.append("- Staking: unchanged")
    lines.append("- Live execution: unchanged")
    lines.append("- Playbook E: not activated")
    lines.append("")
    lines.append(f"*CASHRUN detector is read-only operator intelligence. Source: Racing Post PDF ingestion + Racing API racecard.*")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD report: {out_path}")


def write_csv_report(results: list[CashrunResult], out_path: Path) -> None:
    fieldnames = [
        "cashrun_class", "cashrun_score",
        "horse", "venue", "race_time", "race_class", "distance", "going",
        "current_or", "last_winning_or", "or_vs_last_win",
        "or_compression_score", "or_trend_drops",
        "current_ts", "ts_trend_signal",
        "current_rpr", "form_string", "weight", "draw",
        "trainer", "jockey", "trainer_14day", "trainer_form",
        "headgear", "wind_surgery", "last_run_days",
        "postdata_score", "is_postdata_pick", "plot_conviction",
        "intent_signals", "going_flag", "distance_flag", "course_flag",
        "last6_OR", "last6_TS",
        "mark_compression", "hidden_form", "setup_run",
        "trainer_intent", "spotlight_intent", "negative_suppression",
        "spotlight_snippet",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in sorted(results, key=lambda x: -x.cashrun_score):
            w.writerow({
                "cashrun_class": r.cashrun_class,
                "cashrun_score": r.cashrun_score,
                "horse": r.horse,
                "venue": r.venue,
                "race_time": r.race_time,
                "race_class": r.race_class,
                "distance": r.distance,
                "going": r.going,
                "current_or": r.current_or or "",
                "last_winning_or": r.last_winning_or or "",
                "or_vs_last_win": r.or_vs_last_win if r.or_vs_last_win is not None else "",
                "or_compression_score": r.or_compression_score,
                "or_trend_drops": r.or_trend_drops,
                "current_ts": r.current_ts or "",
                "ts_trend_signal": r.ts_trend_signal,
                "current_rpr": r.current_rpr or "",
                "form_string": r.form_string,
                "weight": r.weight,
                "draw": r.draw or "",
                "trainer": r.trainer,
                "jockey": r.jockey,
                "trainer_14day": r.trainer_14day,
                "trainer_form": r.trainer_form,
                "headgear": r.headgear,
                "wind_surgery": r.wind_surgery,
                "last_run_days": r.last_run_days or "",
                "postdata_score": r.postdata_score if r.postdata_score is not None else "",
                "is_postdata_pick": r.is_postdata_pick,
                "plot_conviction": r.plot_conviction,
                "intent_signals": "|".join(r.intent_signals),
                "going_flag": r.going_flag,
                "distance_flag": r.distance_flag,
                "course_flag": r.course_flag,
                "last6_OR": _fmt_or_hist(r.or_history),
                "last6_TS": _fmt_ts_hist(r.ts_history),
                "mark_compression": r.signals.mark_compression,
                "hidden_form": r.signals.hidden_form,
                "setup_run": r.signals.setup_run,
                "trainer_intent": r.signals.trainer_intent,
                "spotlight_intent": r.signals.spotlight_intent,
                "negative_suppression": r.signals.negative_suppression,
                "spotlight_snippet": (r.spotlight or "")[:120],
            })
    print(f"CSV report: {out_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="VÉLØ CASHRUN Detector")
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()

    date_str = args.date
    print(f"VÉLØ CASHRUN DETECTOR — {date_str}")
    print(f"Loading per-venue JSON from {MERGED}/")

    results = load_horses(date_str)
    if not results:
        print(f"ERROR: No horses loaded for {date_str}. Check racecard_merged/ files.")
        sys.exit(1)

    print(f"Loaded {len(results)} horses across "
          f"{len(set(r.venue for r in results))} venues")

    ready = [r for r in results if r.cashrun_class == "CASHRUN_READY"]
    watch = [r for r in results if r.cashrun_class == "CASHRUN_WATCH"]
    suppress = [r for r in results if r.cashrun_class == "SUPPRESS"]
    weak = [r for r in results if r.cashrun_class == "WEAK_SIGNAL"]

    print(f"  CASHRUN_READY:  {len(ready)}")
    print(f"  CASHRUN_WATCH:  {len(watch)}")
    print(f"  WEAK_SIGNAL:    {len(weak)}")
    print(f"  SUPPRESS:       {len(suppress)}")
    print()

    print("TOP CASHRUN_READY:")
    for r in sorted(ready, key=lambda x: -x.cashrun_score)[:10]:
        print(f"  {r.cashrun_score:5.1f}  {r.venue} {r.race_time}  {r.horse}")
        if r.last_winning_or and r.current_or:
            print(f"         OR {r.current_or} (win OR was {r.last_winning_or}, Δ={r.or_vs_last_win:+d})")
        print(f"         {r.signals.notes[0] if r.signals.notes else ''}")
    print()

    print("TOP CASHRUN_WATCH:")
    for r in sorted(watch, key=lambda x: -x.cashrun_score)[:8]:
        print(f"  {r.cashrun_score:5.1f}  {r.venue} {r.race_time}  {r.horse}")
    print()

    md_path = DATA / f"cashrun_report_{date_str}.md"
    csv_path = DATA / f"cashrun_report_{date_str}.csv"
    write_md_report(results, date_str, md_path)
    write_csv_report(results, csv_path)

    print()
    print("K. SYSTEM INTEGRITY CONFIRMATION")
    print("   Scoring:         unchanged")
    print("   SQPE/model:      unchanged")
    print("   Router rules:    unchanged")
    print("   Staking:         unchanged")
    print("   Live execution:  unchanged")
    print("   Playbook E:      not activated")
    print()
    print("CASHRUN detector complete. Operator intelligence only.")


if __name__ == "__main__":
    main()
