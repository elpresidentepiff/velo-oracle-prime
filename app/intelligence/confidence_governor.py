"""
VELO Confidence Governor
Downgrades confidence when structural conditions undermine signal reliability.
"""
from typing import Dict, Any, List

# Race regime classification
REGIME_ORDERLY = "ORDERLY"
REGIME_COMPRESSED = "COMPRESSED"
REGIME_CHAOS = "CHAOS"
REGIME_NOVICE = "NOVICE_UNKNOWN"
REGIME_HANDICAP_PLOT = "HANDICAP_PLOT_ZONE"
REGIME_LIQUIDITY_TRAP = "LIQUIDITY_TRAP"


def classify_race_regime(race: Dict, runners: List[Dict], top_scores: List[float]) -> str:
    field_size = len(runners)
    going = (race.get('going') or '').upper()
    race_type = (race.get('race_type') or race.get('type') or '').upper()

    # Chaos: large field + extreme going
    if field_size >= 14 and any(x in going for x in ['HEAVY', 'SOFT']):
        return REGIME_CHAOS

    # Chaos: NH flat or novice hurdle with inexperienced field
    if 'NH FLAT' in race_type or ('NOVICE' in race_type and field_size >= 8):
        return REGIME_NOVICE

    # Compressed: top 3 scores within 3 points of each other
    if len(top_scores) >= 3 and (max(top_scores[:3]) - min(top_scores[:3])) < 3.0:
        return REGIME_COMPRESSED

    # Handicap plot zone: large handicap field
    if 'HANDICAP' in race_type and field_size >= 12:
        return REGIME_HANDICAP_PLOT

    # Liquidity trap: very short favourite in large field
    favs = [r for r in runners if r.get('is_fav') or r.get('raw', {}).get('is_fav')]
    if favs:
        fav_odds = favs[0].get('odds') or favs[0].get('raw', {}).get('odds') or 10
        if fav_odds < 2.0 and field_size >= 8:
            return REGIME_LIQUIDITY_TRAP

    return REGIME_ORDERLY


def govern_confidence(
    raw_confidence: str,
    regime: str,
    top_score: float,
    field_size: int,
    decoy_flag: float = 0.0,
    going: str = '',
) -> str:
    """
    Downgrade confidence based on structural conditions.

    Inputs:
        raw_confidence: 'HIGH', 'MEDIUM', 'LOW'
        regime: from classify_race_regime()
        top_score: top model score (0-100)
        field_size: number of runners
        decoy_flag: doctrine decoy_support_flag (0 or 1)
        going: going string

    Returns:
        Final confidence: 'HIGH', 'HIGH-RISK', 'MEDIUM', 'CHAOS', 'LOW'
    """
    going_upper = going.upper()
    extreme_going = any(x in going_upper for x in ['HEAVY', 'VERY SOFT'])

    # Chaos regime always returns CHAOS
    if regime in (REGIME_CHAOS, REGIME_NOVICE):
        return 'CHAOS'

    # Decoy flag active — downgrade HIGH to HIGH-RISK
    if decoy_flag >= 1.0 and raw_confidence == 'HIGH':
        return 'HIGH-RISK'

    # Compressed regime + not a clear leader — downgrade
    if regime == REGIME_COMPRESSED and top_score < 65:
        return 'MEDIUM'

    # Large field penalty
    if field_size >= 16 and raw_confidence == 'HIGH':
        return 'HIGH-RISK'

    # Extreme going penalty
    if extreme_going and raw_confidence == 'HIGH':
        return 'HIGH-RISK'

    # Handicap plot zone — cap at MEDIUM unless very high score
    if regime == REGIME_HANDICAP_PLOT and top_score < 70:
        return 'MEDIUM'

    return raw_confidence
