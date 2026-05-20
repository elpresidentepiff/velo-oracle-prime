#!/usr/bin/env python3
"""
VÉLØ HFS Pure Feature Functions
Deterministic, side-effect-free functions for core feature calculation.
"""

import math
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

logger = logging.getLogger("hfs.pure_features")

def compute_mpi_from_pre_race_odds(odds_decimal_list: List[float]) -> float:
    """
    Compute Manipulation Probability Index (MPI) from a field of pre-race odds.
    
    Logic:
    - High market overround indicates uncertainty/manipulation.
    - Tight price clustering at the top (multiple short-priced runners) increases MPI.
    - Returns a score between 0.0 and 100.0.
    """
    if not odds_decimal_list or len(odds_decimal_list) < 2:
        return 50.0  # Neutral/Unknown

    # Filter out invalid odds
    valid_odds = [o for o in odds_decimal_list if o > 1.0]
    if len(valid_odds) < 2:
        return 50.0

    # 1. Market Overround (Bookmaker's margin)
    # 100% = fair market, >115% = high margin/uncertainty
    implied_probs = [1.0 / o for o in valid_odds]
    overround = sum(implied_probs)
    
    overround_factor = max(0.0, (overround - 1.0) / 0.5) # Normalized over fair, 0.5 margin = 1.0
    
    # 2. Top-End Compression (Price clustering)
    # If the standard deviation of the top 3 runners is low, and prices are short, MPI increases.
    sorted_probs = sorted(implied_probs, reverse=True)
    top_3 = sorted_probs[:3]
    
    avg_top_prob = sum(top_3) / len(top_3)
    if avg_top_prob > 0.2: # Significant favorites
        # Use variance as a measure of "indecision" at the top
        variance = sum((p - avg_top_prob)**2 for p in top_3) / len(top_3)
        compression_factor = max(0.0, 1.0 - (math.sqrt(variance) / 0.1)) # Lower variance = Higher compression
    else:
        compression_factor = 0.0

    # Combine factors: (Overround weighting 60%, Compression weighting 40%)
    mpi_score = (overround_factor * 60.0) + (compression_factor * 40.0)
    
    return max(0.0, min(mpi_score, 100.0))

def compute_chaos_bloom_from_mpi(mpi_score: float, field_size: int) -> float:
    """
    Compute Chaos Bloom (Environmental Volatility).
    
    Logic:
    - Base chaos scales with field size (more runners = more traffic/interference).
    - Market uncertainty (MPI) acts as a multiplier.
    - Returns a score between 0.0 and 100.0.
    """
    if field_size <= 0:
        return 0.0
        
    # Base Factor: log-scaled field size
    # 8 runners ~ 30, 16 runners ~ 40, 24 runners ~ 46
    base_factor = math.log2(field_size) * 10.0
    
    # MPI Adjustment: scale by (1 + mpi/100)
    # If MPI is 100 (extreme uncertainty), chaos doubles.
    mpi_multiplier = 1.0 + (mpi_score / 100.0)
    
    chaos_score = base_factor * mpi_multiplier
    
    # Boost for large fields + high MPI
    if field_size > 14 and mpi_score > 60:
        chaos_score += 15.0

    return max(0.0, min(chaos_score, 100.0))

def validate_odds_temporal_safety(odds_ts: datetime, execution_ts: datetime) -> bool:
    """
    Strict temporal safety check to prevent data leakage.
    Returns True if odds were recorded at or before the time of execution.
    """
    if not isinstance(odds_ts, datetime) or not isinstance(execution_ts, datetime):
        logger.error("Invalid timestamp types provided to temporal safety check")
        return False
        
    return odds_ts <= execution_ts

def build_feature_provenance(version: str, source: str, **kwargs) -> Dict[str, Any]:
    """
    Generate a standardized _meta block for feature provenance.
    """
    meta = {
        "version": version,
        "source": source,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "method": "pure_function_v1"
    }
    meta.update(kwargs)
    return meta
