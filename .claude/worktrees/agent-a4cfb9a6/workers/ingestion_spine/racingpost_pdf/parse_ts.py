"""
Racing Post PDF Parser - TS Parser
Parse F_0032_TS files (Timeform Speed).
"""

from typing import List, Dict
from .types import ParseError


def parse_ts_card(pdf_path: str) -> tuple[Dict[str, Dict[str, int]], List[ParseError]]:
    """
    Parse TS (Timeform Speed) PDF.
    
    Returns:
        Tuple of (ratings_map, errors)
        ratings_map: {race_id: {runner_name: ts_rating}}
    """
    # Stub implementation - would parse TS ratings from PDF
    # For now, return empty map
    return {}, []
