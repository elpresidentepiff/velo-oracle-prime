"""
Racing Post PDF Parser - PM Parser
Parse F_0015_PM files (Price/Market).
"""

from typing import List, Dict
from .types import ParseError


def parse_pm_card(pdf_path: str) -> tuple[Dict[str, Dict[str, float]], List[ParseError]]:
    """
    Parse PM (Price/Market) PDF.
    
    Returns:
        Tuple of (prices_map, errors)
        prices_map: {race_id: {runner_name: price}}
    """
    # Stub implementation - would parse prices from PDF
    # For now, return empty map
    return {}, []
