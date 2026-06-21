"""
Deep Race Agent V1 - paper-only analyst layer.

Consumes the Tri-Lane agent review board and enriches each review card with
local racing evidence found on the operator laptop:

  - BHA-style ratings CSV
  - Performance figures CSV
  - Historical raceform CSV, scoped only to reviewed horses
  - Downloaded race PDF pack inventory

This script does not score live races, stake, notify, or write live tables.
It writes a structured JSON report and a copy-paste markdown report.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REPORT_DIR = DATA_DIR / "reports"
DEFAULT_DOWNLOADS = Path.home() / "Downloads"
NON_UK_IRE_COURSES = {
    "happyvalley",
    "saratoga",
    "sansiro",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(date: str) -> str:
    return date.replace("-", "_")


def _norm(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _norm_horse(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+\(([A-Z]{2,4})\)\s*$", "", text, flags=re.IGNORECASE)
    return _norm(text)


def _norm_trainer(value: Any) -> str:
    text = str(value or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _infer_review_dates(cards: list[dict[str, Any]]) -> list[str]:
    dates = sorted({str(card.get("date") or "") for card in cards if card.get("date")})
    return [date for date in dates if re.match(r"^\d{4}-\d{2}-\d{2}$", date)]


def _load_live_identity(dates: list[str]) -> dict[str, Any]:
    """
    Load the RP merged racecards as the live identity spine.

    The laptop gold files are useful, but horse-name-only joins are dangerous.
    These racecards carry the actual runner identity for the day: horse_id,
    trainer, jockey, ratings and comments.
    """
    by_race_horse: dict[str, dict[str, Any]] = {}
    by_horse: dict[str, dict[str, Any]] = {}
    duplicate_horses: set[str] = set()
    files_loaded = 0
    runners_loaded = 0

    for date in dates:
        for path in (DATA_DIR / "racecard_merged").glob(f"*{date}*.json"):
            payload = _load_json(path, {})
            races = payload.get("races") if isinstance(payload, dict) else None
            if not isinstance(races, dict):
                continue
            files_loaded += 1
            venue = payload.get("venue")
            venue_code = payload.get("venue_code")
            for race_key, race in races.items():
                if not isinstance(race, dict):
                    continue
                race_id = str(race.get("race_id") or "")
                course = race.get("course") or venue
                off_time = race.get("off") or race.get("off_time") or race_key
                for runner in race.get("horses") or []:
                    if not isinstance(runner, dict):
                        continue
                    name = _first_present(runner, "horse_name", "horse", "name")
                    norm_name = _norm_horse(name)
                    if not norm_name:
                        continue
                    snapshot = {
                        "available": True,
                        "source_file": str(path),
                        "date": date,
                        "course": course,
                        "venue": venue,
                        "venue_code": venue_code,
                        "race_id": race_id,
                        "off_time": off_time,
                        "horse": name,
                        "horse_id": _first_present(runner, "horse_id", "rp_horse_id"),
                        "age": runner.get("age"),
                        "trainer": _first_present(runner, "trainer", "trainer_name"),
                        "trainer_name": _first_present(runner, "trainer_name", "trainer"),
                        "jockey": _first_present(runner, "jockey", "jockey_name"),
                        "jockey_name": _first_present(runner, "jockey_name", "jockey"),
                        "current_or": _first_present(runner, "current_or", "or", "official_rating"),
                        "rpr_master": runner.get("rpr_master"),
                        "ts_master": runner.get("ts_master"),
                        "days_since_last_run": runner.get("days_since_last_run"),
                        "form_figures": runner.get("form_figures"),
                        "spotlight_comment": runner.get("spotlight_comment"),
                        "diomed_comment": runner.get("diomed_comment"),
                        "newspaper_tip_count": runner.get("newspaper_tip_count"),
                        "postdata_score": runner.get("postdata_score"),
                        "or_compression_score": runner.get("or_compression_score"),
                        "plot_conviction": runner.get("plot_conviction"),
                    }
                    runners_loaded += 1
                    if race_id:
                        by_race_horse[f"{race_id}|{norm_name}"] = snapshot
                    horse_key = f"{date}|{norm_name}"
                    if horse_key in by_horse:
                        duplicate_horses.add(horse_key)
                    else:
                        by_horse[horse_key] = snapshot

    for horse_key in duplicate_horses:
        by_horse.pop(horse_key, None)

    return {
        "dates": dates,
        "files_loaded": files_loaded,
        "runners_loaded": runners_loaded,
        "duplicates_removed": len(duplicate_horses),
        "by_race_horse": by_race_horse,
        "by_horse": by_horse,
    }


def _live_identity_for(card: dict[str, Any], live_index: dict[str, Any]) -> dict[str, Any]:
    horse_key = _norm_horse(card.get("horse"))
    race_id = str(card.get("race_id") or "")
    date = str(card.get("date") or "")
    if race_id:
        match = live_index.get("by_race_horse", {}).get(f"{race_id}|{horse_key}")
        if match:
            return match
    return live_index.get("by_horse", {}).get(f"{date}|{horse_key}", {"available": False})


def _read_csv_lookup(path: Path, key_field: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = _norm_horse(row.get(key_field))
            if key:
                out[key] = row
    return out


def _pdf_inventory(downloads: Path) -> dict[str, Any]:
    pattern = re.compile(
        r"(?P<course>[A-Z]{3})_(?P<date>\d{8})_\d+_\d+_F_(?P<sheet>\d{4})_(?P<label>[A-Z]{2})_(?P<venue>.+)\.pdf$",
        re.IGNORECASE,
    )
    sheet_names = {
        "0010": "selection_box",
        "0011": "postdata_grid",
        "0012": "colour_racecard",
        "0015": "official_ratings",
        "0016": "spotlight_comments",
        "0032": "topspeed_ratings",
    }
    by_date_course: dict[str, dict[str, Any]] = defaultdict(dict)
    total = 0
    for path in downloads.rglob("*.pdf"):
        m = pattern.match(path.name)
        if not m:
            continue
        total += 1
        date_raw = m.group("date")
        date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
        course = m.group("course").upper()
        sheet = m.group("sheet")
        key = f"{date}:{course}"
        by_date_course[key][sheet_names.get(sheet, sheet)] = str(path)
    return {
        "downloads": str(downloads),
        "race_pdf_files": total,
        "race_pdf_sets": len(by_date_course),
        "by_date_course": dict(by_date_course),
    }


def _load_raceform_history(path: Path, horse_names: set[str], max_rows_per_horse: int = 8) -> dict[str, list[dict[str, Any]]]:
    if not path.exists() or not horse_names:
        return {}
    wanted = {_norm_horse(name) for name in horse_names if name}
    rows_by_horse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            horse = row.get("horse") or ""
            key = _norm_horse(horse)
            if key not in wanted:
                continue
            rows_by_horse[key].append(
                {
                    "date": row.get("date"),
                    "course": row.get("course"),
                    "race_type": row.get("type"),
                    "class": row.get("class"),
                    "dist": row.get("dist"),
                    "going": row.get("going"),
                    "ran": row.get("ran"),
                    "pos": row.get("pos"),
                    "draw": row.get("draw"),
                    "sp": row.get("sp"),
                    "jockey": row.get("jockey"),
                    "trainer": row.get("trainer"),
                    "or": row.get("or"),
                    "rpr": row.get("rpr"),
                    "ts": row.get("ts"),
                    "comment": row.get("comment"),
                }
            )
    out: dict[str, list[dict[str, Any]]] = {}
    for key, rows in rows_by_horse.items():
        rows.sort(key=lambda r: str(r.get("date") or ""), reverse=True)
        out[key] = rows[:max_rows_per_horse]
    return out


def _rating_snapshot(ratings: dict[str, dict[str, Any]], horse: str) -> dict[str, Any]:
    row = ratings.get(_norm_horse(horse)) or {}
    if not row:
        return {"available": False}
    return {
        "available": True,
        "trainer": row.get("Trainer"),
        "flat_rating": row.get("Flat rating"),
        "diff_flat": row.get("Diff Flat"),
        "awt_rating": row.get("AWT rating"),
        "diff_awt": row.get("Diff AWT"),
        "chase_rating": row.get("Chase rating"),
        "diff_chase": row.get("Diff Chase"),
        "hurdle_rating": row.get("Hurdle rating"),
        "diff_hurdle": row.get("Diff Hurdle"),
    }


def _performance_snapshot(performance: dict[str, dict[str, Any]], horse: str) -> dict[str, Any]:
    row = performance.get(_norm_horse(horse)) or {}
    if not row:
        return {"available": False}
    values = [row.get(col) for col in ["Latest", "2 runs ago", "3 runs ago", "4 runs ago", "5 runs ago", "6 runs ago"]]
    numeric = []
    for value in values:
        m = re.search(r":(-?\d+)", str(value or ""))
        if m:
            numeric.append(int(m.group(1)))
    trend = None
    if len(numeric) >= 2:
        trend = numeric[0] - numeric[-1]
    return {
        "available": True,
        "trainer": row.get("Trainer"),
        "figures": values,
        "numeric_figures": numeric,
        "six_run_trend": trend,
    }


def _history_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {"available": False}
    wins = sum(1 for row in history if str(row.get("pos")) == "1")
    frames = sum(1 for row in history if str(row.get("pos")).isdigit() and int(str(row.get("pos"))) <= 3)
    recent_courses = [row.get("course") for row in history[:4] if row.get("course")]
    recent_comments = [row.get("comment") for row in history[:3] if row.get("comment")]
    return {
        "available": True,
        "runs_loaded": len(history),
        "recent_wins": wins,
        "recent_frames": frames,
        "recent_courses": recent_courses,
        "latest": history[0],
        "recent_comments": recent_comments,
    }


def _identity_lock(horse: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """
    Evidence confidence for local file joins.

    The same-day RP merged racecard is the live identity spine. Laptop gold can
    support or challenge that spine, but cannot overrule it by name alone.
    """
    live = evidence.get("live_identity") or {}
    rating = evidence.get("rating") or {}
    performance = evidence.get("performance") or {}
    history = evidence.get("history") or {}
    warnings: list[str] = []
    source_confidence: dict[str, str] = {}

    live_available = bool(live.get("available"))
    live_trainer = _norm_trainer(_first_present(live, "trainer", "trainer_name")) if live_available else ""
    rating_trainer = _norm_trainer(rating.get("trainer")) if rating.get("available") else ""
    performance_trainer = _norm_trainer(performance.get("trainer")) if performance.get("available") else ""
    latest = history.get("latest") if history.get("available") else None
    history_trainer = _norm_trainer((latest or {}).get("trainer")) if latest else ""

    for source, data in [("rating", rating), ("performance", performance), ("history", history)]:
        source_confidence[source] = "MISSING" if not data.get("available") else "NAME_ONLY"

    if live_available:
        for source, trainer in [("rating", rating_trainer), ("performance", performance_trainer)]:
            if source_confidence[source] == "MISSING":
                continue
            if trainer and live_trainer and trainer == live_trainer:
                source_confidence[source] = "EXACT"
            elif trainer and live_trainer and trainer != live_trainer:
                source_confidence[source] = "REJECTED"
                warnings.append(f"{source.upper()}_LIVE_TRAINER_MISMATCH")
            else:
                warnings.append(f"{source.upper()}_ATTACHED_BY_NAME_ONLY")

        if source_confidence["history"] != "MISSING":
            if history_trainer and live_trainer and history_trainer == live_trainer:
                source_confidence["history"] = "STRONG"
            elif history_trainer and live_trainer and history_trainer != live_trainer:
                source_confidence["history"] = "WEAK"
                warnings.append("HISTORY_TRAINER_DIFF_FROM_LIVE_CARD")
            else:
                warnings.append("HISTORY_ATTACHED_BY_NAME_ONLY")

        if any(conf == "EXACT" for conf in source_confidence.values()):
            overall = "LIVE_CONFIRMED"
        elif any(conf == "REJECTED" for conf in source_confidence.values()):
            overall = "LIVE_CONFLICT"
        elif any(conf in {"STRONG", "WEAK", "NAME_ONLY"} for conf in source_confidence.values()):
            overall = "LIVE_WEAK"
        else:
            overall = "LIVE_ONLY"

        return {
            "horse": horse,
            "overall_confidence": overall,
            "source_confidence": source_confidence,
            "live_identity": {
                "available": True,
                "horse_id": live.get("horse_id"),
                "trainer": _first_present(live, "trainer", "trainer_name"),
                "jockey": _first_present(live, "jockey", "jockey_name"),
                "age": live.get("age"),
                "source_file": live.get("source_file"),
            },
            "corroborated_trainers": [],
            "warnings": warnings,
            "rule": "RP merged racecard identity is the live spine; local files must match trainer to become exact.",
        }

    trainer_values = [v for v in [rating_trainer, performance_trainer, history_trainer] if v]
    trainer_counts = Counter(trainer_values)
    corroborated_trainers = {trainer for trainer, count in trainer_counts.items() if count >= 2}

    if rating_trainer and rating_trainer in corroborated_trainers:
        source_confidence["rating"] = "STRONG"
    if performance_trainer and performance_trainer in corroborated_trainers:
        source_confidence["performance"] = "STRONG"
    if history_trainer and history_trainer in corroborated_trainers:
        source_confidence["history"] = "STRONG"

    if len(set(trainer_values)) > 1 and not corroborated_trainers:
        warnings.append("LOCAL_EVIDENCE_TRAINER_CONFLICT")

    for source, confidence in source_confidence.items():
        if confidence == "NAME_ONLY":
            warnings.append(f"{source.upper()}_ATTACHED_BY_NAME_ONLY")

    if any(conf == "STRONG" for conf in source_confidence.values()):
        overall = "STRONG"
    elif any(conf == "NAME_ONLY" for conf in source_confidence.values()):
        overall = "NAME_ONLY"
    else:
        overall = "NO_LOCAL_IDENTITY_EVIDENCE"

    return {
        "horse": horse,
        "overall_confidence": overall,
        "source_confidence": source_confidence,
        "live_identity": {"available": False},
        "corroborated_trainers": sorted(corroborated_trainers),
        "warnings": warnings,
        "rule": "No exact identity unless live card carries trainer/age/sire/horse_id into agent card.",
    }


def _danger_from_new_build(card: dict[str, Any], selected: str) -> list[str]:
    danger: list[str] = []
    selected_norm = _norm_horse(selected)
    for lane_key in ("lane_a_top3", "lane_b_top3"):
        for horse in card.get(lane_key) or []:
            if _norm_horse(horse) != selected_norm and horse not in danger:
                danger.append(str(horse))
            if len(danger) >= 3:
                return danger
    return danger


def _agent_judgement(card: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    support = list(card.get("support") or [])
    risk = list(card.get("risk") or [])
    questions = list(card.get("agent_questions") or [])
    core = card.get("core_numbers") or {}
    new = card.get("new_build") or {}
    shadow = card.get("shadow") or {}
    state = card.get("horse_state") or {}
    tri_action = card.get("tri_action")

    support_score = len(support)
    risk_score = len(risk)
    vp = _float(core.get("vp"))
    mds = _float(core.get("mds"))
    frame_gate = _float(core.get("frame_gate_probability"))
    win_gate = _float(core.get("win_gate_probability"))
    passport = _float(core.get("passport_strength_score"))

    if evidence["rating"].get("available"):
        support_score += 1
    if evidence["performance"].get("available"):
        support_score += 1
        trend = evidence["performance"].get("six_run_trend")
        if trend is not None and trend < -10:
            risk_score += 1
            risk.append(f"PERFORMANCE_TREND_DOWN:{trend}")
        elif trend is not None and trend > 10:
            support_score += 1
            support.append(f"PERFORMANCE_TREND_UP:{trend}")
    if evidence["history"].get("available") and evidence["history"].get("recent_frames", 0) > 0:
        support_score += 1

    identity = evidence.get("identity") or {}
    identity_confidence = identity.get("overall_confidence")
    identity_warnings = list(identity.get("warnings") or [])
    if identity_confidence == "NAME_ONLY":
        risk_score += 1
        risk.append("LOCAL_EVIDENCE_NAME_ONLY")
    elif identity_confidence == "STRONG":
        support_score += 1
        support.append("LOCAL_EVIDENCE_STRONG_IDENTITY")
    elif identity_confidence == "LIVE_CONFIRMED":
        support_score += 2
        support.append("LOCAL_EVIDENCE_LIVE_CONFIRMED")
    elif identity_confidence == "LIVE_ONLY":
        support_score += 1
        support.append("LIVE_RACECARD_IDENTITY_ONLY")
    elif identity_confidence == "LIVE_WEAK":
        risk_score += 1
        risk.append("LOCAL_EVIDENCE_LIVE_WEAK")
    elif identity_confidence == "LIVE_CONFLICT":
        risk_score += 3
        risk.append("LOCAL_EVIDENCE_LIVE_CONFLICT")
    if "LOCAL_EVIDENCE_TRAINER_CONFLICT" in identity_warnings:
        risk_score += 2
        risk.append("LOCAL_EVIDENCE_TRAINER_CONFLICT")

    if new.get("weak_data"):
        risk_score += 1
    if not new.get("old_in_lane_a_top3") and not new.get("old_in_lane_b_top3"):
        risk_score += 1
        risk.append("OLD_NOT_IN_NEW_BUILD_TOP3")
    if state.get("race_fit_state") == "weak":
        risk_score += 1
    if state.get("market_state") in {"quiet", "cold"}:
        risk_score += 1

    if tri_action == "TRI_CASH_RUN" and support_score >= risk_score:
        verdict = "CASH_RUN_REVIEW"
    elif tri_action == "TRI_WATCH" and support_score >= risk_score + 2:
        verdict = "UPGRADE_CANDIDATE_REVIEW"
    elif tri_action == "TRI_WATCH":
        verdict = "WATCH_ONLY"
    elif tri_action == "TRI_PASS" and support_score >= risk_score + 3 and (vp >= 0.40 or frame_gate >= 0.62):
        verdict = "PASS_WITH_SUPPORT_REVIEW"
    else:
        verdict = "NO_BET"

    why_wrong = []
    if new.get("weak_data"):
        why_wrong.append("New Build passport coverage is weak, so confirmation may be thin.")
    if not new.get("old_in_lane_a_top3") and not new.get("old_in_lane_b_top3"):
        why_wrong.append("Old Velo horse is not supported by New Build top-three lanes.")
    if mds < 0.08:
        why_wrong.append("MDS is low, so this may be obvious/flat rather than hidden value.")
    if vp >= 0.40 and win_gate < 0.58:
        why_wrong.append("Old Velo is confident but Shadow win gate is not strong.")
    if passport < 1.0:
        why_wrong.append("Passport strength is weak or missing.")
    if state.get("race_fit_state") == "weak":
        why_wrong.append("Horse-state race fit is weak.")
    if identity_confidence == "NAME_ONLY":
        why_wrong.append("Local ratings/history/performance evidence is attached by name only, not exact identity.")
    if identity_confidence == "LIVE_CONFLICT":
        why_wrong.append("Local rating/performance evidence conflicts with the live RP racecard trainer.")
    if identity_confidence == "LIVE_WEAK":
        why_wrong.append("Live RP racecard identifies the horse, but laptop evidence is thin or historical.")
    if "LOCAL_EVIDENCE_TRAINER_CONFLICT" in identity_warnings:
        why_wrong.append("Local evidence has trainer conflict; treat attached history as suspect.")
    if not why_wrong:
        why_wrong.append("Primary risk is normal racing variance; no major contradiction found.")

    return {
        "agent_verdict": verdict,
        "support_score": support_score,
        "risk_score": risk_score,
        "support": support,
        "risk": risk,
        "questions": questions,
        "danger_horses": _danger_from_new_build(new, card.get("horse") or ""),
        "why_velo_may_be_wrong": why_wrong,
        "recommended_use": {
            "CASH_RUN_REVIEW": "cash-run shortlist only; paper until Sigma confirms",
            "UPGRADE_CANDIDATE_REVIEW": "agent review candidate; do not promote automatically",
            "WATCH_ONLY": "watch / learning only",
            "PASS_WITH_SUPPORT_REVIEW": "do not bet; study contradiction after result",
            "NO_BET": "no bet / no acca",
        }.get(verdict, "paper only"),
        "key_numbers": {
            "vp": vp,
            "mds": mds,
            "frame_gate": frame_gate,
            "win_gate": win_gate,
            "passport_strength": passport,
            "shadow_action": shadow.get("action"),
            "tri_action": tri_action,
        },
        "identity_confidence": identity_confidence,
        "identity_warnings": identity_warnings,
    }


def build_report(
    review_path: Path,
    downloads: Path,
    include_raceform: bool = True,
    max_cards: int | None = None,
) -> dict[str, Any]:
    review = _load_json(review_path, {})
    raw_cards = list(review.get("review_cards") or [])
    excluded_cards = [
        card for card in raw_cards
        if _norm(card.get("course")) in NON_UK_IRE_COURSES
    ]
    cards = [
        card for card in raw_cards
        if _norm(card.get("course")) not in NON_UK_IRE_COURSES
    ]
    if max_cards:
        cards = cards[:max_cards]

    horses = {str(card.get("horse") or "") for card in cards if card.get("horse")}
    live_index = _load_live_identity(_infer_review_dates(cards))
    ratings = _read_csv_lookup(downloads / "ratings.csv", "Name")
    performance = _read_csv_lookup(downloads / "performance-figures.csv", "Racehorse")
    raceform_history = (
        _load_raceform_history(downloads / "raceform.csv", horses)
        if include_raceform
        else {}
    )
    pdfs = _pdf_inventory(downloads)

    agent_cards = []
    for card in cards:
        horse = str(card.get("horse") or "")
        evidence = {
            "live_identity": _live_identity_for(card, live_index),
            "rating": _rating_snapshot(ratings, horse),
            "performance": _performance_snapshot(performance, horse),
            "history": _history_summary(raceform_history.get(_norm_horse(horse), [])),
        }
        evidence["identity"] = _identity_lock(horse, evidence)
        judgement = _agent_judgement(card, evidence)
        agent_cards.append(
            {
                "date": card.get("date"),
                "race_id": card.get("race_id"),
                "off_time": card.get("off_time"),
                "course": card.get("course"),
                "race_name": card.get("race_name"),
                "horse": horse,
                "priority": card.get("priority"),
                "tri_action": card.get("tri_action"),
                "agent": judgement,
                "evidence": evidence,
                "new_build": card.get("new_build") or {},
                "horse_state": card.get("horse_state") or {},
            }
        )

    counts = Counter(card["agent"]["agent_verdict"] for card in agent_cards)
    identity_counts = Counter(
        (card.get("evidence") or {}).get("identity", {}).get("overall_confidence", "UNKNOWN")
        for card in agent_cards
    )
    return {
        "generated_at": _utc_now(),
        "status": "DEEP_RACE_AGENT_V1_PAPER_ONLY",
        "live_writes": False,
        "racing_api_used": False,
        "source_review": str(review_path),
        "downloads": str(downloads),
        "summary": {
            "cards": len(agent_cards),
            "raw_cards": len(raw_cards),
            "excluded_non_uk_ire_cards": len(excluded_cards),
            "excluded_non_uk_ire_courses": sorted({str(card.get("course")) for card in excluded_cards}),
            "agent_verdict_counts": dict(counts),
            "identity_confidence_counts": dict(identity_counts),
            "ratings_rows": len(ratings),
            "performance_rows": len(performance),
            "raceform_loaded": include_raceform,
            "race_pdf_files": pdfs["race_pdf_files"],
            "race_pdf_sets": pdfs["race_pdf_sets"],
            "live_identity_files_loaded": live_index["files_loaded"],
            "live_identity_runners_loaded": live_index["runners_loaded"],
            "live_identity_duplicates_removed": live_index["duplicates_removed"],
        },
        "pdf_inventory": {
            "race_pdf_files": pdfs["race_pdf_files"],
            "race_pdf_sets": pdfs["race_pdf_sets"],
        },
        "agent_cards": agent_cards,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Deep Race Agent V1",
        f"Generated: {report['generated_at']}",
        "",
        f"- Status: `{report['status']}`",
        f"- Live writes: `{report['live_writes']}`",
        f"- Racing API used: `{report['racing_api_used']}`",
        f"- Source review: `{report['source_review']}`",
        f"- Downloads: `{report['downloads']}`",
        "",
        "## Summary",
        f"- Cards: {report['summary']['cards']}",
        f"- Raw cards: {report['summary'].get('raw_cards', report['summary']['cards'])}",
        f"- Excluded non-UK/IRE cards: {report['summary'].get('excluded_non_uk_ire_cards', 0)}",
        f"- Ratings rows: {report['summary']['ratings_rows']}",
        f"- Performance rows: {report['summary']['performance_rows']}",
        f"- Raceform loaded: {report['summary']['raceform_loaded']}",
        f"- Race PDF files indexed: {report['summary']['race_pdf_files']}",
        f"- Race PDF sets indexed: {report['summary']['race_pdf_sets']}",
        f"- Live identity files loaded: {report['summary'].get('live_identity_files_loaded', 0)}",
        f"- Live identity runners loaded: {report['summary'].get('live_identity_runners_loaded', 0)}",
        "",
        "## Verdict Counts",
        "| Verdict | Count |",
        "|---|---:|",
    ]
    for verdict, count in sorted(report["summary"]["agent_verdict_counts"].items()):
        lines.append(f"| {verdict} | {count} |")

    lines.extend(["", "## Identity Confidence", "| Confidence | Count |", "|---|---:|"])
    for confidence, count in sorted(report["summary"].get("identity_confidence_counts", {}).items()):
        lines.append(f"| {confidence} | {count} |")

    lines.extend(["", "## Agent Cards"])
    for card in report["agent_cards"]:
        agent = card["agent"]
        evidence = card["evidence"]
        identity = evidence.get("identity") or {}
        live = evidence.get("live_identity") or {}
        nums = agent["key_numbers"]
        danger = ", ".join(agent.get("danger_horses") or []) or "-"
        latest = evidence["history"].get("latest") if evidence["history"].get("available") else None
        latest_line = "-"
        if latest:
            latest_line = (
                f"{latest.get('date')} {latest.get('course')} pos {latest.get('pos')} "
                f"SP {latest.get('sp')} OR {latest.get('or')} RPR {latest.get('rpr')} TS {latest.get('ts')}"
            )
        lines.extend(
            [
                "",
                f"### {card.get('off_time')} {card.get('course')} - {card.get('horse')}",
                f"- Race: {card.get('race_name')}",
                f"- Priority: `{card.get('priority')}` / Tri: `{card.get('tri_action')}`",
                f"- Agent verdict: `{agent['agent_verdict']}` ({agent['recommended_use']})",
                f"- Identity: `{identity.get('overall_confidence')}`; warnings: {', '.join(identity.get('warnings') or []) or '-'}",
                f"- Live card: horse_id `{live.get('horse_id') or '-'}`, trainer `{_first_present(live, 'trainer', 'trainer_name') or '-'}`, jockey `{_first_present(live, 'jockey', 'jockey_name') or '-'}`",
                f"- Numbers: VP {nums['vp']:.3f}, MDS {nums['mds']:.3f}, WIN {nums['win_gate']:.3f}, FRAME {nums['frame_gate']:.3f}, Passport {nums['passport_strength']:.2f}",
                f"- Support: {', '.join(agent['support']) or '-'}",
                f"- Risk: {', '.join(agent['risk']) or '-'}",
                f"- Danger horses: {danger}",
                f"- Latest history: {latest_line}",
                f"- Rating snapshot: {json.dumps(evidence['rating'], ensure_ascii=False)}",
                f"- Performance figures: {json.dumps(evidence['performance'], ensure_ascii=False)}",
                "- Why Velo may be wrong:",
            ]
        )
        for reason in agent["why_velo_may_be_wrong"]:
            lines.append(f"  - {reason}")

    lines.extend(
        [
            "",
            "## Contract",
            "- This is a paper-only analyst layer.",
            "- It does not place bets or promote live execution.",
            "- Any rule change must go through Sigma replay and Mission Control.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--review", default=None)
    parser.add_argument("--downloads", default=str(DEFAULT_DOWNLOADS))
    parser.add_argument("--skip-raceform", action="store_true")
    parser.add_argument("--max-cards", type=int, default=None)
    args = parser.parse_args()

    if args.review:
        review_path = Path(args.review)
        suffix = review_path.stem.replace("tri_lane_agent_review_", "")
    else:
        if not args.date:
            raise SystemExit("--date or --review is required")
        suffix = f"{_slug(args.date)}_v2"
        review_path = REPORT_DIR / f"tri_lane_agent_review_{suffix}.json"

    report = build_report(
        review_path=review_path,
        downloads=Path(args.downloads),
        include_raceform=not args.skip_raceform,
        max_cards=args.max_cards,
    )
    out_json = REPORT_DIR / f"deep_race_agent_v1_{suffix}.json"
    out_md = REPORT_DIR / f"deep_race_agent_v1_{suffix}.md"
    blob = json.dumps(report, indent=2, ensure_ascii=False)
    md = _markdown(report)
    out_json.write_text(blob + "\n", encoding="utf-8")
    out_md.write_text(md, encoding="utf-8")
    (REPORT_DIR / "deep_race_agent_v1_latest.json").write_text(blob + "\n", encoding="utf-8")
    (REPORT_DIR / "deep_race_agent_v1_latest.md").write_text(md, encoding="utf-8")

    print(f"DEEP_RACE_AGENT_V1_COMPLETE cards={report['summary']['cards']}")
    print(f"verdicts={report['summary']['agent_verdict_counts']}")
    print(f"ratings_rows={report['summary']['ratings_rows']} performance_rows={report['summary']['performance_rows']}")
    print(f"race_pdf_files={report['summary']['race_pdf_files']} race_pdf_sets={report['summary']['race_pdf_sets']}")
    print(f"json={out_json}")
    print(f"md={out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
