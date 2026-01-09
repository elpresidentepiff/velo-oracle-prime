"""
Racing Post PDF Parser - Normalization Utilities
Distance canonicalization, name normalization, weight parsing.
"""

import re
from typing import Optional, Tuple


# Distance canonicalization map: Racing Post distance string -> yards
DISTANCE_MAP = {
    # Sprints (5f - 7f)
    "5f": 1100,
    "6f": 1320,
    "7f": 1540,
    
    # Mile distances
    "1m": 1760,
    "1m 1f": 1980,
    "1m 2f": 2200,
    "1m 3f": 2420,
    "1m 4f": 2640,
    "1m 5f": 2860,
    "1m 6f": 3080,
    "1m 7f": 3300,
    
    # Extended distances
    "2m": 3520,
    "2m 1f": 3740,
    "2m 2f": 3960,
    "2m 3f": 4180,
    "2m 4f": 4400,
    "2m 5f": 4620,
    "2m 6f": 4840,
    
    # Marathon distances
    "3m": 5280,
    "3m 1f": 5500,
    "3m 2f": 5720,
    "3m 3f": 5940,
    "3m 4f": 6160,
    "3m 5f": 6380,
    "3m 6f": 6600,
    
    # Longer distances
    "4m": 7040,
    "4m 1f": 7260,
    "4m 2f": 7480,
    "4m 3f": 7700,
    "4m 4f": 7920,
}


def parse_distance(distance_str: str) -> Tuple[Optional[int], Optional[float], Optional[int]]:
    """
    Convert Racing Post distance string to yards (canonical), furlongs, and meters.
    
    Args:
        distance_str: Distance string like "6f", "1m 2f", "2m 4f"
        
    Returns:
        Tuple of (yards, furlongs, meters) or (None, None, None) if unmapped
        
    Examples:
        >>> parse_distance("6f")
        (1320, 6.0, 1207)
        >>> parse_distance("1m 2f")
        (2200, 10.0, 2012)
    """
    # Normalize: lowercase, strip whitespace
    normalized = distance_str.strip().lower()
    
    # Look up in distance map
    if normalized in DISTANCE_MAP:
        yards = DISTANCE_MAP[normalized]
        furlongs = yards / 220.0  # 1 furlong = 220 yards
        meters = int(yards * 0.9144)  # 1 yard = 0.9144 meters
        return (yards, round(furlongs, 2), meters)
    
    # Try to parse dynamic distances (e.g., "1m 3f 110y")
    # Pattern: optional miles, optional furlongs, optional yards
    match = re.match(r"(?:(\d+)m\s*)?(?:(\d+)f\s*)?(?:(\d+)y)?", normalized)
    if match:
        miles_str, furlongs_str, yards_str = match.groups()
        
        total_yards = 0
        if miles_str:
            total_yards += int(miles_str) * 1760  # 1 mile = 1760 yards
        if furlongs_str:
            total_yards += int(furlongs_str) * 220  # 1 furlong = 220 yards
        if yards_str:
            total_yards += int(yards_str)
        
        if total_yards > 0:
            furlongs = total_yards / 220.0
            meters = int(total_yards * 0.9144)
            return (total_yards, round(furlongs, 2), meters)
    
    # Unmapped distance
    return (None, None, None)


def normalize_horse_name(name: str) -> str:
    """
    Normalize horse name: uppercase, strip whitespace, remove special chars.
    
    Args:
        name: Raw horse name from PDF
        
    Returns:
        Normalized horse name
        
    Examples:
        >>> normalize_horse_name("  Brave Empire ")
        "BRAVE EMPIRE"
        >>> normalize_horse_name("Sea The Stars (IRE)")
        "SEA THE STARS"
    """
    # Strip whitespace
    name = name.strip()
    
    # Remove country codes like (IRE), (FR), (USA)
    name = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name)
    
    # Uppercase
    name = name.upper()
    
    # Remove extra whitespace
    name = " ".join(name.split())
    
    return name


def parse_weight(weight_str: str) -> Optional[str]:
    """
    Parse weight string from PDF.
    
    Args:
        weight_str: Weight like "9-8", "10-0", "8-12"
        
    Returns:
        Normalized weight string or None
        
    Examples:
        >>> parse_weight("9-8")
        "9-8"
        >>> parse_weight("10-0")
        "10-0"
    """
    # Pattern: stone-pounds like "9-8"
    if re.match(r"\d{1,2}-\d{1,2}", weight_str):
        return weight_str.strip()
    
    return None


def is_placeholder_name(name: str) -> bool:
    """
    Check if horse name is a placeholder (TBD, RUNNER A, etc.).
    
    Args:
        name: Horse name to check
        
    Returns:
        True if placeholder, False otherwise
    """
    # Normalize for comparison
    normalized = name.strip().upper()
    
    # Known placeholders
    placeholders = {
        "TBD",
        "RUNNER A",
        "RUNNER B", 
        "RUNNER C",
        "RUNNER D",
        "RUNNER E",
        "RUNNER F",
        "UNKNOWN",
        "-",
        "N/A",
        "NA",
        "TBA",
        "TO BE ADVISED",
    }
    
    return normalized in placeholders


def extract_age_from_line(line: str) -> Optional[int]:
    """
    Extract age from a line (looking for single digit 2-15).
    Used to parse the age line in XX racecards.
    
    Args:
        line: Text line from PDF
        
    Returns:
        Age as integer or None
    """
    # Look for standalone numbers 2-15
    matches = re.findall(r"\b(\d{1,2})\b", line)
    
    for match in matches:
        age = int(match)
        if 2 <= age <= 15:
            return age
    
    return None


def extract_days_since_run(line: str) -> Optional[int]:
    """
    Extract days since run from form line.
    Usually appears after form figures, e.g., "09353- 21 D 5"
    
    Args:
        line: Form line text from PDF
        
    Returns:
        Days as integer or None
    """
    # Pattern: number followed by "D" (for days)
    # e.g., "21 D 5" -> 21
    match = re.search(r"(\d+)\s*D\s*\d*", line)
    if match:
        return int(match.group(1))
    
    return None
