"""
Racing Post PDF Parser
One source of truth: canonical JSON from validated PDF parse.

Usage:
    from racingpost_pdf import parse_meeting
    
    meeting = parse_meeting(pdf_paths)
    
Parse flow:
    1. Parse XX card (identity backbone: races + runners)
    2. Enrich with OR/TS/PM (ratings, speed, prices)
    3. Merge by (race_id, runner_number)
    4. Validate (hard gates)
    5. Return Meeting object
"""

import os
import re
from datetime import datetime
from typing import List, Optional

from .types import Meeting, ParseReport, ParseError
from .parse_xx import parse_xx_card
from .parse_or import parse_or_card
from .parse_ts import parse_ts_card
from .parse_pm import parse_pm_card
from .merge import merge_ratings
from .validate import validate_meeting


def parse_meeting(pdf_paths: List[str], validate_output: bool = True) -> ParseReport:
    """
    Parse Racing Post PDFs and return canonical meeting data.
    
    Args:
        pdf_paths: List of PDF file paths (XX, OR, TS, PM)
        validate_output: Whether to run validation gates (default: True)
        
    Returns:
        ParseReport with meeting data and any errors
        
    Raises:
        ValueError: If no XX card found (required)
    """
    errors = []
    warnings = []
    
    # Categorize PDFs by type
    xx_pdf = None
    or_pdf = None
    ts_pdf = None
    pm_pdf = None
    
    for pdf_path in pdf_paths:
        filename = os.path.basename(pdf_path)
        
        if "_F_0012_XX_" in filename or "_XX_" in filename:
            xx_pdf = pdf_path
        elif "_F_0015_OR_" in filename or "_OR_" in filename:
            or_pdf = pdf_path
        elif "_F_0032_TS_" in filename or "_TS_" in filename:
            ts_pdf = pdf_path
        elif "_F_0015_PM_" in filename or "_PM_" in filename:
            pm_pdf = pdf_path
    
    # XX card is required
    if not xx_pdf:
        errors.append(ParseError(
            severity="error",
            message="No XX racecard found (required)",
            location="input_files"
        ))
        return ParseReport(
            success=False,
            errors=errors,
            input_files=pdf_paths
        )
    
    # Extract metadata from XX filename
    # Pattern: WOL_20260109_00_00_F_0012_XX_Wolverhampton.pdf
    filename = os.path.basename(xx_pdf)
    parts = filename.split("_")
    
    try:
        course_code = parts[0]
        date_str = parts[1]  # YYYYMMDD
        # Find course name (last part before .pdf)
        course_name = filename.split("_")[-1].replace(".pdf", "")
        
        # Parse date
        meeting_date = datetime.strptime(date_str, "%Y%m%d").date()
    except Exception as e:
        errors.append(ParseError(
            severity="error",
            message=f"Failed to parse filename metadata: {str(e)}",
            location="filename"
        ))
        return ParseReport(
            success=False,
            errors=errors,
            input_files=pdf_paths
        )
    
    # Parse XX card (identity backbone)
    races, parse_errors = parse_xx_card(xx_pdf, course_name, str(meeting_date))
    errors.extend(parse_errors)
    
    if not races:
        errors.append(ParseError(
            severity="error",
            message="No races parsed from XX card",
            location="xx_card"
        ))
        return ParseReport(
            success=False,
            errors=errors,
            input_files=pdf_paths
        )
    
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
    races = merge_ratings(races, or_ratings, ts_ratings, pm_prices)
    
    # Create meeting
    meeting = Meeting(
        course_code=course_code,
        course_name=course_name,
        meeting_date=meeting_date,
        races=races,
        parsed_at=datetime.now().isoformat()
    )
    
    # Validate meeting (hard gates)
    if validate_output:
        is_valid, validation_errors = validate_meeting(meeting)
        
        if not is_valid:
            # Convert validation errors to ParseError objects
            for err in validation_errors:
                errors.append(ParseError(
                    severity="error",
                    message=err,
                    location="validation"
                ))
            
            return ParseReport(
                success=False,
                meeting=meeting,
                errors=errors,
                warnings=warnings,
                stats={
                    "races_count": len(races),
                    "runners_count": sum(len(r.runners) for r in races),
                    "validation_errors": len(validation_errors)
                },
                input_files=pdf_paths
            )
    
    # Success
    return ParseReport(
        success=True,
        meeting=meeting,
        errors=errors,
        warnings=warnings,
        stats={
            "races_count": len(races),
            "runners_count": sum(len(r.runners) for r in races),
        },
        input_files=pdf_paths
    )


__all__ = [
    "parse_meeting",
    "Meeting",
    "Race",
    "Runner",
    "ParseReport",
    "validate_meeting",
]
