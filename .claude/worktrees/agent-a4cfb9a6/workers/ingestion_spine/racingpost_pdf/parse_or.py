"""
Racing Post PDF Parser - OR Parser
Parse F_0015_OR files (Official Ratings).
"""

from typing import List, Dict
from .types import ParseError


def parse_or_card(pdf_path: str) -> tuple[Dict[str, Dict[str, int]], List[ParseError]]:
    """
    Parse OR (Official Ratings) PDF.
    
    Returns:
        Tuple of (ratings_map, errors)
        ratings_map: {race_id: {runner_name: or_rating}}
    """
    # Stub implementation - would parse OR ratings from PDF
    # For now, return empty map
    return {}, []
