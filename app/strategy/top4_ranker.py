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
from app.core.errors import validate_scores, validate_top4, V12Error

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
    
    Components (Phase 2A order):
    1. Stability modifier (±0.10)
    2. Historical stats modifier (±0.05)
    3. Market role strength (40% base, adjusted for strong favorites)
    4. Odds-derived probability (30%)
    5. Chaos adjustment (20%)
    6. Field position (10%)
    
    Phase 1.1 Anchor Guard:
    If top_prob >= 0.62 AND manipulation_risk < 0.45,
    allow anchor to regain weight to prevent Release bias.
    
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
        # Try multiple paths for odds
        odds = profile.get('odds_decimal') or profile.get('evidence', {}).get('odds', 10.0)
    else:
        runner_id = getattr(profile, 'runner_id', 'unknown')
        market_role = getattr(profile, 'market_role', None)
        if hasattr(market_role, 'value'):
            market_role = market_role.value
        odds = getattr(profile, 'evidence', {}).get('odds', 10.0)
    
    # Extract race context
    chaos_level = race_ctx.get('chaos_level', 0.5)
    field_size = race_ctx.get('field_size', 10)
    manipulation_risk = race_ctx.get('manipulation_risk', 0.5)
    
    # Phase 1.1: Anchor weight guard
    # If strong favorite (top_prob >= 0.62) AND low manipulation,
    # boost anchor weight to prevent Release bias
    implied_prob = 1.0 / odds if odds > 0 else 0.0
    is_strong_favorite = (implied_prob >= 0.62 and manipulation_risk < 0.45)
    anchor_boost = 0.10 if (is_strong_favorite and market_role in ['Liquidity_Anchor', 'ANCHOR']) else 0.0
    
    # Component 1: Market role strength (40% base + anchor boost)
    role_scores = {
        'Liquidity_Anchor': 1.0,      # Favorite
        'ANCHOR': 1.0,                 # Alias
        'Release_Horse': 0.75,         # Second fav / mid-band
        'RELEASE': 0.75,               # Alias
        'Steam': 0.70,                 # Sharp money
        'Drift_Bait': 0.40,            # Drifting
        'Spoiler': 0.30,               # Tactical
        'Noise': 0.20,                 # Outsider
        'NOISE': 0.20                  # Alias
    }
    role_score = role_scores.get(market_role, 0.5) * 0.40 + anchor_boost
    
    # Component 2: Odds-derived probability (30%)
    # (implied_prob already calculated above for anchor guard)
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
    
    # Phase 2A: Stability modifier (±0.10)
    stability_modifier = 0.0
    stability_reason = "not_available"
    if isinstance(profile, dict) and 'stability_profile' in profile:
        from app.ml.stability_clusters import get_cluster_trust_modifier
        cluster_id = profile['stability_profile'].get('cluster_id', '')
        if cluster_id:
            stability_modifier = get_cluster_trust_modifier(cluster_id)
            stability_reason = cluster_id
    
    # Phase 2A: Historical stats modifier (±0.05)
    historical_modifier = 0.0
    historical_reason = "not_available"
    if isinstance(profile, dict) and 'historical_stats' in profile:
        from app.ml.historical_stats import calculate_historical_modifier
        hist_result = calculate_historical_modifier(
            profile['historical_stats'],
            use_trainer=True,
            use_jockey=True,
            use_combo=False
        )
        historical_modifier = hist_result['total_modifier']
        historical_reason = hist_result['reason']
    
    # Total score
    total = (
        stability_modifier +
        historical_modifier +
        role_score +
        odds_score +
        chaos_boost +
        field_score
    )
    
    components = {
        'stability': stability_modifier,
        'historical': historical_modifier,
        'role': role_score,
        'odds': odds_score,
        'chaos': chaos_boost,
        'field': field_score,
        'anchor_guard': anchor_boost,  # Phase 1.1
        'stability_reason': stability_reason,
        'historical_reason': historical_reason
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
    
    # Phase 1.1: Validate score contract
    field_size = len(opponent_profiles)
    validate_scores(score_breakdowns, field_size)
    
    # Phase 1.1: Validate Top-4 output
    top4_ids = [s['runner_id'] for s in scores[:4]]
    validate_top4(top4_ids, field_size)
    
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
