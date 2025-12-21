"""
VELO Top-4 Ranker (Patch 4)

Score-based ranking that combines:
- Market role strength
- Odds-derived signals
- Chaos adjustment
- Field position

NO POSITIONAL DEFAULTS - every runner gets a real score.

Author: VELO Team
Version: 1.0 (Phase 1)
Date: December 21, 2025
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Score breakdown for a runner."""
    total: float
    components: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'total': self.total,
            'components': self.components
        }


def calculate_runner_score(
    profile: any,
    race_ctx: Dict
) -> ScoreBreakdown:
    """
    Calculate composite score for a runner.
    
    Components:
    1. Market role strength (40%)
    2. Odds-derived probability (30%)
    3. Chaos adjustment (20%)
    4. Field position (10%)
    
    Args:
        profile: OpponentProfile (object or dict)
        race_ctx: Race context with chaos_level, field_size, etc.
        
    Returns:
        ScoreBreakdown with total and components
    """
    # Extract profile data (handle both object and dict)
    if isinstance(profile, dict):
        runner_id = profile.get('runner_id', 'unknown')
        market_role = profile.get('market_role', 'Noise')
        odds = profile.get('evidence', {}).get('odds', 10.0)
    else:
        runner_id = getattr(profile, 'runner_id', 'unknown')
        market_role = getattr(profile, 'market_role', None)
        if hasattr(market_role, 'value'):
            market_role = market_role.value
        odds = getattr(profile, 'evidence', {}).get('odds', 10.0)
    
    # Extract race context
    chaos_level = race_ctx.get('chaos_level', 0.5)
    field_size = race_ctx.get('field_size', 10)
    
    # Component 1: Market role strength (40%)
    role_scores = {
        'Liquidity_Anchor': 1.0,      # Favorite
        'Release_Horse': 0.75,         # Second fav / mid-band
        'Steam': 0.70,                 # Sharp money
        'Drift_Bait': 0.40,            # Drifting
        'Spoiler': 0.30,               # Tactical
        'Noise': 0.20                  # Outsider
    }
    role_score = role_scores.get(market_role, 0.5) * 0.40
    
    # Component 2: Odds-derived probability (30%)
    implied_prob = 1.0 / odds if odds > 0 else 0.0
    # Normalize to 0-1 range (cap at 80% prob)
    odds_score = min(implied_prob / 0.80, 1.0) * 0.30
    
    # Component 3: Chaos adjustment (20%)
    # In high chaos, favor mid-range odds (Release horses)
    # In low chaos, favor favorites (Anchors)
    if chaos_level > 0.6:
        # High chaos: boost mid-range
        if 3.0 <= odds <= 8.0:
            chaos_boost = 0.20
        elif odds < 3.0:
            chaos_boost = 0.10  # Penalize favorites in chaos
        else:
            chaos_boost = 0.05
    else:
        # Low chaos: boost favorites
        if odds < 3.0:
            chaos_boost = 0.20
        elif 3.0 <= odds <= 8.0:
            chaos_boost = 0.15
        else:
            chaos_boost = 0.05
    
    # Component 4: Field position (10%)
    # Smaller fields = higher scores (less competition)
    field_score = max(0.0, (20 - field_size) / 20.0) * 0.10
    
    # Total score
    total = role_score + odds_score + chaos_boost + field_score
    
    components = {
        'role': role_score,
        'odds': odds_score,
        'chaos': chaos_boost,
        'field': field_score
    }
    
    return ScoreBreakdown(total=total, components=components)


def rank_top4(
    opponent_profiles: List[any],
    race_ctx: Dict
) -> Tuple[List[any], Dict[str, ScoreBreakdown]]:
    """
    Rank runners by composite score and return top 4.
    
    CRITICAL: This is score-based, NOT positional.
    Top-4 order is determined by total score, not runner ID.
    
    Args:
        opponent_profiles: List of OpponentProfile objects
        race_ctx: Race context
        
    Returns:
        (top4_profiles, score_breakdowns)
    """
    logger.info(f"Ranking {len(opponent_profiles)} runners by composite score")
    
    # Calculate scores for all runners
    scores = []
    score_breakdowns = {}
    
    for profile in opponent_profiles:
        # Get runner_id
        if isinstance(profile, dict):
            runner_id = profile.get('runner_id', 'unknown')
        else:
            runner_id = getattr(profile, 'runner_id', 'unknown')
        
        # Calculate score
        breakdown = calculate_runner_score(profile, race_ctx)
        score_breakdowns[str(runner_id)] = breakdown
        
        scores.append({
            'profile': profile,
            'runner_id': runner_id,
            'score': breakdown.total
        })
    
    # Sort by score (descending)
    scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Extract top 4
    top4_profiles = [s['profile'] for s in scores[:4]]
    
    # Log rankings
    logger.info("Top-4 Rankings:")
    for i, s in enumerate(scores[:4], 1):
        rid = s['runner_id']
        score = s['score']
        bd = score_breakdowns[str(rid)]
        logger.info(f"  #{i}: {rid} | score={score:.3f} | role={bd.components['role']:.3f} odds={bd.components['odds']:.3f} chaos={bd.components['chaos']:.3f}")
    
    return top4_profiles, score_breakdowns


if __name__ == "__main__":
    # Test with example data
    from app.ml.opponent_models import OpponentProfile, MarketRole, IntentClass, StableTactic
    
    test_profiles = [
        OpponentProfile(
            runner_id='r1',
            horse_name='Aqua Bleu',
            intent_class=IntentClass.UNKNOWN,
            market_role=MarketRole.LIQUIDITY_ANCHOR,
            stable_tactic=StableTactic.SOLO,
            confidence=0.7,
            evidence={'odds': 1.44}
        ),
        OpponentProfile(
            runner_id='r2',
            horse_name='Majeur Alien',
            intent_class=IntentClass.UNKNOWN,
            market_role=MarketRole.RELEASE_HORSE,
            stable_tactic=StableTactic.SOLO,
            confidence=0.7,
            evidence={'odds': 3.75}
        ),
        OpponentProfile(
            runner_id='r3',
            horse_name='Network Gold',
            intent_class=IntentClass.UNKNOWN,
            market_role=MarketRole.RELEASE_HORSE,
            stable_tactic=StableTactic.SOLO,
            confidence=0.7,
            evidence={'odds': 9.0}
        ),
        OpponentProfile(
            runner_id='r4',
            horse_name='Pink n Purple',
            intent_class=IntentClass.UNKNOWN,
            market_role=MarketRole.RELEASE_HORSE,
            stable_tactic=StableTactic.SOLO,
            confidence=0.7,
            evidence={'odds': 19.0}
        ),
        OpponentProfile(
            runner_id='r5',
            horse_name='Network Rgb',
            intent_class=IntentClass.UNKNOWN,
            market_role=MarketRole.NOISE,
            stable_tactic=StableTactic.SOLO,
            confidence=0.7,
            evidence={'odds': 29.0}
        ),
        OpponentProfile(
            runner_id='r6',
            horse_name='Callero',
            intent_class=IntentClass.UNKNOWN,
            market_role=MarketRole.NOISE,
            stable_tactic=StableTactic.SOLO,
            confidence=0.7,
            evidence={'odds': 34.0}
        ),
    ]
    
    race_ctx = {
        'race_id': 'TEST_001',
        'chaos_level': 0.43,
        'manipulation_risk': 0.54,
        'field_size': 6
    }
    
    top4, breakdowns = rank_top4(test_profiles, race_ctx)
    
    print("\nTop-4 Results:")
    for i, p in enumerate(top4, 1):
        rid = p.runner_id
        bd = breakdowns[rid]
        print(f"#{i}: {p.horse_name} ({rid}) - Score: {bd.total:.3f}")
        print(f"     Components: {bd.components}")
