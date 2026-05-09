"""
distance_normalizer.py

Converts any distance representation to the canonical string key used by
Racing API jockey/trainer analysis tables (e.g. "6f", "6.5f", "16f").

Racing API analysis tables store dist_f as strings like "6f", "6.5f", "16f".
racing_horse_runs.distance_f stores float (e.g. 6.5, 16.0).
races.distance_f stores integers that may be tenths or full furlongs.
"""
from __future__ import annotations


def float_to_dist_key(distance_f: float | int | None) -> str | None:
    """Convert float furlongs to Racing API dist_f string key.

    6.0  → "6f"
    6.5  → "6.5f"
    16.0 → "16f"
    Returns None for null/zero input.
    """
    if distance_f is None:
        return None
    v = float(distance_f)
    if v <= 0:
        return None
    if v == int(v):
        return f"{int(v)}f"
    # Keep one decimal place, strip trailing zeros
    s = f"{v:.1f}".rstrip("0")
    return f"{s}f"


def normalize_distance(raw) -> float | None:
    """Normalize any raw distance representation to float furlongs.

    Handles:
    - float/int from racing_horse_runs.distance_f  → return as-is
    - string "6f", "6.5f"                          → parse
    - string "1m2f"                                → convert
    - string "2m4f110y"                            → convert (yards → furlongs)
    - races.distance_f integer (tenths encoding)   → detect and divide
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        v = float(raw)
        if v <= 0:
            return None
        # Heuristic: racing_horse_runs stores real furlongs (< 40).
        # races table may store tenths (e.g. 120 = 12.0f, 60 = 6.0f).
        # Values >= 30 that aren't plausible real distances are tenths.
        if v >= 30:
            v = v / 10.0
        return v if v > 0 else None
    if isinstance(raw, str):
        return _parse_str_distance(raw.strip())
    return None


def _parse_str_distance(s: str) -> float | None:
    """Parse string distance to float furlongs."""
    if not s:
        return None
    s_lower = s.lower()
    # Simple "Xf" or "X.Xf"
    if s_lower.endswith("f") and "m" not in s_lower and "y" not in s_lower:
        try:
            return float(s_lower[:-1])
        except ValueError:
            return None
    # "XmYf" or "XmYfZy" patterns
    total = 0.0
    # miles
    if "m" in s_lower:
        parts = s_lower.split("m", 1)
        try:
            total += float(parts[0]) * 8.0
        except ValueError:
            return None
        remainder = parts[1]
    else:
        remainder = s_lower
    # furlongs
    if "f" in remainder:
        f_parts = remainder.split("f", 1)
        try:
            total += float(f_parts[0]) if f_parts[0] else 0.0
        except ValueError:
            pass
        remainder = f_parts[1]
    # yards (220y = 1f)
    if "y" in remainder:
        y_parts = remainder.split("y", 1)
        try:
            total += float(y_parts[0]) / 220.0
        except ValueError:
            pass
    return total if total > 0 else None
