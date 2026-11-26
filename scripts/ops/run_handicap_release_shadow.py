#!/usr/bin/env python3
"""Build dated, pre-off Handicap Release Shadow evidence cards.

The output is a review queue, never a model score, betting recommendation or
learning input.  It consumes only the existing Racing Post standard-card
artifact and local RP profile history.  Missing or after-off source evidence is
reported explicitly and produces no candidate.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.velo.handicap_release_shadow import HistoricalRun, RaceContext, review_handicap_release

ROOT = Path(__file__).resolve().parents[2]
RACE_SHAPE_DIR = ROOT / "data" / "race_shape"
REPORT_DIR = ROOT / "data" / "reports"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "-") else None
    except (TypeError, ValueError):
        return None


def _course_key(value: Any) -> str | None:
    text = re.sub(r"\(aw\)", "", str(value or ""), flags=re.I)
    text = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return text or None


def _going_bucket(value: Any) -> str | None:
    text = str(value or "").upper()
    if not text:
        return None
    if any(token in text for token in ("STANDARD", "TAPETA", "POLYTRACK", "FAST", "FIRM", "GF")):
        return "FAST_AW"
    if "HEAVY" in text or "VERY SOFT" in text:
        return "HEAVY"
    if "SOFT" in text or "YIELD" in text or text in {"SFT", "GS"}:
        return "SOFT"
    return "GOOD"


def _distance_furlongs(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).casefold().replace("½", ".5")
    match = re.fullmatch(r"(?:(\d+)m)?(?:(\d+(?:\.\d+)?)f)?", text)
    if not match or not (match.group(1) or match.group(2)):
        return None
    return 8 * float(match.group(1) or 0) + float(match.group(2) or 0)


def _load_history(history_dir: Path) -> dict[str, list[HistoricalRun]]:
    rows: dict[str, list[HistoricalRun]] = {}
    seen: set[tuple[str, str, str, str]] = set()
    for filename in sorted(glob.glob(str(history_dir / "form_history_*.json"))):
        if "latest" in filename:
            continue
        try:
            source = json.loads(Path(filename).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for raw in source.get("runs", []):
            runner_id = str(raw.get("horse_rp_uid") or "")
            raw_date = str(raw.get("race_date") or "")
            if not runner_id or not raw_date:
                continue
            try:
                run_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                continue
            dedupe = (runner_id, raw_date, str(raw.get("result_url") or ""), str(raw.get("position") or ""))
            if dedupe in seen:
                continue
            seen.add(dedupe)
            try:
                position = int(raw["position"]) if raw.get("position") not in (None, "", "NR") else None
            except (TypeError, ValueError):
                position = None
            rows.setdefault(runner_id, []).append(HistoricalRun(
                run_date=run_date,
                official_rating=_number(raw.get("or_rating")),
                position=position,
                course=_course_key(raw.get("course_key") or raw.get("course_name")),
                distance_furlongs=_distance_furlongs(raw.get("distance")),
                going_bucket=_going_bucket(raw.get("going")),
            ))
    return rows


def _card_is_preoff(race: dict[str, Any]) -> bool:
    parsed_at, off_at = race.get("parsed_at"), race.get("race_time")
    if not parsed_at or not off_at:
        return False
    try:
        parsed = datetime.fromisoformat(str(parsed_at).replace("Z", "+00:00"))
        off = datetime.fromisoformat(str(off_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if off.tzinfo is None:
            off = off.replace(tzinfo=timezone.utc)
        return parsed <= off
    except ValueError:
        return False


def build(*, standard_cache: Path, target_date: str, execute: bool,
          history_dir: Path = RACE_SHAPE_DIR, report_dir: Path = REPORT_DIR) -> dict[str, Any]:
    try:
        card_date = date.fromisoformat(target_date)
    except ValueError as exc:
        raise ValueError("target_date must be YYYY-MM-DD") from exc
    source = json.loads(standard_cache.read_text(encoding="utf-8"))
    races = source if isinstance(source, list) else source.get("races", [])
    history = _load_history(history_dir)
    rows: list[dict[str, Any]] = []
    for race in races:
        handicap = "handicap" in " ".join(str(race.get(key) or "") for key in ("category", "race_title", "race_type")).casefold()
        card_safe = _card_is_preoff(race)
        for runner in race.get("runners", []):
            runner_id = str(runner.get("horse_id") or "")
            base = {
                "race_id": str(race.get("race_id") or ""), "runner_id": runner_id,
                "horse": runner.get("horse"), "course": race.get("course"),
                "off_time": race.get("race_time"), "card_source": race.get("source"),
                "card_html_sha256": race.get("html_sha256"), "card_parsed_at": race.get("parsed_at"),
                "classification": "SHADOW_ONLY_NO_LIVE_SCORING_CHANGE",
                "provider_predictions_consumed": False,
            }
            if not card_safe:
                base.update({"status": "INSUFFICIENT_EVIDENCE", "missing": ["PREOFF_CARD_TIMESTAMP_UNPROVEN"],
                             "evidence": [], "contradictions": [], "corroborator_count": 0})
            elif runner.get("non_runner") or runner.get("irish_reserve"):
                base.update({"status": "NOT_SUPPORTED", "missing": [], "evidence": [],
                             "contradictions": ["NON_RUNNER_OR_RESERVE"], "corroborator_count": 0})
            elif not runner_id:
                base.update({"status": "INSUFFICIENT_EVIDENCE", "missing": ["RUNNER_ID_MISSING"],
                             "evidence": [], "contradictions": [], "corroborator_count": 0})
            else:
                review = review_handicap_release(RaceContext(
                    race_id=base["race_id"], runner_id=runner_id, race_date=card_date, is_handicap=handicap,
                    official_rating=_number(runner.get("official_rating")), course=_course_key(race.get("course")),
                    distance_furlongs=_number(race.get("distance_furlongs")), going_bucket=_going_bucket(race.get("going")),
                ), history.get(runner_id, ()))
                base.update({
                    "status": review.status, "evidence": list(review.evidence),
                    "contradictions": list(review.contradictions), "missing": list(review.missing),
                    "history_runs_used": review.history_runs_used, "current_or": review.current_or,
                    "last_win_or": review.last_win_or, "best_prior_or": review.best_prior_or,
                    "days_since_run": review.days_since_run, "corroborator_count": review.corroborator_count,
                })
            rows.append(base)
    summary = {
        "task_id": "HANDICAP-RELEASE-SHADOW-01", "target_date": target_date,
        "classification": "SHADOW_ONLY_NO_LIVE_SCORING_CHANGE", "standard_cache": str(standard_cache),
        "history_source": str(history_dir), "total_runners": len(rows),
        "candidate_for_review": sum(row["status"] == "CANDIDATE_FOR_REVIEW" for row in rows),
        "insufficient_evidence": sum(row["status"] == "INSUFFICIENT_EVIDENCE" for row in rows),
        "not_supported": sum(row["status"] == "NOT_SUPPORTED" for row in rows),
        "rows": rows,
    }
    if execute:
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"handicap_release_shadow_{target_date.replace('-', '_')}.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        summary["output_path"] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Handicap Release Shadow review cards.")
    parser.add_argument("--standard-cache", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(standard_cache=Path(args.standard_cache), target_date=args.date, execute=args.execute), indent=2))


if __name__ == "__main__":
    main()
