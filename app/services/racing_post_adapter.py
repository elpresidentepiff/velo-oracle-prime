"""
RacingPostAdapter V1 — read-only structured feature extractor.

Reads merged racecard JSONs produced by ingest_racecard_pdfs.py and outputs
structured features consumed by convergence, CASHRUN, learning, and dashboard.
No scoring integration. No DB writes. Local artifact only.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RACECARD_DIR = ROOT / "data" / "racecard_merged"
OUTPUT_DIR = ROOT / "data" / "racing_post_features"

# Claim phrase catalogue → structured claim tags
_CLAIM_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"well handicapp", re.I), "HANDICAP_CLAIM"),
    (re.compile(r"(good|workable|below.+winning|dropped in weights)", re.I), "HANDICAP_CLAIM"),
    (re.compile(r"(should improve|open to improvement|unexposed|scope for improvement)", re.I), "PROGRESSION_CLAIM"),
    (re.compile(r"(stable fancy|yard in form|trainer in form|off a mark)", re.I), "TRAINER_INTENT_CLAIM"),
    (re.compile(r"(laid out for|laid up for|been freshened|given time)", re.I), "TRAINER_INTENT_CLAIM"),
    (re.compile(r"(ground will suit|handles the going|in his element|conditions suit)", re.I), "GROUND_CLAIM"),
    (re.compile(r"(market support|market confidence|punters know|money likely|heavily backed)", re.I), "MARKET_CLAIM"),
    (re.compile(r"(return to form|bounce.?back|better than bare|eyecatcher|not knocked about)", re.I), "FORM_REVERSAL_CLAIM"),
    (re.compile(r"(return to course|course winner|course specialist|loves this track)", re.I), "COURSE_CLAIM"),
    (re.compile(r"(return to trip|return to distance|suited by this trip)", re.I), "TRIP_CLAIM"),
    (re.compile(r"(others preferred|hard to recommend|needs to raise|opposable|up against it)", re.I), "NEGATIVE_CLAIM"),
    (re.compile(r"(well beaten|out of sorts|no appeal|lacks the pace)", re.I), "NEGATIVE_CLAIM"),
]

# Consensus signal: flag is present in N sources → signal fires
_FLAG_SOURCES = ["going_flag", "distance_flag", "course_flag", "draw_flag", "ability_flag"]


def _extract_claim_tags(text: str) -> list[str]:
    if not text:
        return []
    tags: list[str] = []
    for pattern, tag in _CLAIM_MAP:
        if pattern.search(text) and tag not in tags:
            tags.append(tag)
    return tags


def _norm_time(raw: str) -> str:
    s = str(raw or "").strip().replace(".", ":").replace(" ", "")
    if re.match(r"^\d:\d{2}$", s):
        return s
    if re.match(r"^\d{1,2}\.\d{2}$", str(raw or "")):
        parts = str(raw).split(".")
        return f"{parts[0]}:{parts[1]}"
    return s


def _or_trend(history: list[dict]) -> str:
    ors = [e.get("or") for e in (history or []) if e.get("or")]
    if len(ors) < 2:
        return "INSUFFICIENT"
    if ors[-1] > ors[0]:
        return "RISING"
    if ors[-1] < ors[0]:
        return "FALLING"
    return "FLAT"


def _ts_trend(history: list[dict]) -> str:
    scores = [e.get("ts") for e in (history or []) if e.get("ts")]
    if len(scores) < 2:
        return "INSUFFICIENT"
    recent = scores[-3:] if len(scores) >= 3 else scores
    baseline = scores[:-3] if len(scores) > 3 else scores[:1]
    if not baseline:
        return "INSUFFICIENT"
    return "IMPROVING" if sum(recent) / len(recent) > sum(baseline) / len(baseline) else "FLAT_OR_DECLINING"


def _consensus_signals(horse: dict, race_postdata_pick: str, race_topspeed_pick: str) -> list[str]:
    signals: list[str] = []
    name = (horse.get("horse_name") or "").upper()
    # Flags from RP parsers
    for flag in _FLAG_SOURCES:
        val = str(horse.get(flag) or "").lower()
        if "positive" in val or "strong" in val:
            signals.append(f"FLAG:{flag.replace('_flag','').upper()}_POSITIVE")
    # Postdata/topspeed agreement
    if name and race_postdata_pick and name in race_postdata_pick.upper():
        signals.append("RP_POSTDATA_PICK")
    if name and race_topspeed_pick and name in race_topspeed_pick.upper():
        signals.append("RP_TOPSPEED_PICK")
    return signals


def _rating_ranks(horses: list[dict]) -> dict[str, int]:
    """Return {horse_name: rank} by current_or descending."""
    scored = [(h.get("horse_name", ""), h.get("current_or") or 0) for h in horses]
    scored.sort(key=lambda x: -x[1])
    return {name: idx + 1 for idx, (name, _) in enumerate(scored) if name}


def extract_race_features(venue: str, race_time: str, race: dict) -> dict[str, Any]:
    race_info = race.get("race_info", "")
    postdata_pick = race.get("postdata_pick", "") or ""
    topspeed_pick = race.get("topspeed_pick", "") or ""
    spotlight_verdict = race.get("spotlight_verdict", "") or ""
    horses = race.get("horses", [])

    rating_ranks = _rating_ranks(horses)

    runner_features: list[dict] = []
    all_claim_tags: list[str] = []

    for h in horses:
        name = h.get("horse_name", "")
        spotlight = h.get("spotlight_comment", "") or ""
        claim_tags = _extract_claim_tags(spotlight)
        all_claim_tags.extend(claim_tags)
        consensus = _consensus_signals(h, postdata_pick, topspeed_pick)

        runner_features.append({
            "horse": name,
            "or_rank": rating_ranks.get(name),
            "current_or": h.get("current_or"),
            "current_ts": h.get("ts_master") or h.get("ts_latest"),
            "current_rpr": h.get("rpr_master"),
            "or_trend": _or_trend(h.get("or_run_history", [])),
            "ts_trend": _ts_trend(h.get("ts_run_history", [])),
            "or_compression": h.get("or_compression") or 0,
            "going_flag": h.get("going_flag"),
            "distance_flag": h.get("distance_flag"),
            "course_flag": h.get("course_flag"),
            "draw_flag": h.get("draw_flag"),
            "ability_flag": h.get("ability_flag"),
            "trainer_form": h.get("trainer_form"),
            "trainer_form_signal": h.get("trainer_form_signal"),
            "plot_conviction": h.get("plot_conviction"),
            "handicap_plot_score": h.get("handicap_plot_score"),
            "stall": h.get("stall"),
            "days_since_last_run": h.get("days_since_last_run"),
            "headgear": h.get("headgear_cc"),
            "spotlight_comment": spotlight,
            "claim_tags": claim_tags,
            "consensus_signals": consensus,
            "postdata_pick": bool(name and postdata_pick and name.upper() in postdata_pick.upper()),
            "topspeed_pick": bool(name and topspeed_pick and name.upper() in topspeed_pick.upper()),
        })

    # Race-level consensus: which horses appear in ≥2 RP sources
    from collections import Counter
    all_sources: list[str] = []
    if postdata_pick:
        all_sources.append(postdata_pick.upper())
    if topspeed_pick:
        all_sources.append(topspeed_pick.upper())

    claim_freq = Counter(all_claim_tags)
    top_claims = [tag for tag, _ in claim_freq.most_common(5)]

    return {
        "venue": venue,
        "off_time": _norm_time(race_time),
        "race_info": race_info,
        "postdata_pick": postdata_pick,
        "topspeed_pick": topspeed_pick,
        "spotlight_verdict": spotlight_verdict,
        "runner_count": len(horses),
        "rp_race_features": {
            "has_postdata": bool(postdata_pick),
            "has_topspeed": bool(topspeed_pick),
            "has_spotlight": bool(spotlight_verdict),
            "top_claim_tags": top_claims,
        },
        "rp_rating_ranks": rating_ranks,
        "rp_runner_features": runner_features,
    }


def build_racing_post_features(date: str) -> dict[str, Any]:
    races_out: list[dict] = []
    coverage = {"venues": 0, "races": 0, "runners": 0, "spotlight_present": 0, "postdata_present": 0}

    for path in sorted(RACECARD_DIR.glob(f"racecard_*_{date}.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        venue = card.get("venue", path.stem.split("_")[1])
        races = card.get("races", {})
        if not isinstance(races, dict):
            continue
        coverage["venues"] += 1
        for race_time, race in races.items():
            features = extract_race_features(venue, race_time, race)
            races_out.append(features)
            coverage["races"] += 1
            coverage["runners"] += features["runner_count"]
            if features["rp_race_features"]["has_spotlight"]:
                coverage["spotlight_present"] += 1
            if features["rp_race_features"]["has_postdata"]:
                coverage["postdata_present"] += 1

    payload = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": coverage,
        "races": races_out,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{date}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
