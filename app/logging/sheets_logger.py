"""
Google Sheets Logging Module
Append results to Google Sheets for real-time monitoring
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# ============================================================================
# GOOGLE SHEETS CONFIGURATION
# ============================================================================

GOOGLE_SHEETS_ENABLED = os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "")

# ============================================================================
# GOOGLE SHEETS CLIENT (Lazy Load)
# ============================================================================

_sheets_client = None

def get_sheets_client():
    """
    Get or create Google Sheets client.
    
    Returns:
        gspread client or None if disabled/unavailable
    """
    global _sheets_client
    
    if not GOOGLE_SHEETS_ENABLED:
        logger.debug("Google Sheets logging disabled")
        return None
    
    if _sheets_client is not None:
        return _sheets_client
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        if not GOOGLE_SHEETS_CREDENTIALS_PATH or not os.path.exists(GOOGLE_SHEETS_CREDENTIALS_PATH):
            logger.warning(f"Google Sheets credentials not found: {GOOGLE_SHEETS_CREDENTIALS_PATH}")
            return None
        
        # Authenticate
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_file(
            GOOGLE_SHEETS_CREDENTIALS_PATH,
            scopes=scopes
        )
        
        _sheets_client = gspread.authorize(creds)
        logger.info("Google Sheets client initialized")
        
        return _sheets_client
        
    except ImportError:
        logger.warning("gspread not installed - pip install gspread google-auth")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets client: {e}")
        return None

# ============================================================================
# APPEND TO GOOGLE SHEETS
# ============================================================================

def append_to_sheet(
    sheet_name: str,
    row_data: List[Any],
    headers: Optional[List[str]] = None
):
    """
    Append row to Google Sheet.
    
    Args:
        sheet_name: Worksheet name (e.g., "master_race_log")
        row_data: List of values to append
        headers: Optional headers to create if sheet doesn't exist
    """
    client = get_sheets_client()
    if client is None:
        logger.debug(f"Skipping Google Sheets append: {sheet_name}")
        return
    
    try:
        # Open spreadsheet
        spreadsheet = client.open_by_key(GOOGLE_SHEETS_ID)
        
        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            if headers:
                worksheet = spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1000,
                    cols=len(headers)
                )
                worksheet.append_row(headers)
                logger.info(f"Created worksheet: {sheet_name}")
            else:
                logger.error(f"Worksheet not found and no headers provided: {sheet_name}")
                return
        
        # Append row
        worksheet.append_row(row_data)
        logger.info(f"Appended to Google Sheets: {sheet_name}")
        
    except Exception as e:
        logger.error(f"Failed to append to Google Sheets: {e}")

# ============================================================================
# LOG ENGINE RESULT TO GOOGLE SHEETS
# ============================================================================

MASTER_RACE_LOG_HEADERS = [
    "run_id", "race_id", "track", "date", "off_time", "race_type", "class",
    "distance_yards", "going", "field_size", "market_snapshot_ts", "input_hash",
    "data_version", "chaos_score", "structure_class", "mof_state", "mof_confidence",
    "entropy_score", "confidence_ceiling", "top4_chassis", "win_candidate",
    "win_overlay", "stake_cap", "stake_used", "status", "kill_list_triggers",
    "result_1st", "result_2nd", "result_3rd", "result_4th", "sp_win_candidate",
    "top4_hit_count", "win_hit", "pnl_race", "pnl_cumulative", "roi_race", "logged_at"
]

def log_engine_result_to_sheets(result: Dict[str, Any]):
    """
    Log engine result to Google Sheets.
    
    Args:
        result: OracleExecutionReport JSON
    """
    if not GOOGLE_SHEETS_ENABLED:
        return
    
    race_details = result.get("race_details", {})
    audit = result.get("audit", {})
    signals = result.get("signals", {})
    decision = result.get("decision", {})
    
    # Extract signals
    chaos_score = signals.get("chaos_score", "")
    structure_class = signals.get("structure_class", "")
    mof = signals.get("MOF", {})
    entropy = signals.get("entropy", {})
    
    row_data = [
        # Race metadata
        audit.get("run_id", ""),
        race_details.get("race_id", ""),
        race_details.get("track", ""),
        race_details.get("date", ""),
        race_details.get("off_time", ""),
        race_details.get("race_type", ""),
        race_details.get("class", ""),
        race_details.get("distance_yards", ""),
        race_details.get("going", ""),
        race_details.get("field_size", ""),
        
        # Market snapshot
        audit.get("market_snapshot_ts", ""),
        audit.get("input_hash", ""),
        audit.get("data_version", ""),
        
        # Signals
        f"{chaos_score:.3f}" if isinstance(chaos_score, (int, float)) else chaos_score,
        structure_class,
        mof.get("mof_state", ""),
        f"{mof.get('mof_confidence', 0):.3f}" if isinstance(mof.get('mof_confidence'), (int, float)) else "",
        f"{entropy.get('entropy_score', 0):.3f}" if isinstance(entropy.get('entropy_score'), (int, float)) else "",
        f"{entropy.get('confidence_ceiling', 0):.3f}" if isinstance(entropy.get('confidence_ceiling'), (int, float)) else "",
        
        # Decision
        "|".join(decision.get("top4_chassis", [])),
        decision.get("win_candidate", ""),
        decision.get("win_overlay", False),
        f"{decision.get('stake_cap', 0):.2f}",
        f"{decision.get('stake_used', 0):.2f}",
        decision.get("status", ""),
        "|".join(decision.get("kill_list_triggers", [])),
        
        # Results (placeholders)
        "", "", "", "", "", "", "",
        
        # PnL (placeholders)
        "", "", "",
        
        # Audit
        datetime.utcnow().isoformat()
    ]
    
    append_to_sheet("master_race_log", row_data, headers=MASTER_RACE_LOG_HEADERS)

# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def log_engine_result(result: Dict[str, Any]):
    """
    Log engine result to Google Sheets (convenience wrapper).
    
    Args:
        result: OracleExecutionReport JSON
    """
    log_engine_result_to_sheets(result)
