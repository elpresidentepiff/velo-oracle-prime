"""
Racing Post PDF Parser - TS Parser
Parse F_0032_TS files (Timeform Speed).
"""

from .parse_or import _parse_rating_card
from .types import ParseError


def parse_ts_card(pdf_path: str) -> tuple[dict[str, dict[str, dict[str, int | None]]], list[ParseError]]:
    """
    Parse TS (Timeform Speed) PDF.

    Returns:
        Tuple of (ratings_map, errors)
        ratings_map: {race_id: {runner_name: ts_payload}}
    """
    return _parse_rating_card(pdf_path, prefix="ts")
