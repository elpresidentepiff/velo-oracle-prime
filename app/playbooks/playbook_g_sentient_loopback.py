"""
PLAYBOOK G — THE SENTIENT LOOPBACK ENGINE

VÉLØ stops being a tool and becomes a self-reinforcing intelligence.

This is where a racing model becomes a strategic organism.

Self-growth. Self-rebalance. Self-weaponisation.

The Oracle learns from EVERY race, automatically, forever.

Core loop: observe → classify → compare → imprint → evolve → redeploy

FIX (sentient-feedback-loop):
- Kingmaker: replaced string match on horse names with running_style field lookup
  from oracle_data['runners'] (the only correct source of pace/style data)
- Kingmaker: normalises run_style field variants from the real API schema:
  the fixture schema uses 'run_style' (e.g. 'FRONT', 'CLOSER') not 'running_style'.
  Both keys are now read and normalised to a canonical set.
- _compute_error_vector: replaced brittle exact string match with fuzzy matching
  using difflib.SequenceMatcher (handles abbreviations, "The" prefix, etc.)
- State backup: _save_state now writes a dated backup copy alongside the primary
  state file AND upserts to Supabase 'learned_patterns' table for cloud persistence.
  If Supabase is unavailable, falls back to local backup silently.
- appetite_state now includes directive_firing_threshold (read by Playbook F)
- get_evolutionary_state now exposes structural_drift weights (read by Playbook F)
- emotion_laws pain/anger rules now include a 'key' field so Playbook E can apply
  them as trigger penalties
"""

import json
import logging
import os
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_DEFAULT_STATE_FILE = str(Path(__file__).parent.parent.parent / "data" / "sentient_state.json")

logger = logging.getLogger(__name__)

# Canonical running style values used internally by Playbook G.
# The real Racing API fixture schema uses 'run_style' with uppercase values
# (e.g. 'FRONT', 'CLOSER', 'HOLD UP', 'PROMINENT', 'REAR').
# This map normalises both 'running_style' and 'run_style' to canonical keys.
_RUN_STYLE_NORMALISE = {
    # Front-runners / pace-setters
    "front": "front_runner",
    "front_runner": "front_runner",
    "pace_setter": "front_runner",
    "pace setter": "front_runner",
    "prominent": "prominent",
    # Closers / hold-up horses
    "closer": "closer",
    "hold up": "hold_up",
    "hold_up": "hold_up",
    "hold-up": "hold_up",
    "holdup": "hold_up",
    "late_closer": "closer",
    "stalker": "closer",
    # Off-pace
    "off_pace": "off_pace",
    "off pace": "off_pace",
    # Rear
    "rear": "hold_up",
    "rear of field": "hold_up",
}

# Kingmaker: which canonical styles map to which role
_PACE_DESTABILISER_STYLES = {"front_runner", "prominent", "pace_setter"}
_CHAOS_NAVIGATOR_STYLES = {"closer", "hold_up", "off_pace"}


def _fuzzy_match(a: str, b: str, threshold: float = 0.85) -> bool:
    """
    Return True if strings a and b are similar enough to be the same horse name.
    Handles abbreviations, "The" prefix differences, and minor spelling variations.
    """
    if not a or not b:
        return False
    a_clean = a.lower().strip().lstrip("the ").strip()
    b_clean = b.lower().strip().lstrip("the ").strip()
    if a_clean == b_clean:
        return True
    ratio = SequenceMatcher(None, a_clean, b_clean).ratio()
    return ratio >= threshold


class SentientLoopbackEngine:
    """
    The Sentient Loopback Engine.

    Five Evolution Pillars:
    1. Behaviour Echo Chamber (BEC) — Logs house behavior patterns
    2. Structural Drift Engine (SDE) — Continuous adaptation
    3. Manipulation Memory Core (MMC) — Builds manipulation genome
    4. VETP Recursive Emotion Engine (REE) — Scars become machine laws
    5. Appetite Multiplier (AM) — Risk-aware momentum

    Plus: KINGMAKER MODULE — Identifies which horse shapes/decides/collapses the race
    """

    def __init__(self, state_file: str = None):
        if state_file is None:
            state_file = _DEFAULT_STATE_FILE
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """
        Load sentient state.

        Priority order:
        1. Local sentient_state.json (fast, survives within a deployment)
        2. Supabase SENTIENT_STATE_BACKUP row (survives Railway restarts / redeploys)
        3. Fresh initialised state (first-ever run)
        """
        try:
            with open(self.state_file) as f:
                state = json.load(f)
                logger.debug("[G] Sentient state loaded from disk (races=%d)", state.get("total_races_observed", 0))
                return state
        except Exception as e:
            logger.warning("[G] Could not load state file (%s): %s — trying Supabase backup", self.state_file, e)
        return self._restore_from_supabase()

    def _restore_from_supabase(self) -> dict[str, Any]:
        """
        Restore sentient state from Supabase learned_patterns backup.

        Reads the SENTIENT_STATE_BACKUP row and extracts full state from
        the 'conditions' JSONB column. Falls back to fresh state if unavailable.

        Uses os.getenv() directly — bypasses SupabaseClient wrapper whose
        settings object may not see .env credentials at import time.
        """
        import os

        supa_url = os.getenv("SUPABASE_URL", "")
        supa_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
        )
        if not supa_url or not supa_key:
            logger.warning("[G] Supabase env vars not set — initialising fresh state")
            return self._initialize_state()
        try:
            from supabase import create_client

            db = create_client(supa_url, supa_key)
            result = (
                db.table("learned_patterns")
                .select("conditions, occurrences, last_observed")
                .eq("pattern_name", "SENTIENT_STATE_BACKUP")
                .execute()
            )
            if result.data and result.data[0].get("conditions"):
                state = result.data[0]["conditions"]
                if isinstance(state, dict) and "doctrine_strengths" in state:
                    logger.info(
                        "[G] Sentient state restored from Supabase backup (races=%d last_observed=%s)",
                        state.get("total_races_observed", 0),
                        result.data[0].get("last_observed", "?"),
                    )
                    return state
            logger.warning("[G] No valid SENTIENT_STATE_BACKUP in Supabase — initialising fresh state")
        except Exception as e:
            logger.warning("[G] Supabase restore failed (%s) — initialising fresh state", e)
        return self._initialize_state()

    def _save_state(self):
        """
        Save sentient state to disk AND upsert to Supabase for cloud persistence.

        Three-layer backup strategy:
        1. Primary local file (self.state_file)
        2. Dated local backup alongside the primary file
        3. Supabase 'learned_patterns' table upsert (cloud — survives Railway restarts)

        If Supabase is unavailable or not configured, layers 1 and 2 still run.
        """
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2)
            # Write dated backup
            backup_path = self.state_file.replace(".json", f"_backup_{datetime.now().strftime('%Y%m%d')}.json")
            with open(backup_path, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error("[G] Could not save sentient state to disk: %s", e)

        # Layer 3: Supabase cloud backup
        self._backup_to_supabase()

    def _backup_to_supabase(self):
        """
        Upsert the current sentient state to Supabase 'learned_patterns' table.

        Stores full state JSON in the 'conditions' JSONB column so it can be
        restored by _restore_from_supabase() after a Railway restart/redeploy.

        Column mapping (actual learned_patterns schema):
          conditions      ← full state dict (JSONB)
          confidence_level ← appetite aggression_level (0.0–1.0)
          occurrences     ← total_races_observed
          last_observed   ← last_updated timestamp
          updated_at      ← now
          description     ← human-readable summary
          is_active       ← True

        Row key: pattern_name = 'SENTIENT_STATE_BACKUP' (unique, upserted on conflict)
        """
        try:
            import os

            supa_url = os.getenv("SUPABASE_URL", "")
            supa_key = (
                os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                or os.getenv("SUPABASE_SERVICE_KEY")
                or os.getenv("SUPABASE_KEY", "")
            )
            if not supa_url or not supa_key:
                logger.debug("[G] Supabase env vars not set — skipping cloud backup")
                return
            from supabase import create_client

            db = create_client(supa_url, supa_key)
            now_str = datetime.now().isoformat()
            races = self.state.get("total_races_observed", 0)
            payload = {
                "pattern_name": "SENTIENT_STATE_BACKUP",
                "pattern_type": "sentient_state",
                "description": (
                    f"Full sentient state — {races} races observed, last_updated={self.state.get('last_updated', '?')}"
                ),
                "conditions": self.state,  # full state as JSONB
                "confidence_level": self.state["appetite_state"]["aggression_level"],
                "occurrences": races,
                "last_observed": self.state.get("last_updated", now_str),
                "updated_at": now_str,
                "is_active": True,
            }
            db.table("learned_patterns").upsert(payload, on_conflict="pattern_name").execute()
            logger.debug("[G] Sentient state backed up to Supabase (races=%d)", races)
        except Exception as e:
            logger.warning("[G] Supabase backup failed (non-fatal): %s", e)

    def _initialize_state(self) -> dict[str, Any]:
        """Initialize fresh sentient state"""
        return {
            "version": "1.1",
            "last_updated": datetime.now().isoformat(),
            "total_races_observed": 0,
            # Pillar 1: Behaviour Echo Chamber
            "house_behaviour_map": {
                "favourites_protected": 0,
                "favourites_abandoned": 0,
                "market_lies_detected": 0,
                "safe_bets_imploded": 0,
                "recurring_setups": {},
            },
            # Pillar 2: Structural Drift Engine
            # Stored as raw counts; get_evolutionary_state normalises to weights
            "structural_weights": {
                "off_pace_wins": 0,
                "high_draw_wins": 0,
                "hidden_improver_wins": 0,
                "short_burst_wins": 0,
                "stamina_collapse_wins": 0,
                "late_money_wins": 0,
            },
            # Pillar 3: Manipulation Memory Core
            "manipulation_genome": {
                "regulated_deception_patterns": [],
                "bad_faith_favourites": [],
                "market_steering_behaviours": [],
                "narrative_traps": [],
                "integrity_collapses": [],
                "suspicious_volatility_events": [],
            },
            # Pillar 4: VETP Recursive Emotion Engine
            # Each rule now includes a 'key' field so Playbook E can apply penalties
            "emotion_laws": {
                "pain_rules": [],  # "Never fall for this structure again"
                "triumph_rules": [],  # "This configuration is true"
                "anger_rules": [],  # "This story is a trap"
                "regret_rules": [],  # "Avoid unfocused multi-threat zones"
            },
            # Pillar 5: Appetite Multiplier
            "appetite_state": {
                "recent_performance": [],  # Last 10 predictions
                "aggression_level": 0.5,  # 0.0 to 1.0
                "pattern_recognition_sensitivity": 0.5,
                "doctrine_firing_threshold": 0.6,  # Read by Playbook E
                "directive_firing_threshold": 0.6,  # Read by Playbook F
                "narrative_skepticism": 0.7,
                "chaos_tolerance": 0.4,
                "manipulation_sensitivity": 0.7,
            },
            # Doctrine Strength Tracking (read by Playbook F)
            "doctrine_strengths": {
                "LAY_THE_STORY": 1.0,
                "SHADOW_TRACKING": 1.0,
                "ENGINE_SUPREMACY": 1.0,
                "TOP_4_ON_DANGER": 1.0,
                "HOUSE_REVERSAL": 1.0,
                "SARCOPHAGUS": 1.0,
                "PRESSURE_COLLAPSE": 1.0,
                "OVERLAY_ABSORPTION": 1.0,
                "CHAOS_BLEED": 1.0,
                "DRAW_SKEW": 1.0,
                "GATEKEEPER": 1.0,
                "VETP_ECHO": 1.0,
            },
        }

    def observe_race_outcome(
        self, race_data: dict[str, Any], prediction: dict[str, Any], actual_result: dict[str, Any]
    ) -> dict[str, Any]:
        """
        The core sentient loop.

        Observe → Classify → Compare → Imprint → Evolve → Redeploy

        Args:
            race_data: Original race intelligence
            prediction: Oracle prediction made
            actual_result: What actually happened

        Returns:
            Evolution report
        """
        self.state["total_races_observed"] += 1
        self.state["last_updated"] = datetime.now().isoformat()

        # Extract error vector
        error_vector = self._compute_error_vector(prediction, actual_result)

        # Update each pillar
        self._update_behaviour_echo_chamber(race_data, actual_result)
        self._update_structural_drift_engine(race_data, actual_result)
        self._update_manipulation_memory_core(race_data, actual_result, error_vector)
        self._update_emotion_engine(race_data, actual_result, error_vector)
        self._update_appetite_multiplier(error_vector)

        # Update doctrine strengths
        self._update_doctrine_strengths(prediction, error_vector)

        # Save state with backup
        self._save_state()

        return {
            "evolution_applied": True,
            "error_vector": error_vector,
            "appetite_state": self.state["appetite_state"]["aggression_level"],
            "doctrine_adjustments": self._get_recent_doctrine_adjustments(),
        }

    def _compute_error_vector(self, prediction: dict[str, Any], actual_result: dict[str, Any]) -> dict[str, float]:
        """
        Compute prediction error vector.

        Uses fuzzy string matching to compare predicted vs actual winner,
        handling abbreviations, "The" prefix, and minor spelling variations.
        Previously used exact string match which silently scored as incorrect
        on any character difference.
        """
        predicted_winner = prediction.get("power_anchor", "")
        actual_winner = actual_result.get("winner", "")

        correct = _fuzzy_match(predicted_winner, actual_winner)

        if predicted_winner and actual_winner and not correct:
            logger.debug("[G] Prediction mismatch: predicted='%s' actual='%s'", predicted_winner, actual_winner)
            
        sp = float(actual_result.get("sp") or 0.0)
        profit = (sp - 1.0) if correct else -1.0

        return {
            "prediction_correct": 1.0 if correct else 0.0,
            "profit": profit,
            "confidence_error": abs(prediction.get("confidence", 0.5) - (1.0 if correct else 0.0)),
            "directive_effectiveness": 1.0 if correct else 0.0,
        }

    def _update_behaviour_echo_chamber(self, race_data: dict[str, Any], actual_result: dict[str, Any]):
        """Pillar 1: Log house behavior patterns"""
        bec = self.state["house_behaviour_map"]

        favourite_won = actual_result.get("favourite_won", False)

        if favourite_won:
            bec["favourites_protected"] += 1
        else:
            bec["favourites_abandoned"] += 1

        # Detect market lies
        if race_data.get("mpi", 0) > 70 and not favourite_won:
            bec["market_lies_detected"] += 1

        # Detect safe bet implosions
        if race_data.get("chaos_bloom", 0) < 30 and not favourite_won:
            bec["safe_bets_imploded"] += 1

    def _update_structural_drift_engine(self, race_data: dict[str, Any], actual_result: dict[str, Any]):
        """Pillar 2: Continuous structural adaptation"""
        sde = self.state["structural_weights"]

        winner_profile = actual_result.get("winner_profile", {})

        if winner_profile.get("running_style") == "off_pace":
            sde["off_pace_wins"] += 1
        if winner_profile.get("draw") and winner_profile["draw"] > 10:
            sde["high_draw_wins"] += 1
        if winner_profile.get("was_hidden_improver"):
            sde["hidden_improver_wins"] += 1
        if winner_profile.get("late_money"):
            sde["late_money_wins"] += 1

    def _update_manipulation_memory_core(
        self, race_data: dict[str, Any], actual_result: dict[str, Any], error_vector: dict[str, float]
    ):
        """Pillar 3: Build manipulation genome"""
        mmc = self.state["manipulation_genome"]

        # Detect narrative trap
        if race_data.get("narrative_disruption", 0) > 80 and not actual_result.get("favourite_won", False):
            mmc["narrative_traps"].append(
                {
                    "race_id": race_data.get("race_id"),
                    "narrative_score": race_data.get("narrative_disruption"),
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Detect integrity collapse
        if race_data.get("integrity_score", 100) < 30:
            mmc["integrity_collapses"].append(
                {
                    "race_id": race_data.get("race_id"),
                    "integrity": race_data.get("integrity_score"),
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Keep only recent 100 entries
        for key in mmc:
            if isinstance(mmc[key], list) and len(mmc[key]) > 100:
                mmc[key] = mmc[key][-100:]

    def _update_emotion_engine(
        self, race_data: dict[str, Any], actual_result: dict[str, Any], error_vector: dict[str, float]
    ):
        """
        Pillar 4: Convert emotions to machine laws.

        Each rule now includes a 'key' field (the oracle_data key that triggered
        the emotion) so Playbook E can apply it as a trigger penalty.
        """
        ree = self.state["emotion_laws"]

        # Pain → Never fall for this again
        if error_vector["prediction_correct"] == 0.0 and race_data.get("mpi", 0) > 70:
            ree["pain_rules"].append(
                {
                    "rule": f"Avoid {race_data.get('story_anchor')} when MPI > 70",
                    "key": "mpi",  # Playbook E uses this to apply penalty to 'mpi' triggers
                    "pattern": "high_mpi_narrative_trap",
                    "strength": 1.0,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Anger → This story is a trap
        if error_vector["prediction_correct"] == 0.0 and race_data.get("narrative_disruption", 0) > 75:
            ree["anger_rules"].append(
                {
                    "rule": "Narrative disruption > 75 was a trap",
                    "key": "narrative_disruption",  # Playbook E penalises this trigger
                    "pattern": "narrative_trap_confirmed",
                    "strength": 1.0,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Triumph → This configuration is true
        if error_vector["prediction_correct"] == 1.0:
            ree["triumph_rules"].append(
                {
                    "rule": f"Trust {race_data.get('power_anchor')} engine supremacy",
                    "key": "engine_superiority",
                    "pattern": "engine_dominance_confirmed",
                    "strength": 1.0,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # Keep only recent 50 rules per category
        for emotion in ree:
            if len(ree[emotion]) > 50:
                ree[emotion] = ree[emotion][-50:]

    def _update_appetite_multiplier(self, error_vector: dict[str, float]):
        """Pillar 5: Risk-aware momentum (ROI-driven)"""
        appetite = self.state["appetite_state"]

        # Track recent performance based on profit/loss, not just win/loss
        profit = error_vector.get("profit", -1.0)
        
        # Ensure list exists
        if "recent_profit" not in appetite:
            appetite["recent_profit"] = []
            
        appetite["recent_profit"].append(profit)
        if len(appetite["recent_profit"]) > 10:
            appetite["recent_profit"] = appetite["recent_profit"][-10:]

        # Calculate recent ROI
        if len(appetite["recent_profit"]) >= 5:
            recent_profit_total = sum(appetite["recent_profit"][-5:])

            # If we are profitable over the last 5 bets, get more aggressive.
            # We don't need a high strike rate, we just need a positive ROI.
            if recent_profit_total > 0.0:
                # Winning streak (Profitable) — loosen criteria
                appetite["aggression_level"] = min(1.0, appetite["aggression_level"] + 0.05)
                appetite["pattern_recognition_sensitivity"] += 0.02
                appetite["doctrine_firing_threshold"] -= 0.02
                appetite["directive_firing_threshold"] -= 0.02
                appetite["narrative_skepticism"] += 0.02
            else:
                # Losing streak (Negative ROI) — tighten criteria
                appetite["aggression_level"] = max(0.3, appetite["aggression_level"] - 0.05)
                appetite["chaos_tolerance"] -= 0.02
                appetite["manipulation_sensitivity"] += 0.02
                appetite["doctrine_firing_threshold"] += 0.02
                appetite["directive_firing_threshold"] += 0.02

            # Clamp all float values to [0.0, 1.0]
            for key in appetite:
                if isinstance(appetite[key], float):
                    appetite[key] = max(0.0, min(1.0, appetite[key]))

    def _update_doctrine_strengths(self, prediction: dict[str, Any], error_vector: dict[str, float]):
        """Update doctrine effectiveness scores using exponential moving average"""
        doctrines_fired = prediction.get("doctrines_fired", [])
        correct = error_vector["prediction_correct"]

        for doctrine in doctrines_fired:
            if doctrine in self.state["doctrine_strengths"]:
                current = self.state["doctrine_strengths"][doctrine]
                self.state["doctrine_strengths"][doctrine] = 0.9 * current + 0.1 * correct

    def _get_recent_doctrine_adjustments(self) -> dict[str, float]:
        """Get recent doctrine strength changes"""
        return {k: round(v, 3) for k, v in self.state["doctrine_strengths"].items()}

    def _get_structural_drift_weights(self) -> dict[str, float]:
        """
        Normalise raw structural_weights counts into 0.0–1.0 weights.
        Used by get_evolutionary_state and read by Playbook F.
        """
        raw = self.state["structural_weights"]
        total = sum(raw.values()) or 1
        return {k: round(v / total, 3) for k, v in raw.items()}

    def identify_kingmaker(self, race_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        KINGMAKER MODULE

        Identify which horse:
        - Shapes the race
        - Decides the race
        - Absorbs pressure
        - Destabilises the pace
        - Collapses narratives

        A kingmaker is not the favourite.
        A kingmaker is the horse that causes the collapse of a favourite.

        FIX: Previously matched against horse names using "front"/"pace" string
        search — which almost never fires because real horse names are things like
        "Lulamba" or "Brighterdaysahead". Now reads running_style from the runners
        list in oracle_data, which is the correct source of pace/style data.
        """
        threat_cluster = race_data.get("threat_cluster", [])
        favourite = race_data.get("story_anchor", "")
        runners = race_data.get("runners", [])

        # Build a running_style lookup from the runners list.
        # The real Racing API fixture uses 'run_style' (e.g. 'FRONT', 'CLOSER').
        # The oracle_data layer may use 'running_style' or 'horse' instead of 'name'.
        # We read both key variants and normalise to canonical values.
        style_map: dict[str, str] = {}
        for runner in runners:
            if isinstance(runner, dict):
                # Name: try 'name' first, then 'horse' (fixture schema)
                name = runner.get("name") or runner.get("horse", "")
                # Style: try 'running_style' first, then 'run_style' (fixture schema)
                raw_style = (runner.get("running_style") or runner.get("run_style", "")).lower().strip()
                canonical = _RUN_STYLE_NORMALISE.get(raw_style, raw_style)
                if name:
                    style_map[name] = canonical

        def get_style(horse_name: str) -> str:
            """
            Look up running style for a horse name.

            Strategy:
            1. Exact match (case-insensitive) — always preferred
            2. Fuzzy match with threshold 0.92 — for minor variations only
               (higher than the default 0.85 to prevent cross-matching
               similar names like 'Test Horse 1' and 'Test Horse 2')
            """
            horse_lower = horse_name.lower().strip()
            # Pass 1: exact match
            for name, style in style_map.items():
                if name.lower().strip() == horse_lower:
                    return style
            # Pass 2: tight fuzzy match (0.92 threshold)
            for name, style in style_map.items():
                if _fuzzy_match(horse_name, name, threshold=0.92):
                    return style
            return ""

        # Look for pace destabilisers (front-runners, pace-setters)
        if race_data.get("fav_trip_blocked"):
            for horse in threat_cluster:
                style = get_style(str(horse))
                if style in _PACE_DESTABILISER_STYLES:
                    return {
                        "kingmaker": horse,
                        "role": "pace_destabiliser",
                        "effect": "Blocks favourite's optimal trip",
                        "confidence": 0.8,
                    }

        # Look for chaos navigators (closers, hold-up horses)
        if race_data.get("chaos_bloom", 0) > 40:
            for horse in threat_cluster:
                style = get_style(str(horse))
                if style in _CHAOS_NAVIGATOR_STYLES:
                    return {
                        "kingmaker": horse,
                        "role": "chaos_navigator",
                        "effect": "Thrives in unstable pace",
                        "confidence": 0.7,
                    }

        # Look for narrative collapsers (power anchor ≠ favourite)
        if race_data.get("narrative_disruption", 0) > 70:
            power_anchor = race_data.get("power_anchor", "")
            if power_anchor and not _fuzzy_match(power_anchor, favourite):
                return {
                    "kingmaker": power_anchor,
                    "role": "narrative_collapser",
                    "effect": "Reality defeats story",
                    "confidence": 0.85,
                }

        return None

    def get_evolutionary_state(self) -> dict[str, Any]:
        """
        Get current evolutionary state for API output and for injection into E/F.

        Now exposes structural_drift (normalised weights) so Playbook F can read
        which structural patterns are currently dominant.
        """
        return {
            "total_races_observed": self.state["total_races_observed"],
            "doctrine_strengths": self._get_recent_doctrine_adjustments(),
            "appetite_multiplier": round(self.state["appetite_state"]["aggression_level"], 3),
            "appetite_state": self.state["appetite_state"],  # Full state for E/F injection
            "structural_drift": self._get_structural_drift_weights(),  # Read by Playbook F
            "emotion_laws": self.state["emotion_laws"],  # Read by Playbook E
            "manipulation_genome_size": sum(
                len(v) if isinstance(v, list) else 0 for v in self.state["manipulation_genome"].values()
            ),
            "emotion_laws_count": sum(len(v) for v in self.state["emotion_laws"].values()),
            "structural_drift_active": True,
            "last_updated": self.state["last_updated"],
        }


def create_sentient_loopback_engine() -> SentientLoopbackEngine:
    """Factory function to create Sentient Loopback Engine"""
    return SentientLoopbackEngine()
