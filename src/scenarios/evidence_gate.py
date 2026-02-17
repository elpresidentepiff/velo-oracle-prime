"""
VÉLØ Oracle Prime — Phase 1: Scenario Evidence Gate
====================================================

Module: src/scenarios/evidence_gate.py
Purpose: Prevents scenario code overuse (especially S6) by requiring
         minimum independent signal counts before a scenario can be assigned.

Day 1 Lessons:
    - "Hidden Intent without market confirmation is fiction."
    - "S6 was deployed 3 times based on single anecdotal signals and
       failed all 3 times."
    - "Flagging S8 as high probability while selecting a conventional
       Top Strike is internally contradictory."

Architecture: Integrates with existing SQLite memory engine (WAL mode).
              Tracks scenario accuracy rates in sigma_evaluations table.

Author: VÉLØ Oracle Prime — Phase 1 Build
Date: 2026-02-16
"""

import sqlite3
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple


# ---------------------------------------------------------------------------
# Scenario Definitions
# ---------------------------------------------------------------------------

class ScenarioVerdict(Enum):
    """Verdict on whether a scenario assignment is approved."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


SCENARIO_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "S1": {
        "name": "Straight Win",
        "description": (
            "The selection wins on merit through superior form, class, "
            "and market alignment. The most common winning scenario on "
            "conventional tracks."
        ),
        "min_signals": 3,
        "required_signal_types": {
            "form": "Form evidence — recent results support winning expectation",
            "class": "Class evidence — horse is at appropriate or lower class level",
            "market_agreement": (
                "Market agreement — BSP/ISP aligned with selection "
                "(not drifting significantly)"
            ),
        },
        "hard_requirements": [],
        "day1_notes": None,
    },
    "S2": {
        "name": "Tactical Grind",
        "description": (
            "The selection wins through tactical superiority — pace "
            "judgement, jockey skill, or positional advantage rather "
            "than raw ability."
        ),
        "min_signals": 2,
        "required_signal_types": {
            "pace_shape": (
                "Pace shape — race pace profile suits this horse's "
                "running style (e.g., strong pace for a closer)"
            ),
            "jockey_tactical": (
                "Jockey tactical record — jockey has proven tactical "
                "ability at this track/distance"
            ),
        },
        "hard_requirements": [],
        "day1_notes": (
            "At Wolverhampton Race 3, Arishka's Dream won via S2 "
            "(Tactical Grind) but was not identified as the primary "
            "scenario beneficiary."
        ),
    },
    "S3": {
        "name": "Collapse & Sweep",
        "description": (
            "Front-runners compromise each other through contested pace, "
            "allowing a closer to sweep past in the final stages."
        ),
        "min_signals": 3,
        "required_signal_types": {
            "pace_suicide_risk": (
                "Pace suicide risk — 2+ confirmed front-runners in the "
                "field likely to contest the lead"
            ),
            "closer_form": (
                "Closer form — the selection has proven closing ability "
                "and recent form to capitalise"
            ),
            "draw_position": (
                "Draw/position advantage — the selection's draw or "
                "typical racing position allows them to benefit from "
                "the pace collapse"
            ),
        },
        "hard_requirements": [],
        "day1_notes": (
            "At Wolverhampton Race 1, S3 was correctly identified but "
            "the wrong horse was named as the sweeper. The pace dynamic "
            "was right; the beneficiary was wrong."
        ),
    },
    "S4": {
        "name": "Controlled Theft",
        "description": (
            "A front-runner steals the race by controlling the pace "
            "from the front with no serious challengers for the lead."
        ),
        "min_signals": 3,
        "required_signal_types": {
            "front_runner_form": (
                "Front-runner form — the selection has proven front-running "
                "ability and recent competitive form"
            ),
            "pace_map_clear": (
                "Pace map clear — no other confirmed front-runners in the "
                "field; the selection gets an uncontested lead"
            ),
            "jockey_record": (
                "Jockey record — jockey has a record of making from the "
                "front at this track/distance"
            ),
        },
        "hard_requirements": [],
        "day1_notes": None,
    },
    "S5": {
        "name": "Market Trap",
        "description": (
            "The selection benefits from market manipulation or "
            "information asymmetry. The 'smart money' is on this horse "
            "while the public is elsewhere."
        ),
        "min_signals": 3,
        "required_signal_types": {
            "market_anomaly": (
                "Market anomaly — unusual price movement or volume "
                "that cannot be explained by public information"
            ),
            "stable_pattern": (
                "Stable pattern — the trainer/owner has a documented "
                "pattern of landing gambles or targeting specific races"
            ),
            "information_asymmetry": (
                "Information asymmetry indicator — evidence that "
                "connections have private information (e.g., trial "
                "reports, undisclosed fitness improvements)"
            ),
        },
        "hard_requirements": [],
        "day1_notes": None,
    },
    "S6": {
        "name": "Hidden Intent",
        "description": (
            "The connections are hiding their true intentions. The horse "
            "has been prepared for this specific race but the public "
            "signals are muted. HIGHEST EVIDENCE BAR — requires market "
            "confirmation as a HARD REQUIREMENT."
        ),
        "min_signals": 4,
        "required_signal_types": {
            "trainer_pattern": (
                "Trainer pattern — documented history of placing horses "
                "for specific targets after a series of prep runs"
            ),
            "jockey_upgrade": (
                "Jockey upgrade — significant upgrade in jockey booking "
                "compared to recent runs"
            ),
            "gear_change": (
                "Gear change — meaningful equipment change suggesting "
                "intent (first-time visor, tongue-tie, cheekpieces)"
            ),
            "market_shortening": (
                "Market shortening — HARD REQUIREMENT: BSP must be "
                "shorter than morning price. The market MUST confirm "
                "hidden intent. Without this signal, S6 is fiction."
            ),
        },
        "hard_requirements": ["market_shortening"],
        "day1_notes": (
            "S6 was deployed 3 times at Wolverhampton based on single "
            "anecdotal intent signals and failed all 3 times. "
            "Day 1 lesson: 'Hidden Intent without market confirmation "
            "is fiction.' The market_shortening signal is now a HARD "
            "REQUIREMENT — S6 cannot be assigned without it."
        ),
    },
    "S7": {
        "name": "Conditioning Run",
        "description": (
            "The horse is being conditioned — this is a stepping stone "
            "race, not the target. Similar to P (Prep) tag but at the "
            "scenario level."
        ),
        "min_signals": 2,
        "required_signal_types": {
            "campaign_stage": (
                "Campaign stage — horse is early in campaign (1-2 runs "
                "back) or clearly being brought along gradually"
            ),
            "trainer_pattern": (
                "Trainer pattern — trainer has a documented pattern of "
                "using conditioning runs before targeting"
            ),
        },
        "hard_requirements": [],
        "day1_notes": None,
    },
    "S8": {
        "name": "Chaos",
        "description": (
            "Insufficient data to assign any other scenario code with "
            "confidence. The race is genuinely unpredictable. On chaos "
            "tracks (rating >= 3), this should LOWER confidence in any "
            "Top Strike selection, not be ignored."
        ),
        "min_signals": 1,
        "required_signal_types": {
            "insufficient_data": (
                "Insufficient data — cannot confidently assign any "
                "other scenario code"
            ),
        },
        "hard_requirements": [],
        "day1_notes": (
            "At Wolverhampton Race 2, S8 was correctly flagged as high "
            "probability but the operational output ignored it. Flagging "
            "S8 while selecting a conventional Top Strike is internally "
            "contradictory. If S8 is the primary scenario, Top Strike "
            "confidence MUST be downgraded."
        ),
    },
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class ScenarioValidation:
    """Result of validating a proposed scenario assignment.

    Attributes:
        code: Scenario code (S1-S8).
        verdict: APPROVED or REJECTED.
        signals_provided: List of signal codes provided.
        signals_met: List of signal codes that matched requirements.
        signals_missing: List of signal codes still needed.
        hard_requirements_met: Whether all hard requirements are satisfied.
        reasoning: Human-readable explanation.
        confidence: Confidence score 0.0-1.0.
    """
    code: str
    verdict: ScenarioVerdict
    signals_provided: List[str]
    signals_met: List[str]
    signals_missing: List[str]
    hard_requirements_met: bool
    reasoning: str
    confidence: float = 0.0


@dataclass
class ScenarioSuggestion:
    """Suggested scenario based on available signals.

    Attributes:
        suggested_code: Best-fit scenario code.
        confidence: Confidence score 0.0-1.0.
        signal_match: Dict mapping code → matched signals.
        reasoning: Human-readable explanation.
        alternatives: List of (code, confidence) for runner-up scenarios.
    """
    suggested_code: str
    confidence: float
    signal_match: Dict[str, List[str]]
    reasoning: str
    alternatives: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class ScenarioAuditResult:
    """Post-race scenario accuracy assessment.

    Attributes:
        total_predictions: Total scenarios audited.
        correct_scenarios: Number of correct scenario assignments.
        accuracy_pct: Overall accuracy percentage.
        code_breakdown: Dict mapping code → {correct, total, accuracy}.
        lessons: List of lessons from incorrect scenarios.
    """
    total_predictions: int
    correct_scenarios: int
    accuracy_pct: float
    code_breakdown: Dict[str, Dict[str, Any]]
    lessons: List[str]


# ---------------------------------------------------------------------------
# Scenario Evidence Gate
# ---------------------------------------------------------------------------

class ScenarioEvidenceGate:
    """Evidence-based gating mechanism for scenario code assignment.

    Prevents scenario overuse (especially S6) by requiring minimum
    independent signal counts before a scenario can be assigned high
    probability.

    Key Principles (from SIGMA-02):
        - S6 requires 4 signals including market confirmation (HARD).
        - S8 flagged as primary → Top Strike confidence MUST drop.
        - Every scenario must earn its probability through evidence.

    Usage:
        >>> gate = ScenarioEvidenceGate(db_path="velo.db")
        >>> result = gate.validate_scenario("S6",
        ...     ["trainer_pattern", "jockey_upgrade", "gear_change",
        ...      "market_shortening"])
        >>> suggestion = gate.suggest_scenario(
        ...     ["form", "class", "market_agreement"])
    """

    def __init__(self, db_path: str = "velo_oracle.db"):
        """Initialise the Scenario Evidence Gate.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.scenario_defs = SCENARIO_DEFINITIONS
        self._init_db()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Ensure sigma_evaluations table exists with scenario tracking."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sigma_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id TEXT,
                    track TEXT,
                    race_date TEXT,
                    scenario_code TEXT,
                    scenario_name TEXT,
                    signals_provided TEXT,
                    signals_met TEXT,
                    verdict TEXT,
                    confidence REAL DEFAULT 0.0,
                    actual_scenario TEXT,
                    scenario_correct INTEGER,
                    horse TEXT,
                    actual_finish_pos INTEGER,
                    actual_bsp REAL,
                    notes TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sigma_scenario
                ON sigma_evaluations(scenario_code)
            """)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Core Methods
    # ------------------------------------------------------------------

    def validate_scenario(self, code: str,
                          signals_provided: List[str]) -> ScenarioValidation:
        """Validate whether a scenario assignment meets evidence requirements.

        Args:
            code: Scenario code (S1-S8).
            signals_provided: List of signal code strings.

        Returns:
            ScenarioValidation with APPROVED/REJECTED verdict.
        """
        code_upper = code.strip().upper()
        if code_upper not in self.scenario_defs:
            return ScenarioValidation(
                code=code_upper,
                verdict=ScenarioVerdict.REJECTED,
                signals_provided=signals_provided,
                signals_met=[],
                signals_missing=[],
                hard_requirements_met=False,
                reasoning=f"Unknown scenario code: {code}",
                confidence=0.0
            )

        defn = self.scenario_defs[code_upper]
        required_types = set(defn["required_signal_types"].keys())
        hard_reqs = set(defn.get("hard_requirements", []))

        signals_met = [s for s in signals_provided if s in required_types]
        signals_missing = [s for s in required_types if s not in signals_provided]

        # Check hard requirements
        hard_met = all(hr in signals_provided for hr in hard_reqs)

        min_signals = defn["min_signals"]
        meets_minimum = len(signals_met) >= min_signals

        approved = meets_minimum and hard_met

        # Confidence calculation
        if len(required_types) > 0:
            confidence = len(signals_met) / len(required_types)
        else:
            confidence = 0.5

        if not hard_met:
            confidence *= 0.3  # Heavy penalty for missing hard requirements

        confidence = round(min(1.0, max(0.0, confidence)), 3)

        # Build reasoning
        if approved:
            reasoning = (
                f"Scenario {code_upper} ({defn['name']}) APPROVED. "
                f"{len(signals_met)}/{min_signals} minimum signals met. "
                f"Signals: {', '.join(signals_met)}."
            )
            if hard_reqs:
                reasoning += " All hard requirements satisfied."
        else:
            reasons = []
            if not meets_minimum:
                reasons.append(
                    f"Only {len(signals_met)}/{min_signals} minimum signals met"
                )
            if not hard_met:
                missing_hard = [hr for hr in hard_reqs if hr not in signals_provided]
                reasons.append(
                    f"HARD REQUIREMENT(S) missing: {', '.join(missing_hard)}"
                )
            if signals_missing:
                reasons.append(
                    f"Missing signals: {', '.join(signals_missing)}"
                )
            reasoning = (
                f"Scenario {code_upper} ({defn['name']}) REJECTED. "
                f"{'; '.join(reasons)}."
            )

        # Append Day 1 notes
        if defn.get("day1_notes"):
            reasoning += f" Day 1 note: {defn['day1_notes']}"

        result = ScenarioValidation(
            code=code_upper,
            verdict=ScenarioVerdict.APPROVED if approved else ScenarioVerdict.REJECTED,
            signals_provided=signals_provided,
            signals_met=signals_met,
            signals_missing=signals_missing,
            hard_requirements_met=hard_met,
            reasoning=reasoning,
            confidence=confidence
        )

        self._store_validation(result)
        return result

    def suggest_scenario(self, signals_available: List[str]) -> ScenarioSuggestion:
        """Suggest the best-fit scenario based on available signals.

        Evaluates all scenarios against the signals and returns the one
        with the highest match confidence.

        Args:
            signals_available: List of all available signal codes.

        Returns:
            ScenarioSuggestion with recommended scenario and confidence.
        """
        scores: Dict[str, float] = {}
        signal_matches: Dict[str, List[str]] = {}

        for code, defn in self.scenario_defs.items():
            required = set(defn["required_signal_types"].keys())
            hard_reqs = set(defn.get("hard_requirements", []))

            matched = [s for s in signals_available if s in required]
            signal_matches[code] = matched

            min_req = defn["min_signals"]
            hard_met = all(hr in signals_available for hr in hard_reqs)

            if len(matched) >= min_req and hard_met:
                score = len(matched) / max(len(required), 1)
                score += 0.1 * (len(matched) - min_req)
            elif not hard_met and hard_reqs:
                score = (len(matched) / max(len(required), 1)) * 0.2
            else:
                score = (len(matched) / max(min_req, 1)) * 0.3

            scores[code] = round(min(1.0, score), 3)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_code, best_score = ranked[0]

        if best_score < 0.15:
            best_code = "S8"
            best_score = 0.5

        alternatives = [
            (code, score) for code, score in ranked[1:4] if score > 0.0
        ]

        defn = self.scenario_defs[best_code]
        reasoning = (
            f"Suggested scenario: {best_code} ({defn['name']}) "
            f"with confidence {best_score:.1%}. "
            f"Matched signals: {', '.join(signal_matches.get(best_code, []))}."
        )
        if best_code == "S8":
            reasoning += (
                " S8 (Chaos) assigned — insufficient signals for any "
                "other scenario. If S8 is primary, Top Strike confidence "
                "MUST be downgraded."
            )

        return ScenarioSuggestion(
            suggested_code=best_code,
            confidence=best_score,
            signal_match=signal_matches,
            reasoning=reasoning,
            alternatives=alternatives
        )

    def scenario_audit(self, predictions: List[Dict[str, Any]],
                       results: List[Dict[str, Any]]) -> ScenarioAuditResult:
        """Post-race scenario accuracy assessment by code.

        Args:
            predictions: List of dicts with keys:
                race_id, scenario_code, horse, confidence
            results: List of dicts with keys:
                race_id, actual_scenario, horse, finish_pos, won

        Returns:
            ScenarioAuditResult with accuracy metrics.
        """
        results_map = {r["race_id"]: r for r in results}
        code_stats: Dict[str, Dict[str, int]] = {}
        correct = 0
        total = 0
        lessons = []

        for pred in predictions:
            race_id = pred["race_id"]
            pred_code = pred["scenario_code"].upper()
            result = results_map.get(race_id)
            if not result:
                continue

            total += 1
            actual_code = result.get("actual_scenario", "").upper()
            is_correct = pred_code == actual_code

            if pred_code not in code_stats:
                code_stats[pred_code] = {"correct": 0, "total": 0}
            code_stats[pred_code]["total"] += 1

            if is_correct:
                code_stats[pred_code]["correct"] += 1
                correct += 1
            else:
                lesson = (
                    f"Race {race_id}: Predicted {pred_code}, "
                    f"actual {actual_code}. "
                )
                if pred_code == "S6" and actual_code != "S6":
                    lesson += (
                        "S6 overuse detected — Hidden Intent was "
                        "fiction in this case."
                    )
                elif pred_code == "S1" and actual_code == "S8":
                    lesson += (
                        "Conventional win predicted in a chaos race."
                    )
                lessons.append(lesson)

            # Store audit
            self._store_audit(pred, result, is_correct)

        accuracy = (correct / total * 100.0) if total > 0 else 0.0

        breakdown = {}
        for code, stats in code_stats.items():
            t = stats["total"]
            c = stats["correct"]
            breakdown[code] = {
                "correct": c,
                "total": t,
                "accuracy": round((c / t * 100.0) if t > 0 else 0.0, 1)
            }

        return ScenarioAuditResult(
            total_predictions=total,
            correct_scenarios=correct,
            accuracy_pct=round(accuracy, 1),
            code_breakdown=breakdown,
            lessons=lessons
        )

    def get_requirements(self, code: str) -> Dict[str, Any]:
        """Return the evidence checklist for a given scenario code.

        Args:
            code: Scenario code (S1-S8).

        Returns:
            Dict with scenario definition including signal types,
            minimums, hard requirements, and Day 1 notes.
        """
        code_upper = code.strip().upper()
        if code_upper not in self.scenario_defs:
            return {"error": f"Unknown scenario code: {code}"}
        return dict(self.scenario_defs[code_upper])

    def s6_hard_gate(self, signals: List[str]) -> ScenarioValidation:
        """Specific S6 check: REQUIRES market confirmation as mandatory signal.

        Day 1 lesson: "Hidden Intent without market confirmation is fiction."
        S6 was deployed 3 times at Wolverhampton based on single anecdotal
        signals and failed all 3 times.

        This method is a convenience wrapper that enforces the S6 hard gate
        with explicit messaging about the Day 1 failure.

        Args:
            signals: List of signal codes for S6 validation.

        Returns:
            ScenarioValidation — will be REJECTED if market_shortening
            is not in the signals list.
        """
        result = self.validate_scenario("S6", signals)

        # Add explicit S6 hard gate messaging
        if "market_shortening" not in signals:
            result = ScenarioValidation(
                code="S6",
                verdict=ScenarioVerdict.REJECTED,
                signals_provided=signals,
                signals_met=result.signals_met,
                signals_missing=result.signals_missing,
                hard_requirements_met=False,
                reasoning=(
                    "S6 (Hidden Intent) REJECTED — HARD GATE FAILURE. "
                    "market_shortening signal is MANDATORY for S6. "
                    "Day 1 lesson: 'Hidden Intent without market "
                    "confirmation is fiction.' S6 was deployed 3 times "
                    "at Wolverhampton without market confirmation and "
                    "failed all 3 times. Provide market_shortening "
                    "signal or downgrade to S7 (Conditioning Run) or "
                    "S8 (Chaos)."
                ),
                confidence=0.0
            )

        return result

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _store_validation(self, result: ScenarioValidation) -> None:
        """Store a scenario validation result."""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO sigma_evaluations (
                    scenario_code, scenario_name,
                    signals_provided, signals_met,
                    verdict, confidence, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.code,
                self.scenario_defs.get(result.code, {}).get("name", "Unknown"),
                json.dumps(result.signals_provided),
                json.dumps(result.signals_met),
                result.verdict.value,
                result.confidence,
                result.reasoning,
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
        finally:
            conn.close()

    def _store_audit(self, prediction: Dict[str, Any],
                     result: Dict[str, Any],
                     is_correct: bool) -> None:
        """Store a post-race scenario audit result."""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO sigma_evaluations (
                    race_id, scenario_code, scenario_name,
                    actual_scenario, scenario_correct,
                    horse, actual_finish_pos, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction.get("race_id"),
                prediction.get("scenario_code", "").upper(),
                self.scenario_defs.get(
                    prediction.get("scenario_code", "").upper(), {}
                ).get("name", "Unknown"),
                result.get("actual_scenario"),
                1 if is_correct else 0,
                prediction.get("horse"),
                result.get("finish_pos"),
                f"Predicted: {prediction.get('scenario_code')}, "
                f"Actual: {result.get('actual_scenario')}",
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------

    def get_scenario_accuracy_rates(self) -> Dict[str, Dict[str, Any]]:
        """Get historical accuracy rates for each scenario code.

        Returns:
            Dict mapping scenario code → {correct, total, accuracy_pct}.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT scenario_code,
                       COUNT(*) as total,
                       SUM(CASE WHEN scenario_correct = 1 THEN 1 ELSE 0 END) as correct
                FROM sigma_evaluations
                WHERE scenario_correct IS NOT NULL
                GROUP BY scenario_code
            """).fetchall()

            result = {}
            for row in rows:
                code = row["scenario_code"]
                total = row["total"]
                correct = row["correct"]
                result[code] = {
                    "correct": correct,
                    "total": total,
                    "accuracy_pct": round(
                        (correct / total * 100.0) if total > 0 else 0.0, 1
                    )
                }
            return result
        finally:
            conn.close()
