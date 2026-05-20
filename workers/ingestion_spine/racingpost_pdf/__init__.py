"""
Racing Post PDF Parser
One source of truth: canonical JSON from validated PDF parse.
"""

import os
import re
from datetime import datetime
from typing import Optional

from .merge import merge_ratings
from .parse_or import parse_or_card
from .parse_pm import parse_pm_card
from .parse_postdata import parse_postdata_card
from .parse_spotlight import parse_spotlight_card
from .parse_ts import parse_ts_card
from .parse_xx import parse_xx_card
from .parse_xx_v2 import parse_xx_v2_card
from .types import Meeting, ParseError, ParseReport, Race, Runner
from .validate import validate_meeting


def parse_meeting(pdf_paths: list[str], validate_output: bool = True) -> ParseReport:
    """
    Parse Racing Post PDFs and return canonical meeting data.
    Supports standard 0012_XX and alternate 0003_XX racecard formats.
    """
    errors = []
    warnings = []

    # Categorize PDFs by type
    xx_pdf = None
    spotlight_pdf = None
    postdata_pdf = None
    or_pdf = None
    ts_pdf = None
    pm_pdf = None

    for pdf_path in pdf_paths:
        filename = os.path.basename(pdf_path)

        if "_F_0012_XX_" in filename or "_F_0003_XX_" in filename:
            xx_pdf = pdf_path
        elif "_F_0016_XX_" in filename:
            spotlight_pdf = pdf_path
        elif "_F_0011_XX_" in filename:
            postdata_pdf = pdf_path
        elif "_F_0015_OR_" in filename or "_OR_" in filename:
            or_pdf = pdf_path
        elif "_F_0032_TS_" in filename or "_TS_" in filename:
            ts_pdf = pdf_path
        elif "_F_0015_PM_" in filename or "_PM_" in filename:
            pm_pdf = pdf_path

    # XX card is required
    if not xx_pdf:
        errors.append(ParseError(severity="error", message="No XX racecard found (required)", location="input_files"))
        return ParseReport(success=False, errors=errors, input_files=pdf_paths)

    # Extract metadata from XX filename
    filename = os.path.basename(xx_pdf)
    parts = filename.split("_")

    try:
        course_code = parts[0]
        date_str = parts[1]  # YYYYMMDD
        course_name = filename.split("_")[-1].replace(".pdf", "")
        meeting_date = datetime.strptime(date_str, "%Y%m%d").date()
    except Exception as e:
        errors.append(
            ParseError(severity="error", message=f"Failed to parse filename metadata: {str(e)}", location="filename")
        )
        return ParseReport(success=False, errors=errors, input_files=pdf_paths)

    # Parse XX card (identity backbone)
    if "_F_0003_XX_" in xx_pdf:
        races, parse_errors = parse_xx_v2_card(xx_pdf, course_name, str(meeting_date))
    else:
        races, parse_errors = parse_xx_card(xx_pdf, course_name, str(meeting_date))

    errors.extend(parse_errors)

    if not races:
        errors.append(ParseError(severity="error", message="No races parsed from XX card", location="xx_card"))
        return ParseReport(success=False, errors=errors, input_files=pdf_paths)

    # Parse standalone spotlight card (optional)
    spotlight_comments = {}
    if spotlight_pdf:
        spotlight_comments, spotlight_errors = parse_spotlight_card(spotlight_pdf, races)
        errors.extend(spotlight_errors)

    # Parse standalone postdata card (optional)
    postdata_signals = {}
    if postdata_pdf:
        postdata_signals, postdata_errors = parse_postdata_card(postdata_pdf, races)
        errors.extend(postdata_errors)

    # Parse OR card (optional)
    or_ratings = {}
    if or_pdf:
        or_ratings, or_errors = parse_or_card(or_pdf)
        errors.extend(or_errors)

    # Parse TS card (optional)
    ts_ratings = {}
    if ts_pdf:
        ts_ratings, ts_errors = parse_ts_card(ts_pdf)
        errors.extend(ts_errors)

    # Parse PM card (optional)
    pm_prices = {}
    if pm_pdf:
        pm_prices, pm_errors = parse_pm_card(pm_pdf)
        errors.extend(pm_errors)

    # Merge ratings into runners
    races = merge_ratings(
        races,
        or_ratings,
        ts_ratings,
        pm_prices,
        spotlight_comments=spotlight_comments,
        postdata_signals=postdata_signals,
    )

    # Create meeting
    meeting = Meeting(
        course_code=course_code,
        course_name=course_name,
        meeting_date=meeting_date,
        races=races,
        parsed_at=datetime.now().isoformat(),
        raw={
            "bundle_inputs": {
                "xx_backbone": xx_pdf,
                "spotlight_0016": spotlight_pdf,
                "postdata_0011": postdata_pdf,
                "or_0015": or_pdf,
                "ts_0032": ts_pdf,
                "pm_0015": pm_pdf,
            }
        },
    )

    # Validate meeting
    if validate_output:
        is_valid, validation_errors = validate_meeting(meeting)
        if not is_valid:
            for err in validation_errors:
                errors.append(ParseError(severity="error", message=err, location="validation"))
            return ParseReport(
                success=False,
                meeting=meeting,
                errors=errors,
                warnings=warnings,
                stats={
                    "races_count": len(races),
                    "runners_count": sum(len(r.runners) for r in races),
                },
                input_files=pdf_paths,
            )

    return ParseReport(
        success=True,
        meeting=meeting,
        errors=errors,
        warnings=warnings,
        stats={
            "races_count": len(races),
            "runners_count": sum(len(r.runners) for r in races),
        },
        input_files=pdf_paths,
    )


__all__ = [
    "parse_meeting",
    "Meeting",
    "Race",
    "Runner",
    "ParseReport",
    "validate_meeting",
]
