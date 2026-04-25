"""
Ingest Racing Post PDF bundles into Supabase.

Phase 1 foundation:
- discover venue/date bundles from incoming PDFs
- de-duplicate duplicate filenames like "(1)"
- parse meetings through workers.ingestion_spine.racingpost_pdf
- persist file ingest log + parsed meetings/races/runners/signals

This lane is intentionally separate from live VELO scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.runtime_env import resolve_supabase_url, resolve_supabase_service_key, load_optional_env_file
from supabase import create_client
from scripts.build_rp_runner_signals import build_decoder_fields
from workers.ingestion_spine.racingpost_pdf import parse_meeting

PARSER_VERSION = "rp_phase1_bundle_ingest"

FILENAME_RE = re.compile(
    r"^(?P<venue>[A-Z0-9]+)_(?P<date>\d{8})_\d{2}_\d{2}_F_(?P<code>\d{4})_(?P<role>[A-Z]{2})_(?P<course>.+)\.pdf$"
)

TRACK_FILE_ORDER = [
    "0012_XX",  # colour card backbone
    "0003_XX",  # alternate backbone
    "0016_XX",  # spotlight file
    "0011_XX",  # postdata file
    "0015_OR",  # OR / handicap history
    "0032_TS",  # Top Speed history
]
V3_DECODER_COLUMNS = {
    "decoder_version",
    "decoded_at",
    "decode_confidence",
    "decode_errors",
    "ts_history_tokens",
    "or_history_tokens",
    "ts_history_values",
    "or_history_values",
    "ts_history_valid_count",
    "or_history_valid_count",
    "ts_history_invalid_count",
    "or_history_invalid_count",
}
WELL_TREATED_PHRASES = (
    "well treated",
    "good chance at the weights",
    "good chance at the weights in a claimer",
)
CLASS_DROP_PHRASES = (
    "dropped in class",
    "step down in class",
    "class dropper",
)
HEADGEAR_CHANGE_PHRASES = (
    "cheekpieces now added",
    "cheekpieces added",
    "first-time blinkers",
    "first-time visor",
    "first-time hood",
    "blinkers now added",
    "visor now added",
)
MARKET_WATCH_PHRASES = (
    "check for market moves",
    "market moves",
    "worth a market check",
    "watch the market",
)
TRAINER_POSITIVE_PHRASES = (
    "yard in form",
    "trainer in form",
    "host of other chances",
    "should go well",
    "gets the vote",
    "in the mix",
)
_MIN_PLAUSIBLE_OR = 40
_MAX_PLAUSIBLE_OR = 180


@dataclass(frozen=True)
class PdfFile:
    path: Path
    canonical_name: str
    venue_code: str
    source_date: str
    file_code: str
    file_role: str
    course_name: str

    @property
    def family_key(self) -> str:
        return f"{self.file_code}_{self.file_role}"

    @property
    def bundle_key(self) -> str:
        return f"{self.venue_code}_{self.source_date}_{self.course_name}"


def canonicalize_pdf_name(name: str) -> str:
    return re.sub(r" \(\d+\)(?=\.pdf$)", "", name.strip())


def parse_pdf_filename(path: Path) -> PdfFile | None:
    canonical_name = canonicalize_pdf_name(path.name)
    match = FILENAME_RE.match(canonical_name)
    if not match:
        return None
    course_name = match.group("course").replace(".pdf", "").strip()
    return PdfFile(
        path=path,
        canonical_name=canonical_name,
        venue_code=match.group("venue"),
        source_date=match.group("date"),
        file_code=match.group("code"),
        file_role=match.group("role"),
        course_name=course_name,
    )


def choose_preferred_duplicate(existing: PdfFile, candidate: PdfFile) -> PdfFile:
    def score(pdf: PdfFile) -> tuple[int, int]:
        duplicate_penalty = 1 if pdf.path.name != pdf.canonical_name else 0
        return duplicate_penalty, len(pdf.path.name)

    return existing if score(existing) <= score(candidate) else candidate


def discover_pdf_bundles(directory: Path, *, venues: set[str] | None = None, source_date: str | None = None) -> dict[str, dict[str, PdfFile]]:
    bundles: dict[str, dict[str, PdfFile]] = {}

    for path in sorted(directory.glob("*.pdf")):
        parsed = parse_pdf_filename(path)
        if not parsed:
            continue
        if venues and parsed.venue_code not in venues:
            continue
        if source_date and parsed.source_date != source_date.replace("-", ""):
            continue

        bundle = bundles.setdefault(parsed.bundle_key, {})
        existing = bundle.get(parsed.canonical_name)
        bundle[parsed.canonical_name] = parsed if existing is None else choose_preferred_duplicate(existing, parsed)

    return bundles


def selected_bundle_inputs(files: dict[str, PdfFile]) -> list[Path]:
    selected: list[PdfFile] = []
    by_family = {item.family_key: item for item in files.values()}

    for family in TRACK_FILE_ORDER:
        candidate = by_family.get(family)
        if candidate is not None:
            selected.append(candidate)

    return [item.path for item in selected]


def pdf_text_and_pages(path: Path) -> tuple[str, int]:
    text_parts: list[str] = []
    page_count = 0
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts), page_count


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_recent_positions(form_figures: str | None) -> list[int]:
    if not form_figures:
        return []
    digits: list[int] = []
    for char in str(form_figures):
        if char.isdigit():
            digits.append(int(char))
    return digits[-6:]


def _derive_spotlight_signals(
    runner: dict[str, Any],
    raw_fields: dict[str, Any],
    *,
    has_recent_place: bool | None,
) -> dict[str, Any]:
    spotlight_text = str(raw_fields.get("spotlight") or "").strip()
    comment_text = str(raw_fields.get("comment") or "").strip()
    race_verdict_text = str(raw_fields.get("spotlight_race_verdict") or "").strip()
    text_parts = [part for part in (spotlight_text, comment_text) if part]
    text_blob = " ".join(text_parts).lower()
    if not text_blob:
        return {
            "spotlight_text": spotlight_text or None,
            "comment_text": comment_text or None,
            "race_verdict_text": race_verdict_text or None,
            "well_treated_flag": False,
            "class_drop_flag": False,
            "headgear_change_flag": False,
            "market_watch_flag": False,
            "trainer_positive_flag": None,
            "release_window_flag": None,
            "cash_run_flag": None,
            "spotlight_tags": [],
        }

    well_treated_flag = any(phrase in text_blob for phrase in WELL_TREATED_PHRASES)
    class_drop_flag = any(phrase in text_blob for phrase in CLASS_DROP_PHRASES)
    headgear_change_flag = any(phrase in text_blob for phrase in HEADGEAR_CHANGE_PHRASES)
    market_watch_flag = any(phrase in text_blob for phrase in MARKET_WATCH_PHRASES)
    trainer_positive_flag = any(phrase in text_blob for phrase in TRAINER_POSITIVE_PHRASES)

    days_since_run = runner.get("days_since_run")
    release_window_flag = None
    if days_since_run is not None:
        release_window_flag = 7 <= int(days_since_run) <= 30 and (
            well_treated_flag or class_drop_flag or trainer_positive_flag or bool(has_recent_place)
        )

    cash_run_flag = well_treated_flag or market_watch_flag or ("back it up" in text_blob)
    spotlight_tags = [
        tag
        for tag, enabled in (
            ("well_treated", well_treated_flag),
            ("class_drop", class_drop_flag),
            ("headgear_change", headgear_change_flag),
            ("market_watch", market_watch_flag),
            ("trainer_positive", trainer_positive_flag),
            ("release_window", bool(release_window_flag)),
            ("cash_run", cash_run_flag),
        )
        if enabled
    ]

    return {
        "spotlight_text": spotlight_text or None,
        "comment_text": comment_text or None,
        "race_verdict_text": race_verdict_text or None,
        "well_treated_flag": well_treated_flag,
        "class_drop_flag": class_drop_flag,
        "headgear_change_flag": headgear_change_flag,
        "market_watch_flag": market_watch_flag,
        "trainer_positive_flag": trainer_positive_flag,
        "release_window_flag": release_window_flag,
        "cash_run_flag": cash_run_flag,
        "spotlight_tags": spotlight_tags,
    }


def _sanitize_live_signal_values(signal_payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(signal_payload)
    compression = cleaned.get("or_compression_score")
    if compression is not None and abs(float(compression)) >= 10000:
        cleaned["or_compression_score"] = None
    return cleaned


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_position_from_or_token(token: str | None) -> int | None:
    if not token:
        return None
    cleaned = str(token).strip()
    if not cleaned or not cleaned[0].isdigit():
        return None
    return int(cleaned[0])


def _extract_or_mark_from_token(token: str | None) -> int | None:
    if not token:
        return None

    cleaned = str(token).strip().lower()
    if not cleaned or not cleaned[0].isdigit():
        return None

    digits = "".join(char for char in cleaned[1:] if char.isdigit())
    candidates: list[int] = []
    if len(digits) >= 3:
        candidates.append(int(digits[:3]))
    if len(digits) >= 2:
        candidates.append(int(digits[:2]))

    for candidate in candidates:
        if _MIN_PLAUSIBLE_OR <= candidate <= _MAX_PLAUSIBLE_OR:
            return candidate
    return None


def _infer_bwl_signal(current_or: int | None, or_history_tokens: list[str] | None) -> dict[str, Any]:
    current = _safe_int(current_or)
    winning_marks: list[int] = []
    inferred_pairs: list[dict[str, Any]] = []

    for token in or_history_tokens or []:
        position = _extract_position_from_or_token(token)
        inferred_or = _extract_or_mark_from_token(token)
        if position is None or inferred_or is None:
            continue
        inferred_pairs.append({"token": token, "position": position, "or_mark": inferred_or})
        if position == 1:
            winning_marks.append(inferred_or)

    bwl_or = max(winning_marks) if winning_marks else None
    compression_lbs = (bwl_or - current) if (bwl_or is not None and current is not None) else None
    in_window_flag = compression_lbs is not None and compression_lbs >= 0
    major_compression_flag = compression_lbs is not None and compression_lbs >= 10

    if bwl_or is None or current is None:
        compression_score = 0.0
    elif current <= bwl_or:
        if compression_lbs >= 10:
            compression_score = 1.0
        elif compression_lbs >= 5:
            compression_score = 0.92
        else:
            compression_score = 0.85
    else:
        if compression_lbs >= -5:
            compression_score = 0.45
        else:
            compression_score = 0.1

    confidence = 0.0
    if bwl_or is not None:
        confidence = min(1.0, 0.35 + (0.2 * len(winning_marks)) + (0.05 * len(inferred_pairs)))

    return {
        "current_or": current,
        "bwl_or": bwl_or,
        "winning_or_marks": winning_marks,
        "compression_lbs": compression_lbs,
        "in_window_flag": in_window_flag,
        "major_compression_flag": major_compression_flag,
        "compression_score": compression_score,
        "confidence": round(confidence, 4),
        "inferred_pairs": inferred_pairs,
    }


def _compute_postdata_signal(raw_fields: dict[str, Any]) -> dict[str, Any]:
    positive_count = _safe_int(raw_fields.get("postdata_positive_count")) or 0
    negative_count = _safe_int(raw_fields.get("postdata_negative_count")) or 0
    unknown_count = _safe_int(raw_fields.get("postdata_unknown_count")) or 0
    flags_raw = str(raw_fields.get("postdata_flags_raw") or "").strip()
    known_total = positive_count + negative_count
    total = known_total + unknown_count

    if known_total:
        balance_score = positive_count / known_total
    else:
        balance_score = 0.0

    cold_flag = known_total > 0 and negative_count > positive_count
    hot_flag = known_total > 0 and positive_count >= max(3, negative_count + 2)

    trainer_cluster = next((part for part in flags_raw.split() if part.strip()), None)
    trainer_signal = None
    trainer_hot_flag = False
    trainer_cold_flag = False
    if trainer_cluster:
        if "✓" in trainer_cluster:
            trainer_signal = "positive"
            trainer_hot_flag = True
        elif "✘" in trainer_cluster:
            trainer_signal = "negative"
            trainer_cold_flag = True
        elif "?" in trainer_cluster:
            trainer_signal = "unknown"

    return {
        "positive_count": positive_count,
        "negative_count": negative_count,
        "unknown_count": unknown_count,
        "known_total": known_total,
        "total": total,
        "balance_score": round(balance_score, 4),
        "cold_flag": cold_flag,
        "hot_flag": hot_flag,
        "trainer_signal": trainer_signal,
        "trainer_hot_flag": trainer_hot_flag,
        "trainer_cold_flag": trainer_cold_flag,
        "trainer_cluster": trainer_cluster,
    }


def _score_plot_conviction(
    *,
    bwl_signal: dict[str, Any],
    postdata_signal: dict[str, Any],
    spotlight_signals: dict[str, Any],
    postdata_pick_flag: bool,
    topspeed_pick_flag: bool,
    ts_improving_flag: bool | None,
) -> dict[str, Any]:
    or_component = bwl_signal["compression_score"]
    ts_component = 1.0 if topspeed_pick_flag else (0.6 if ts_improving_flag else 0.0)
    postdata_component = 1.0 if postdata_pick_flag else min(1.0, postdata_signal["balance_score"])

    headgear_change_flag = spotlight_signals["headgear_change_flag"]
    release_window_flag = bool(spotlight_signals["release_window_flag"])
    cash_run_flag = bool(spotlight_signals["cash_run_flag"])
    trainer_positive_flag = bool(spotlight_signals["trainer_positive_flag"])
    trainer_hot_flag = bool(postdata_signal["trainer_hot_flag"])
    trainer_cold_flag = bool(postdata_signal["trainer_cold_flag"])

    intent_component = 0.0
    if cash_run_flag:
        intent_component += 0.6
    if release_window_flag:
        intent_component += 0.2
    if headgear_change_flag:
        intent_component += 0.1
    if trainer_positive_flag:
        intent_component += 0.1
    if trainer_hot_flag:
        intent_component += 0.1
    intent_component = min(1.0, intent_component)

    conviction = round(
        (0.4 * or_component)
        + (0.2 * ts_component)
        + (0.2 * postdata_component)
        + (0.2 * intent_component),
        4,
    )

    if conviction >= 0.85:
        band = "3_star"
        stars = 3
    elif conviction >= 0.70:
        band = "2_star"
        stars = 2
    elif conviction >= 0.50:
        band = "1_star"
        stars = 1
    else:
        band = "no_pick"
        stars = 0

    return {
        "plot_conviction_score": conviction,
        "plot_band": band,
        "plot_stars": stars,
        "or_component": round(or_component, 4),
        "ts_component": round(ts_component, 4),
        "postdata_component": round(postdata_component, 4),
        "intent_component": round(intent_component, 4),
        "cold_stable_plot_flag": trainer_cold_flag and release_window_flag,
    }


def build_runner_signal_payload(runner: dict[str, Any]) -> dict[str, Any]:
    raw_fields = runner.get("raw", {})
    recent_positions = parse_recent_positions(runner.get("form_figures"))
    true_run_count = sum(1 for pos in recent_positions if 1 <= pos <= 3)
    has_recent_win = any(pos == 1 for pos in recent_positions) if recent_positions else None
    has_recent_place = any(1 <= pos <= 3 for pos in recent_positions) if recent_positions else None
    postdata_pick_flag = bool(raw_fields.get("postdata_pick"))
    topspeed_pick_flag = bool(raw_fields.get("topspeed_pick"))
    decoder_fields = build_decoder_fields(
        raw_fields.get("ts_history_last6"),
        raw_fields.get("or_history_last6"),
    )
    decoder_metrics = decoder_fields.pop("decoder_metrics")
    decoder_fields = _sanitize_live_signal_values(decoder_fields)
    spotlight_signals = _derive_spotlight_signals(
        runner,
        raw_fields,
        has_recent_place=has_recent_place,
    )
    bwl_signal = _infer_bwl_signal(runner.get("or_rating") or raw_fields.get("or_current"), raw_fields.get("or_history_last6"))
    postdata_signal = _compute_postdata_signal(raw_fields)
    trainer_hot_flag = bool(postdata_signal["trainer_hot_flag"])
    trainer_cold_flag = bool(postdata_signal["trainer_cold_flag"])
    conviction = _score_plot_conviction(
        bwl_signal=bwl_signal,
        postdata_signal=postdata_signal,
        spotlight_signals=spotlight_signals,
        postdata_pick_flag=postdata_pick_flag,
        topspeed_pick_flag=topspeed_pick_flag,
        ts_improving_flag=decoder_fields["ts_improving_flag"],
    )

    signal_bits: list[str] = []
    if recent_positions:
        signal_bits.append(f"recent={recent_positions}")
    if true_run_count:
        signal_bits.append(f"true_runs={true_run_count}")
    if runner.get("days_since_run") is not None:
        signal_bits.append(f"days_since_run={runner['days_since_run']}")
    if decoder_fields.get("ts_improving_flag") is True:
        signal_bits.append("ts_improving")
    if decoder_fields.get("or_drop_streak"):
        signal_bits.append(f"or_drop_streak={decoder_fields['or_drop_streak']}")
    if decoder_fields.get("or_compression_score") is not None:
        signal_bits.append(f"or_compression={decoder_fields['or_compression_score']}")
    if postdata_pick_flag:
        signal_bits.append("postdata_pick")
    if topspeed_pick_flag:
        signal_bits.append("topspeed_pick")
    if bwl_signal["bwl_or"] is not None:
        signal_bits.append(f"bwl={bwl_signal['bwl_or']}")
    if bwl_signal["compression_lbs"] is not None:
        signal_bits.append(f"or_window={bwl_signal['compression_lbs']}lb")
    if bwl_signal["major_compression_flag"]:
        signal_bits.append("major_compression")
    if conviction["cold_stable_plot_flag"]:
        signal_bits.append("cold_stable_plot")
    if trainer_hot_flag:
        signal_bits.append("trainer_hot_postdata")
    if trainer_cold_flag:
        signal_bits.append("trainer_cold_postdata")
    for tag in spotlight_signals["spotlight_tags"]:
        signal_bits.append(tag)
    if conviction["plot_stars"]:
        signal_bits.append(f"plot={conviction['plot_band']}")

    return {
        "recent_finish_positions": recent_positions,
        "true_run_count": true_run_count if recent_positions else None,
        "has_recent_win": has_recent_win,
        "has_recent_place": has_recent_place,
        "days_since_run": runner.get("days_since_run"),
        "ts_improving_flag": decoder_fields["ts_improving_flag"],
        "or_drop_streak": decoder_fields["or_drop_streak"],
        "or_compression_score": decoder_fields["or_compression_score"],
        "release_window_flag": spotlight_signals["release_window_flag"],
        "cash_run_flag": spotlight_signals["cash_run_flag"],
        "trainer_positive_flag": spotlight_signals["trainer_positive_flag"],
        "spotlight_present_flag": bool(spotlight_signals["spotlight_text"]),
        "comment_present_flag": bool(spotlight_signals["comment_text"]),
        "signal_summary": "; ".join(signal_bits) if signal_bits else None,
        **decoder_fields,
        "raw_signal_payload": {
            "phase": "rp_phase1",
            "available_fields": {
                "or_current": runner.get("or_rating"),
                "rpr_current": runner.get("rpr"),
                "ts_current": runner.get("ts"),
                "form_figures": runner.get("form_figures"),
                "days_since_run": runner.get("days_since_run"),
                "or_history_last6": raw_fields.get("or_history_last6"),
                "ts_history_last6": raw_fields.get("ts_history_last6"),
                "pm_history_last6": raw_fields.get("pm_history_last6"),
                "spotlight": spotlight_signals["spotlight_text"],
                "comment": spotlight_signals["comment_text"],
                "spotlight_race_verdict": spotlight_signals["race_verdict_text"],
                "postdata_pick": postdata_pick_flag,
                "topspeed_pick": topspeed_pick_flag,
                "postdata_pick_name": raw_fields.get("postdata_pick_name"),
                "topspeed_pick_name": raw_fields.get("topspeed_pick_name"),
                "postdata_positive_count": raw_fields.get("postdata_positive_count"),
                "postdata_latest_rating": raw_fields.get("postdata_latest_rating"),
            },
            "decoder_metrics": decoder_metrics,
            "conviction_analysis": {
                **conviction,
                "bwl_or": bwl_signal["bwl_or"],
                "current_or": bwl_signal["current_or"],
                "compression_lbs": bwl_signal["compression_lbs"],
                "in_window_flag": bwl_signal["in_window_flag"],
                "major_compression_flag": bwl_signal["major_compression_flag"],
                "winning_or_marks": bwl_signal["winning_or_marks"],
                "bwl_confidence": bwl_signal["confidence"],
                "bwl_inferred_pairs": bwl_signal["inferred_pairs"],
            },
            "spotlight_analysis": {
                "spotlight_tags": spotlight_signals["spotlight_tags"],
                "well_treated_flag": spotlight_signals["well_treated_flag"],
                "class_drop_flag": spotlight_signals["class_drop_flag"],
                "headgear_change_flag": spotlight_signals["headgear_change_flag"],
                "market_watch_flag": spotlight_signals["market_watch_flag"],
                "spotlight_text": spotlight_signals["spotlight_text"],
                "comment_text": spotlight_signals["comment_text"],
                "race_verdict_text": spotlight_signals["race_verdict_text"],
            },
            "postdata_analysis": {
                "postdata_pick": postdata_pick_flag,
                "topspeed_pick": topspeed_pick_flag,
                "postdata_pick_name": raw_fields.get("postdata_pick_name"),
                "topspeed_pick_name": raw_fields.get("topspeed_pick_name"),
                "postdata_positive_count": raw_fields.get("postdata_positive_count"),
                "postdata_negative_count": raw_fields.get("postdata_negative_count"),
                "postdata_unknown_count": raw_fields.get("postdata_unknown_count"),
                "postdata_flags_raw": raw_fields.get("postdata_flags_raw"),
                "postdata_row": raw_fields.get("postdata_row"),
                "postdata_latest_rating": raw_fields.get("postdata_latest_rating"),
                "postdata_balance_score": postdata_signal["balance_score"],
                "postdata_hot_flag": postdata_signal["hot_flag"],
                "postdata_cold_flag": postdata_signal["cold_flag"],
                "trainer_signal": postdata_signal["trainer_signal"],
                "trainer_hot_flag": postdata_signal["trainer_hot_flag"],
                "trainer_cold_flag": postdata_signal["trainer_cold_flag"],
                "trainer_cluster": postdata_signal["trainer_cluster"],
            },
        },
    }


def serialize_errors(items: list[Any]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            serialized.append(item.model_dump())
        elif hasattr(item, "dict"):
            serialized.append(item.dict())
        else:
            serialized.append({"message": str(item)})
    return serialized


def _dedupe_rows(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        deduped[key] = row
    return list(deduped.values())


def _strip_v3_decoder_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped_rows: list[dict[str, Any]] = []
    for row in rows:
        stripped_rows.append({key: value for key, value in row.items() if key not in V3_DECODER_COLUMNS})
    return stripped_rows


def persist_bundle(db, *, bundle_key: str, files: dict[str, PdfFile], report, dry_run: bool) -> dict[str, Any]:
    sample = next(iter(files.values()))
    selected_inputs = selected_bundle_inputs(files)
    selected_names = {canonicalize_pdf_name(path.name) for path in selected_inputs}

    file_rows: list[dict[str, Any]] = []
    for pdf in files.values():
        extracted_text, page_count = pdf_text_and_pages(pdf.path)
        file_rows.append(
            {
                "source_date": datetime.strptime(pdf.source_date, "%Y%m%d").date().isoformat(),
                "venue_code": pdf.venue_code,
                "course_name": pdf.course_name,
                "bundle_key": bundle_key,
                "file_name": pdf.path.name,
                "canonical_file_name": pdf.canonical_name,
                "file_role": pdf.family_key,
                "file_hash": sha256_file(pdf.path),
                "page_count": page_count,
                "ingest_status": "selected" if pdf.canonical_name in selected_names else "ignored_duplicate",
                "parser_version": PARSER_VERSION,
                "parse_success": bool(report.success) if pdf.canonical_name in selected_names else None,
                "extracted_text": extracted_text,
                "error_message": None,
                "metadata": {
                    "selected_for_parse": pdf.canonical_name in selected_names,
                    "path": str(pdf.path),
                },
            }
        )

    meeting_row = {
        "bundle_key": bundle_key,
        "source_date": datetime.strptime(sample.source_date, "%Y%m%d").date().isoformat(),
        "venue_code": sample.venue_code,
        "course_name": sample.course_name,
        "parser_version": PARSER_VERSION,
        "parse_success": bool(report.success),
        "races_count": report.stats.get("races_count", 0),
        "runners_count": report.stats.get("runners_count", 0),
        "input_files": [path.name for path in selected_inputs],
        "warnings": serialize_errors(report.warnings),
        "errors": serialize_errors(report.errors),
        "raw_report": report.model_dump(exclude={"meeting"}) if hasattr(report, "model_dump") else {},
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    race_rows: list[dict[str, Any]] = []
    runner_rows: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []

    if report.success and report.meeting is not None:
        for race in report.meeting.races:
            race_key = race.race_id
            race_rows.append(
                {
                    "race_key": race_key,
                    "bundle_key": bundle_key,
                    "source_date": meeting_row["source_date"],
                    "venue_code": sample.venue_code,
                    "course_name": race.course,
                    "off_time": race.off_time.isoformat(),
                    "race_name": race.race_name,
                    "race_number": race.race_number,
                    "race_type": race.race_type,
                    "distance_text": race.distance_text,
                    "distance_yards": race.distance_yards,
                    "distance_furlongs": race.distance_furlongs,
                    "distance_meters": race.distance_meters,
                    "class_band": race.class_band,
                    "going": race.going,
                    "prize": race.prize,
                    "runners_count": race.runners_count,
                    "raw_bundle": race.raw,
                }
            )

            for runner in race.runners:
                runner_payload = {
                    "race_key": race_key,
                    "runner_number": runner.runner_number,
                    "horse_name": runner.name,
                    "cloth_no": runner.cloth_no,
                    "age": runner.age,
                    "sex": runner.sex,
                    "weight": runner.weight,
                    "days_since_run": runner.days_since_run,
                    "trainer_name": runner.trainer,
                    "jockey_name": runner.jockey,
                    "owner_name": runner.owner,
                    "draw": runner.draw,
                    "headgear": runner.headgear,
                    "form_figures": runner.form_figures,
                    "or_current": runner.or_rating,
                    "rpr_current": runner.rpr,
                    "ts_current": runner.ts,
                    "raw_runner_bundle": runner.raw,
                }
                runner_rows.append(runner_payload)

                signal_payload = build_runner_signal_payload(
                    {
                        **runner_payload,
                        "raw": runner.raw,
                    }
                )
                signal_rows.append(
                    {
                        "race_key": race_key,
                        "runner_number": runner.runner_number,
                        "horse_name": runner.name,
                        "signal_version": "rp_phase1",
                        **signal_payload,
                    }
                )

    runner_rows = _dedupe_rows(runner_rows, ("race_key", "runner_number"))
    signal_rows = _dedupe_rows(signal_rows, ("race_key", "runner_number"))

    if not dry_run:
        db.table("rp_file_ingest_log").upsert(file_rows, on_conflict="bundle_key,canonical_file_name,file_hash").execute()
        db.table("rp_meetings").upsert(meeting_row, on_conflict="bundle_key").execute()
        if race_rows:
            db.table("rp_racecards").upsert(race_rows, on_conflict="race_key").execute()
        if runner_rows:
            db.table("rp_runner_profiles").upsert(runner_rows, on_conflict="race_key,runner_number").execute()
        if signal_rows:
            try:
                db.table("rp_runner_signals").upsert(signal_rows, on_conflict="race_key,runner_number").execute()
            except Exception as exc:
                if "decode_confidence" not in str(exc):
                    raise
                compatible_rows = _strip_v3_decoder_columns(signal_rows)
                db.table("rp_runner_signals").upsert(compatible_rows, on_conflict="race_key,runner_number").execute()

    return {
        "bundle_key": bundle_key,
        "selected_inputs": [path.name for path in selected_inputs],
        "success": bool(report.success),
        "races_count": len(race_rows),
        "runners_count": len(runner_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Racing Post PDF bundles into Supabase")
    parser.add_argument("--dir", default="data/incoming_pdfs", help="Directory containing PDF files")
    parser.add_argument("--venue", nargs="*", help="Venue code(s) to process, e.g. FON CHP")
    parser.add_argument("--date", help="Source date in YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing to Supabase")
    parser.add_argument("--no-validate", action="store_true", help="Skip parser validation gates")
    args = parser.parse_args()

    load_optional_env_file(ROOT / ".env")

    directory = Path(args.dir)
    if not directory.is_absolute():
        directory = ROOT / directory
    if not directory.exists():
        raise SystemExit(f"Input directory does not exist: {directory}")

    venues = {value.strip().upper() for value in (args.venue or []) if value.strip()} or None
    bundles = discover_pdf_bundles(directory, venues=venues, source_date=args.date)
    if not bundles:
        print("No matching PDF bundles found.")
        return 0

    load_optional_env_file(ROOT / ".env")
    url = resolve_supabase_url()
    key = resolve_supabase_service_key()
    if not url or not key:
        print("Error: Supabase credentials not found.")
        return 1
    db = None if args.dry_run else create_client(url, key)

    print(f"Discovered {len(bundles)} bundle(s) in {directory}")
    processed = 0
    successes = 0

    for bundle_key, files in sorted(bundles.items()):
        selected_inputs = selected_bundle_inputs(files)
        if not selected_inputs:
            print(f"[SKIP] {bundle_key} - no parseable XX backbone file found")
            continue

        print(f"[BUNDLE] {bundle_key}")
        print(f"  inputs: {', '.join(path.name for path in selected_inputs)}")
        report = parse_meeting([str(path) for path in selected_inputs], validate_output=not args.no_validate)
        summary = persist_bundle(db, bundle_key=bundle_key, files=files, report=report, dry_run=args.dry_run)
        processed += 1
        successes += 1 if summary["success"] else 0
        print(
            f"  success={summary['success']} races={summary['races_count']} "
            f"runners={summary['runners_count']}"
        )
        if report.errors:
            print(f"  errors={len(report.errors)}")
            for item in report.errors[:3]:
                message = getattr(item, "message", str(item))
                print(f"    - {message}")

    print()
    print(f"Bundles processed: {processed}")
    print(f"Bundles successful: {successes}")
    print(f"Mode: {'dry-run' if args.dry_run else 'persisted'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
