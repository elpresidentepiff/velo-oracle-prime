"""
VÉLØ PRIME — Spotlight Ingestion Pipeline Worker
=================================================
Automated pipeline that extracts per-horse spotlight comments from raw race
card text, runs the NLP parsing pass via spotlight_parser.py, and writes
structured results to the Supabase `horse_comments` and
`race_spotlight_verdict` tables.

This worker is called by the main ingestion spine AFTER a race card has been
successfully parsed and BEFORE the main engine analysis is triggered.

NULL PATHWAY CONTRACT
---------------------
A failure at any point in this pipeline MUST NOT block the main VÉLØ engine.
The worker will:
  - Catch all exceptions internally
  - Log failures at ERROR level with full traceback
  - Return a SpotlightIngestionResult with success=False and a null_reason
  - Never raise an exception to the caller

The orchestrator will receive an empty spotlight_records dict and proceed
with a structural-only verdict. The null_reason is recorded in the engine
output for auditability.

Spec: docs/VELO_SPOTLIGHT_INGESTION_PIPELINE.md
Architecture: docs/VELO_SPOTLIGHT_ARCHITECTURE.md
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RESULT DATACLASS
# ---------------------------------------------------------------------------

@dataclass
class SpotlightIngestionResult:
    """
    Result returned by the pipeline worker for every invocation.

    success=True  → spotlight_records is populated and ready for the orchestrator.
    success=False → spotlight_records is empty; null_reason explains why.
                    The engine should proceed with a structural-only verdict.
    """
    success: bool
    race_id: str
    horses_processed: int = 0
    horses_with_comments: int = 0
    spotlight_records: dict = field(default_factory=dict)
    null_reason: Optional[str] = None
    error_detail: Optional[str] = None


# ---------------------------------------------------------------------------
# COMMENT EXTRACTION
# ---------------------------------------------------------------------------

# Regex patterns for extracting per-horse comment blocks from raw card text.
# These patterns are designed to match common Racing Post and Spotlight formats.
# The pipeline is tolerant: if no comments are found, it returns a clean null.

# Pattern 1: "HORSE NAME: comment text" (Racing Post PDF extraction format)
_COMMENT_PATTERN_COLON = re.compile(
    r"^([A-Z][A-Za-z\s'\-]+?):\s+(.+?)(?=\n[A-Z][A-Za-z\s'\-]+?:|$)",
    re.MULTILINE | re.DOTALL,
)

# Pattern 2: Numbered runner format "1. HORSE NAME — comment text"
_COMMENT_PATTERN_NUMBERED = re.compile(
    r"^\d+\.\s+([A-Z][A-Za-z\s'\-]+?)\s+[—–-]+\s+(.+?)(?=\n\d+\.|$)",
    re.MULTILINE | re.DOTALL,
)

# Pattern 3: Bracketed format "(HORSE NAME) comment text"
_COMMENT_PATTERN_BRACKETED = re.compile(
    r"\(([A-Z][A-Za-z\s'\-]+?)\)\s+(.+?)(?=\([A-Z]|$)",
    re.DOTALL,
)


def extract_comments_from_text(raw_text: str) -> dict[str, str]:
    """
    Extract per-horse comment blocks from raw card text.

    Tries multiple regex patterns in order of specificity. Returns a dict
    of {horse_name: comment_text}. Returns empty dict if no comments found.

    This function never raises. All exceptions are caught and logged.
    """
    if not raw_text or not raw_text.strip():
        return {}

    results = {}

    try:
        # Try colon format first (most common in Racing Post PDFs)
        for match in _COMMENT_PATTERN_COLON.finditer(raw_text):
            name = match.group(1).strip()
            comment = match.group(2).strip().replace("\n", " ")
            if len(comment) > 10:  # ignore trivially short matches
                results[name] = comment

        # If nothing found, try numbered format
        if not results:
            for match in _COMMENT_PATTERN_NUMBERED.finditer(raw_text):
                name = match.group(1).strip()
                comment = match.group(2).strip().replace("\n", " ")
                if len(comment) > 10:
                    results[name] = comment

        # If still nothing, try bracketed format
        if not results:
            for match in _COMMENT_PATTERN_BRACKETED.finditer(raw_text):
                name = match.group(1).strip()
                comment = match.group(2).strip().replace("\n", " ")
                if len(comment) > 10:
                    results[name] = comment

    except Exception as exc:
        logger.error(
            f"[SPOTLIGHT_EXTRACT_ERROR] Exception during comment extraction: {exc}",
            exc_info=True,
        )

    return results


# ---------------------------------------------------------------------------
# SUPABASE WRITE
# ---------------------------------------------------------------------------

def _get_supabase_client():
    """
    Return a Supabase client using service role credentials.
    Returns None if env vars are not set (e.g., in local dev without Supabase).
    """
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        return create_client(url, key)
    except ImportError:
        logger.warning("[SPOTLIGHT_SUPABASE] supabase package not installed — DB write skipped.")
        return None
    except Exception as exc:
        logger.error(f"[SPOTLIGHT_SUPABASE] Failed to create client: {exc}")
        return None


def write_spotlight_records_to_supabase(
    race_id: str,
    race_date: date,
    spotlight_records: dict,
    supabase_client=None,
) -> bool:
    """
    Write spotlight NLP records to Supabase horse_comments table.

    Returns True on success, False on failure.
    Never raises.
    """
    if not spotlight_records:
        return True  # Nothing to write — not a failure

    client = supabase_client or _get_supabase_client()
    if client is None:
        logger.info("[SPOTLIGHT_SUPABASE] No client available — skipping DB write.")
        return False

    try:
        rows = []
        for horse_name, record in spotlight_records.items():
            rows.append({
                "race_id": race_id,
                "race_date": race_date.isoformat(),
                "horse_name": horse_name,
                "raw_comment": record.get("raw_comment", ""),
                "flag_intent_today": record.get("flag_intent_today", False),
                "flag_excuse_last": record.get("flag_excuse_last", False),
                "flag_stamina_pos": record.get("flag_stamina_pos", False),
                "flag_stamina_risk": record.get("flag_stamina_risk", False),
                "flag_peak_timing": record.get("flag_peak_timing", False),
                "flag_setup_run": record.get("flag_setup_run", False),
                "flag_pji_signal": record.get("flag_pji_signal", False),
                "flag_behaviour": record.get("flag_behaviour", False),
                "flag_trainer_note": record.get("flag_trainer_note", False),
                "flag_market_note": record.get("flag_market_note", False),
                "flag_ground_suit": record.get("flag_ground_suit", False),
                "flag_ground_risk": record.get("flag_ground_risk", False),
                "flag_class_drop": record.get("flag_class_drop", False),
                "flag_class_rise": record.get("flag_class_rise", False),
                "flag_course_specialist": record.get("flag_course_specialist", False),
                "sentiment_score": record.get("sentiment_score", 0),
                "day_type_push": record.get("day_type_push", "NEUTRAL"),
            })

        # Upsert — safe to re-run if the pipeline is triggered twice for the same race
        client.table("horse_comments").upsert(
            rows,
            on_conflict="race_id,horse_name",
        ).execute()

        logger.info(
            f"[SPOTLIGHT_SUPABASE] Wrote {len(rows)} records for race_id={race_id}"
        )
        return True

    except Exception as exc:
        logger.error(
            f"[SPOTLIGHT_SUPABASE] Failed to write records for race_id={race_id}: {exc}",
            exc_info=True,
        )
        return False


# ---------------------------------------------------------------------------
# MAIN PIPELINE FUNCTION
# ---------------------------------------------------------------------------

def run_spotlight_ingestion(
    race_id: str,
    race_date: date,
    raw_spotlight_text: Optional[str] = None,
    write_to_db: bool = True,
    supabase_client=None,
) -> SpotlightIngestionResult:
    """
    Main pipeline entry point.

    Extracts per-horse spotlight comments from raw text, runs NLP parsing,
    optionally writes to Supabase, and returns a SpotlightIngestionResult.

    This function NEVER raises. All failures are caught and returned as
    SpotlightIngestionResult(success=False, null_reason=...).

    Args:
        race_id:             Unique race identifier (e.g., "2026-03-14-FONTWELL-R3")
        race_date:           Date of the race
        raw_spotlight_text:  Raw text extracted from the race card PDF/source.
                             If None or empty, returns a clean null result.
        write_to_db:         If True, writes NLP records to Supabase.
        supabase_client:     Optional pre-initialised Supabase client (for testing).

    Returns:
        SpotlightIngestionResult
    """
    try:
        # Guard: no text provided
        if not raw_spotlight_text or not raw_spotlight_text.strip():
            logger.info(
                f"[SPOTLIGHT_PIPELINE] race_id={race_id} — "
                "no spotlight text provided. Returning clean null."
            )
            return SpotlightIngestionResult(
                success=False,
                race_id=race_id,
                null_reason="NO_COMMENT_DATA_FOUND",
            )

        # Step 1: Extract per-horse comment blocks
        comment_blocks = extract_comments_from_text(raw_spotlight_text)

        if not comment_blocks:
            logger.info(
                f"[SPOTLIGHT_PIPELINE] race_id={race_id} — "
                "text provided but no comment blocks extracted. Returning clean null."
            )
            return SpotlightIngestionResult(
                success=False,
                race_id=race_id,
                horses_processed=0,
                null_reason="NO_COMMENT_BLOCKS_EXTRACTED",
            )

        # Step 2: Run NLP parsing on each comment block
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.dirname(__file__))
            from spotlight_parser import extract_spotlight_signals
        except ImportError as exc:
            logger.error(
                f"[SPOTLIGHT_PIPELINE] spotlight_parser not importable: {exc}"
            )
            return SpotlightIngestionResult(
                success=False,
                race_id=race_id,
                null_reason="SPOTLIGHT_MODULE_UNAVAILABLE",
                error_detail=str(exc),
            )

        spotlight_records = {}
        for horse_name, comment_text in comment_blocks.items():
            try:
                record = extract_spotlight_signals(
                    raw_text=comment_text,
                    horse_name=horse_name,
                    race_id=race_id,
                    race_date=race_date,
                )
                spotlight_records[horse_name] = record
            except Exception as exc:
                # A single horse parse failure must not abort the whole race
                logger.warning(
                    f"[SPOTLIGHT_PIPELINE] Parse failed for horse={horse_name} "
                    f"in race_id={race_id}: {exc}"
                )

        horses_with_comments = len(spotlight_records)

        if horses_with_comments == 0:
            logger.warning(
                f"[SPOTLIGHT_PIPELINE] race_id={race_id} — "
                "comment blocks found but all NLP parses failed."
            )
            return SpotlightIngestionResult(
                success=False,
                race_id=race_id,
                horses_processed=len(comment_blocks),
                null_reason="ALL_NLP_PARSES_FAILED",
            )

        # Step 3: Optionally write to Supabase
        if write_to_db:
            write_spotlight_records_to_supabase(
                race_id=race_id,
                race_date=race_date,
                spotlight_records=spotlight_records,
                supabase_client=supabase_client,
            )

        logger.info(
            f"[SPOTLIGHT_PIPELINE] race_id={race_id} — "
            f"SUCCESS. {horses_with_comments}/{len(comment_blocks)} horses parsed."
        )

        return SpotlightIngestionResult(
            success=True,
            race_id=race_id,
            horses_processed=len(comment_blocks),
            horses_with_comments=horses_with_comments,
            spotlight_records=spotlight_records,
        )

    except Exception as exc:
        # Outer catch-all: pipeline failure must never block the engine
        logger.error(
            f"[SPOTLIGHT_PIPELINE_EXCEPTION] Unhandled exception for race_id={race_id}: {exc}",
            exc_info=True,
        )
        return SpotlightIngestionResult(
            success=False,
            race_id=race_id,
            null_reason=f"PIPELINE_EXCEPTION: {type(exc).__name__}",
            error_detail=str(exc),
        )


# ---------------------------------------------------------------------------
# SUPABASE QUERY — used by orchestrator to retrieve spotlight_records
# ---------------------------------------------------------------------------

def fetch_spotlight_records_from_supabase(
    race_id: str,
    supabase_client=None,
) -> dict:
    """
    Query Supabase for spotlight NLP records for a given race_id.

    Returns a dict of {horse_name: spotlight_record} ready for the orchestrator.
    Returns an empty dict on failure or if no records exist.
    Never raises.
    """
    client = supabase_client or _get_supabase_client()
    if client is None:
        return {}

    try:
        result = (
            client.table("horse_comments")
            .select("*")
            .eq("race_id", race_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {}

        # Convert list of rows to {horse_name: record} dict
        records = {}
        for row in rows:
            horse_name = row.get("horse_name")
            if horse_name:
                records[horse_name] = row
        return records

    except Exception as exc:
        logger.error(
            f"[SPOTLIGHT_FETCH] Failed to fetch records for race_id={race_id}: {exc}",
            exc_info=True,
        )
        return {}


# ---------------------------------------------------------------------------
# CLI ENTRY POINT (for manual testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    from datetime import date as _date

    parser = argparse.ArgumentParser(description="VÉLØ Spotlight Ingestion Pipeline")
    parser.add_argument("--race-id", required=True, help="Race identifier")
    parser.add_argument("--date", required=True, help="Race date (YYYY-MM-DD)")
    parser.add_argument("--text-file", required=True, help="Path to raw spotlight text file")
    parser.add_argument("--no-db", action="store_true", help="Skip Supabase write")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    with open(args.text_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    race_date = _date.fromisoformat(args.date)
    result = run_spotlight_ingestion(
        race_id=args.race_id,
        race_date=race_date,
        raw_spotlight_text=raw_text,
        write_to_db=not args.no_db,
    )

    print(f"\n=== Spotlight Ingestion Result ===")
    print(f"Success:              {result.success}")
    print(f"Race ID:              {result.race_id}")
    print(f"Horses processed:     {result.horses_processed}")
    print(f"Horses with comments: {result.horses_with_comments}")
    print(f"Null reason:          {result.null_reason}")
    if result.error_detail:
        print(f"Error detail:         {result.error_detail}")
    if result.spotlight_records:
        print(f"\nSpotlight records ({len(result.spotlight_records)} horses):")
        for name, rec in result.spotlight_records.items():
            flags = [k for k, v in rec.items() if k.startswith("flag_") and v]
            print(f"  {name}: flags={flags}, sentiment={rec.get('sentiment_score', 0)}")
