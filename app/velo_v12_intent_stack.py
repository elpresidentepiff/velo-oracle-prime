# velo_v12_intent_stack.py
# V12 Market-Intent Stack - Deterministic layer (pure functions, no I/O)
# Spec: VELO_V12_INTENT_STACK_SPEC v12.0.0-alpha

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import math
import uuid
from datetime import datetime

def clamp01(x: float) -> float:
    """Clamp value to [0, 1] range."""
    return max(0.0, min(1.0, x))

def sigmoid(x: float) -> float:
    """Numerically safe sigmoid function."""
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)

def input_hash(payload: Dict[str, Any]) -> str:
    """Generate deterministic hash of input payload."""
    blob = str(sorted(payload.items())).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]

# ============================================================================
# DATA CONTRACTS
# ============================================================================

@dataclass(frozen=True)
class OddsPoint:
    """Market odds snapshot at a specific timestamp."""
    ts: str
    odds: float

@dataclass
class Runner:
    """Runner (horse) data contract."""
    runner_id: str
    horse: str
    weight_lbs: int
    jockey: str
    trainer: str
    odds_live: float
    claims_lbs: int = 0
    stall: Optional[int] = None
    OR: Optional[int] = None
    TS: Optional[int] = None
    RPR: Optional[int] = None
    owner: Optional[str] = None
    headgear: Optional[str] = None
    run_style: Optional[str] = None
    odds_timeline: Optional[List[OddsPoint]] = None
    place_odds_live: Optional[float] = None
    place_odds_timeline: Optional[List[OddsPoint]] = None
    comments: Optional[str] = None
    last_runs: Optional[List[Dict[str, Any]]] = None

@dataclass
class Race:
    """Race data contract."""
    race_id: str
    track: str
    date: str
    off_time: str
    race_type: str
    klass: Any  # class can be string or int
    distance_yards: int
    going: str
    rail_moves: Optional[str]
    field_size: int
    market_snapshot_ts: str
    nr_list: List[str]
    runners: List[Runner]

# ============================================================================
# RIC+ VALIDATION GATE
# ============================================================================

def validate_RIC_plus(race: Race) -> Tuple[bool, Optional[str]]:
    """
    Validate Race Integrity Contract Plus (RIC+).
    
    Hard constraints:
    - All required race fields must be present
    - At least one runner must exist
    - All required runner fields must be present
    - At least one rating (OR/TS/RPR) must exist across all runners
    
    Returns:
        (ok, error_code) tuple
    """
    required_race = [
        "race_id", "track", "date", "off_time", "race_type", "klass",
        "distance_yards", "going", "field_size", "market_snapshot_ts",
        "runners", "nr_list"
    ]
    
    for f in required_race:
        val = getattr(race, f, None)
        # Allow empty list for nr_list (no non-runners is valid)
        if f == "nr_list" and val is not None:
            continue
        if val in (None, "", []):
            return False, f"INPUT_MISSING:{f}"
    
    if not race.runners:
        return False, "FIELD_INCOMPLETE:RUNNERS"
    
    for r in race.runners:
        for f in ["horse", "weight_lbs", "jockey", "trainer", "odds_live", "claims_lbs"]:
            val = getattr(r, f, None)
            if val in (None, "", []):
                return False, f"INPUT_MISSING:RUNNER_FIELD:{f}"
    
    # Require at least one rating exists across all runners
    if all((rr.OR is None and rr.TS is None and rr.RPR is None) for rr in race.runners):
        return False, "INPUT_MISSING:RATINGS_ALL"
    
    return True, None

# ============================================================================
# CHAOS / STRUCTURE CLASSIFIER
# ============================================================================

def compute_chaos_score(
    race: Race,
    stable_corr_proxy: float = 0.3,
    novice_low_info: float = 0.0,
    pace_density_proxy: float = 0.5
) -> Dict[str, Any]:
    """
    Compute chaos score and structure classification.
    
    Formula: chaos = 0.30*field_size_norm + 0.25*novice_low_info + 
                     0.20*pace_density_proxy + 0.25*stable_corr_proxy
    
    Structure classes:
    - CHAOS: chaos >= 0.70
    - MIXED: 0.45 <= chaos < 0.70
    - STRUCTURE: chaos < 0.45
    
    Returns:
        {chaos_score, structure_class, field_size_norm}
    """
    field_size_norm = clamp01(race.field_size / 16.0)
    chaos = clamp01(
        0.30 * field_size_norm +
        0.25 * novice_low_info +
        0.20 * pace_density_proxy +
        0.25 * stable_corr_proxy
    )
    
    if chaos >= 0.70:
        sclass = "CHAOS"
    elif chaos >= 0.45:
        sclass = "MIXED"
    else:
        sclass = "STRUCTURE"
    
    return {
        "chaos_score": chaos,
        "structure_class": sclass,
        "field_size_norm": field_size_norm
    }

# ============================================================================
# MARKET ROLE CLASSIFIER
# ============================================================================

def classify_market_roles(
    race: Race,
    stability: Dict[str, float],
    yard_hot: Dict[str, float]
) -> Dict[str, str]:
    """
    Classify market roles for each runner.
    
    Roles:
    - ANCHOR: top-2 by price AND price <= 4.0
    - RELEASE: odds in 5.5-16 AND stability high AND yard hot
    - SHADOW: drifted into 12-25 with stability
    
    Returns:
        {runner_id: role} mapping
    """
    odds_sorted = sorted(
        [(r.runner_id, r.odds_live) for r in race.runners],
        key=lambda x: x[1]
    )
    top2 = set([x[0] for x in odds_sorted[:2]])
    
    role = {}
    for r in race.runners:
        if r.runner_id in top2 and r.odds_live <= 4.0:
            role[r.runner_id] = "ANCHOR"
        elif (5.5 <= r.odds_live <= 16.0 and
              stability.get(r.runner_id, 0.5) >= 0.65 and
              yard_hot.get(r.trainer, 0.5) >= 0.55):
            role[r.runner_id] = "RELEASE"
        else:
            # Shadow if drifted but stable
            if r.odds_live >= 12.0 and stability.get(r.runner_id, 0.5) >= 0.65:
                role[r.runner_id] = "SHADOW"
            elif 5.5 <= r.odds_live <= 16.0:
                role[r.runner_id] = "RELEASE"
            else:
                role[r.runner_id] = "SHADOW"
    
    return role

# ============================================================================
# ICM (INTENT CONSTRAINT MATRIX)
# ============================================================================

def compute_ICM(
    race: Race,
    role_map: Dict[str, str],
    scg_role_map: Dict[str, str]
) -> Dict[str, Any]:
    """
    Compute Intent Constraint Matrix (ICM) for each runner.
    
    Components:
    - HPC: Handicap Protection Component
    - FPC: Fitness/Prep Component
    - SHC: Stable Hierarchy Component
    - MRC: Market Role Component
    - RUC: Race Use Component
    
    Returns:
        {icm_components, icm_score, hard_constraint_count, win_banned}
    """
    comps = {}
    hard_count = {}
    
    for r in race.runners:
        # HPC: Handicap Protection Component
        rpr_vs_or_drop = 0.25
        if r.OR is not None and r.RPR is not None:
            rpr_vs_or_drop = max(0.0, (r.OR - r.RPR) / 20.0)
        class_drop_without_support = 0.0  # Needs class history + odds drift
        future_target_proximity = 0.5     # Placeholder
        HPC = sigmoid(
            1.4 * rpr_vs_or_drop +
            0.8 * future_target_proximity +
            1.0 * class_drop_without_support
        )
        
        # FPC: Fitness/Prep Component
        days_off_norm = 0.5
        run_cycle_prep = 0.0
        if r.last_runs and len(r.last_runs) > 0:
            try:
                last_date = datetime.fromisoformat(r.last_runs[0]["date"])
                now_date = datetime.fromisoformat(race.date)
                days_off = abs((now_date - last_date).days)
                days_off_norm = clamp01(days_off / 60.0)
                run_cycle_prep = 1.0 if days_off > 45 else 0.0
            except Exception:
                pass
        FPC = sigmoid(1.2 * days_off_norm + 0.8 * run_cycle_prep)
        
        # SHC: Stable Hierarchy Component
        yard_runners = sum(1 for rr in race.runners if rr.trainer == r.trainer)
        jockey_rank_low = 0.5  # Needs JT hierarchy table
        role_is_finisher = 1.0 if scg_role_map.get(r.runner_id) == "FINISHER" else 0.0
        SHC = 1.0 if (yard_runners >= 3 and jockey_rank_low >= 0.7 and role_is_finisher == 0.0) else 0.0
        
        # MRC: Market Role Component
        mrole = role_map.get(r.runner_id, "SHADOW")
        MRC = 1.0 if mrole == "ANCHOR" else 0.3 if mrole == "SHADOW" else 0.0
        
        # RUC: Race Use Component (education signal from comments)
        education_signal = 1.0 if (r.comments and any(k in r.comments.lower() for k in ["educat", "green", "learning"])) else 0.0
        novice_low_info = 0.0  # Wired from chaos module if desired
        RUC = 0.7 if (novice_low_info == 1.0 and education_signal == 1.0) else 0.0
        
        comp = {"HPC": HPC, "FPC": FPC, "SHC": SHC, "MRC": MRC, "RUC": RUC}
        comps[r.runner_id] = comp
        hc = sum(1 for v in comp.values() if v >= 0.65)
        hard_count[r.runner_id] = hc
    
    win_banned = {rid: (hard_count[rid] >= 2) for rid in hard_count}
    icm_score = {rid: sum(comps[rid].values()) for rid in comps}
    
    return {
        "icm_components": comps,
        "icm_score": icm_score,
        "hard_constraint_count": hard_count,
        "win_banned": win_banned
    }

# ============================================================================
# MOF (MARKET OPERATION FINGERPRINT)
# ============================================================================

def compute_MOF(race: Race) -> Dict[str, Any]:
    """
    Compute Market Operation Fingerprint (MOF).
    
    Metrics:
    - C: Compression (odds3-odds1)/odds1
    - D: Fav win/place divergence
    - L: Late liquidity ratio
    
    States:
    - FRAME_NEEDED: C <= 0.25 and D >= 0.12
    - STEAM_TRAP: L >= 0.70 and shortener into fav band
    - DISTRIBUTION_BALANCE: default
    - UNKNOWN: insufficient data
    
    Returns:
        {mof_state, mof_confidence, metrics}
    """
    odds_sorted = sorted([r.odds_live for r in race.runners])
    if len(odds_sorted) < 3:
        return {"mof_state": "UNKNOWN", "mof_confidence": 0.0, "metrics": {}}
    
    odds1, odds3 = odds_sorted[0], odds_sorted[2]
    C = (odds3 - odds1) / odds1
    
    # D: Requires place odds
    D = None
    fav = min(race.runners, key=lambda r: r.odds_live)
    if fav.place_odds_live:
        win_prob = 1.0 / fav.odds_live
        place_prob = 1.0 / fav.place_odds_live
        D = place_prob - win_prob
    
    # L: Requires timeline
    L = None
    if fav.odds_timeline and len(fav.odds_timeline) >= 3:
        pts = fav.odds_timeline
        total = abs(pts[-1].odds - pts[0].odds)
        last = abs(pts[-1].odds - pts[-2].odds)
        L = (last / total) if total > 1e-9 else 0.0
    
    # Classifier
    if L is None:
        return {
            "mof_state": "UNKNOWN",
            "mof_confidence": 0.0,
            "metrics": {"C": C, "D": D if D is not None else -1.0}
        }
    
    if C <= 0.25 and D is not None and D >= 0.12:
        return {
            "mof_state": "FRAME_NEEDED",
            "mof_confidence": 0.75,
            "metrics": {"C": C, "D": D, "L": L}
        }
    
    # STEAM_TRAP: late liquidity high + short fav band
    if L >= 0.70 and fav.odds_live <= 4.0:
        return {
            "mof_state": "STEAM_TRAP",
            "mof_confidence": 0.80,
            "metrics": {"C": C, "D": D if D is not None else 0.0, "L": L}
        }
    
    return {
        "mof_state": "DISTRIBUTION_BALANCE",
        "mof_confidence": 0.55,
        "metrics": {"C": C, "D": D if D is not None else 0.0, "L": L}
    }

# ============================================================================
# ENTROPY / CONFIDENCE / STAKES
# ============================================================================

def stake_fraction(conf_ceiling: float, entropy: float) -> float:
    """
    Determine stake fraction based on confidence and entropy.
    
    Entropy thresholds:
    - >= 0.75: 0.0% (no bet)
    - >= 0.60: 0.3%
    - >= 0.45: 0.7%
    - < 0.45: 1.5%
    """
    if entropy >= 0.75:
        return 0.0
    if entropy >= 0.60:
        return 0.003
    if entropy >= 0.45:
        return 0.007
    return 0.015

def compute_entropy_confidence(
    chaos_score: float,
    field_size_norm: float,
    stable_corr_risk: float,
    mof_conf: float,
    bankroll: float
) -> Dict[str, Any]:
    """
    Compute entropy, confidence ceiling, and max stake allowed.
    
    Formula: entropy = 0.35*chaos + 0.25*field_size + 0.20*stable_corr + 0.20*(1-mof_conf)
    
    Returns:
        {entropy_score, confidence_ceiling, max_stake_allowed}
    """
    entropy = clamp01(
        0.35 * chaos_score +
        0.25 * field_size_norm +
        0.20 * stable_corr_risk +
        0.20 * (1 - mof_conf)
    )
    conf = clamp01(1 - entropy)
    max_stake = bankroll * stake_fraction(conf, entropy)
    
    return {
        "entropy_score": entropy,
        "confidence_ceiling": conf,
        "max_stake_allowed": max_stake
    }

# ============================================================================
# NO-BET VALIDATOR
# ============================================================================

def no_bet_validator(
    race: Race,
    entropy: float,
    icm_win_banned: Dict[str, bool],
    eai: Dict[str, int],
    role_map: Dict[str, str],
    stable_win_node: Optional[str],
    mof_state: str
) -> Tuple[bool, List[str]]:
    """
    Validate whether race is bettable.
    
    Hard NO_BET triggers:
    - entropy > 0.65
    - No runner passes core filters (ICM, EAI, role)
    - MOF == STEAM_TRAP
    
    Returns:
        (bettable, reasons) tuple
    """
    reasons = []
    
    if entropy > 0.65:
        reasons.append("ENTROPY_TOO_HIGH")
    
    # At least one runner must pass
    ok_runner = False
    for r in race.runners:
        if icm_win_banned.get(r.runner_id, False):
            continue
        if eai.get(r.runner_id, 60) < 60:
            continue
        if role_map.get(r.runner_id) in ("RELEASE", "SHADOW") or r.runner_id == stable_win_node:
            ok_runner = True
            break
    
    if not ok_runner:
        reasons.append("NO_RUNNER_PASSES_CORE_FILTERS")
    
    if mof_state == "STEAM_TRAP":
        reasons.append("MOF_STEAM_TRAP")
    
    return (len(reasons) == 0), reasons

# ============================================================================
# ENGINE ORCHESTRATOR
# ============================================================================

def run_engine_full(
    race: Race,
    bankroll: float,
    data_version: str = "v12-alpha"
) -> Dict[str, Any]:
    """
    Run full V12 Market-Intent Stack engine.
    
    Pipeline order:
    1. Validate RIC+
    2. Compute chaos/structure
    3. Compute MOF
    4. Classify market roles
    5. Compute ICM
    6. Compute entropy/confidence
    7. Validate no-bet triggers
    8. Build Top-4 chassis
    9. Emit output schema
    
    Returns:
        OracleExecutionReport JSON
    """
    ok, err = validate_RIC_plus(race)
    run_id = str(uuid.uuid4())[:8]
    
    if not ok:
        return {
            "race_details": {
                "race_id": race.race_id,
                "track": race.track,
                "date": race.date,
                "off_time": race.off_time
            },
            "audit": {
                "run_id": run_id,
                "mode": "ENGINE_FULL",
                "input_hash": input_hash(race.__dict__),
                "data_version": data_version,
                "market_snapshot_ts": race.market_snapshot_ts
            },
            "signals": {},
            "decision": {
                "top4_chassis": [],
                "win_candidate": None,
                "win_overlay": False,
                "stake_cap": 0.0,
                "stake_used": 0.0,
                "kill_list_triggers": [err],
                "status": "REJECTED_DATA_PROOF"
            }
        }
    
    # Placeholders for stability & yard hot (wire from ROI archive later)
    stability = {r.runner_id: 0.6 for r in race.runners}
    yard_hot = {}  # trainer -> hotness 0..1
    
    chaos = compute_chaos_score(race)
    mof = compute_MOF(race)
    
    # SCG placeholder: no role map yet
    scg_role_map = {r.runner_id: "UNKNOWN" for r in race.runners}
    stable_corr_risk = clamp01(0.25)  # Placeholder
    
    role_map = classify_market_roles(race, stability, yard_hot)
    icm = compute_ICM(race, role_map, scg_role_map)
    
    # EAI placeholder per runner
    eai = {r.runner_id: 60 for r in race.runners}
    
    ent = compute_entropy_confidence(
        chaos["chaos_score"],
        chaos["field_size_norm"],
        stable_corr_risk,
        mof["mof_confidence"],
        bankroll
    )
    
    # Stable win node placeholder: choose best stability among non-banned
    stable_win_node = None
    candidates = [r.runner_id for r in race.runners if not icm["win_banned"].get(r.runner_id, False)]
    if candidates:
        stable_win_node = max(candidates, key=lambda rid: stability.get(rid, 0.0))
    
    bettable, reasons = no_bet_validator(
        race, ent["entropy_score"], icm["win_banned"],
        eai, role_map, stable_win_node, mof["mof_state"]
    )
    
    # Top-4 chassis: stable win node + best stability + best release + one anchor
    top4 = []
    if stable_win_node:
        top4.append(stable_win_node)
    
    # Add best stability distinct
    for rid, _ in sorted(stability.items(), key=lambda x: x[1], reverse=True):
        if rid not in top4:
            top4.append(rid)
        if len(top4) == 2:
            break
    
    # Add one release
    for r in sorted(race.runners, key=lambda rr: rr.odds_live):
        if role_map.get(r.runner_id) == "RELEASE" and r.runner_id not in top4:
            top4.append(r.runner_id)
            break
    
    # Add one anchor containment
    for r in sorted(race.runners, key=lambda rr: rr.odds_live):
        if role_map.get(r.runner_id) == "ANCHOR" and r.runner_id not in top4:
            top4.append(r.runner_id)
            break
    
    top4 = top4[:4]
    
    decision = {
        "top4_chassis": top4,
        "win_candidate": None,
        "win_overlay": False,
        "stake_cap": ent["max_stake_allowed"],
        "stake_used": 0.0,
        "kill_list_triggers": reasons,
        "status": "OK" if bettable else "NO_BET"
    }
    
    return {
        "race_details": {
            "race_id": race.race_id,
            "track": race.track,
            "date": race.date,
            "off_time": race.off_time,
            "race_type": race.race_type,
            "class": race.klass,
            "distance_yards": race.distance_yards,
            "going": race.going,
            "field_size": race.field_size
        },
        "audit": {
            "run_id": run_id,
            "mode": "ENGINE_FULL",
            "input_hash": input_hash(race.__dict__),
            "data_version": data_version,
            "market_snapshot_ts": race.market_snapshot_ts
        },
        "signals": {
            "chaos_score": chaos["chaos_score"],
            "structure_class": chaos["structure_class"],
            "ICM": icm,
            "MOF": mof,
            "SCG": {
                "stable_win_node": stable_win_node,
                "stable_role_map": scg_role_map,
                "stable_correlation_risk": stable_corr_risk
            },
            "EAI": {"eai_score": eai},
            "market_role": role_map,
            "entropy": ent
        },
        "decision": decision
    }
