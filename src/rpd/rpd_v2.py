"""
VÉLØ Oracle Prime — Phase 1: RPD-C v2 Calibration Engine
=========================================================

Module: src/rpd/rpd_v2.py
Purpose: Tightened RPD-C tag system with mandatory evidence requirements.
         Addresses the Wolverhampton failure where tags were assigned
         narratively rather than from data.

Day 1 Lessons:
    - "Exhausted requires physiological evidence, not narrative convenience."
    - "H is not a throwaway — it means 'this horse runs to its rating'."
    - "A horse winning at 21.42 BSP is not running honestly to his mark."
    - "The S tag on a winner in a 5-runner field was a dismissal, not a flag."

Architecture: Integrates with existing SQLite memory engine (WAL mode).
              Stores tag assignments with evidence lists in rpd_validation table.

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
# Enums & Constants
# ---------------------------------------------------------------------------

class RPDTag(Enum):
    """Runner Profile Designation — Chaos (RPD-C) tags."""
    P = "P"  # Prep
    T = "T"  # Target
    E = "E"  # Exhausted
    H = "H"  # Honest
    S = "S"  # Speculative


class TagValidity(Enum):
    """Validation result for a tag assignment."""
    VALID = "VALID"
    INVALID = "INVALID"


# ---------------------------------------------------------------------------
# Evidence Definitions — The Core of v2
# ---------------------------------------------------------------------------

# Each tag has a set of possible evidence types and a minimum count required.
# Evidence types are identified by string codes for flexibility.

EVIDENCE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "P": {
        "name": "Prep",
        "description": (
            "Horse is being prepared / given an educational run. "
            "Not expected to deliver peak performance today."
        ),
        "min_evidence": 2,
        "evidence_types": {
            "trainer_prep_pattern": (
                "Trainer has documented prep-run pattern "
                "(historical data showing deliberate non-competitive entries)"
            ),
            "long_absence": (
                "Horse returning from 60+ day break"
            ),
            "class_drop_no_gear": (
                "Significant class drop with no gear changes "
                "(suggests lack of intent to win)"
            ),
            "jockey_below_standard": (
                "Jockey booking below trainer's usual standard "
                "(conditional jockey on a yard that uses top riders)"
            ),
        },
        "blockers": {
            "market_shortening": (
                "CANNOT assign P if horse is shortening in market. "
                "Market says 'ready' — contradicts prep narrative."
            ),
        },
        "day1_lesson": None,
    },
    "T": {
        "name": "Target",
        "description": (
            "Horse is being targeted at this race. Connections intend "
            "to win. Peak readiness indicators present."
        ),
        "min_evidence": 2,
        "evidence_types": {
            "peak_fitness": (
                "Peak fitness window — 3-5 runs into campaign"
            ),
            "class_appropriate": (
                "Class appropriate or dropping — not outclassed"
            ),
            "course_distance_proven": (
                "Course & distance winner or proven performer"
            ),
            "first_choice_jockey": (
                "First-choice jockey booked (stable's go-to rider)"
            ),
            "gear_additions": (
                "Gear additions suggesting intent "
                "(first-time visor, tongue-tie, cheekpieces)"
            ),
        },
        "blockers": {},
        "confidence_boost": {
            "trainer_track_strike": (
                "Trainer strike rate >25% at this track — "
                "CONFIDENCE BOOST applied"
            ),
        },
        "day1_lesson": None,
    },
    "E": {
        "name": "Exhausted",
        "description": (
            "Horse showing signs of physical/mental fatigue. "
            "Performance decline expected."
        ),
        "min_evidence": 2,
        "evidence_types": {
            "long_campaign": (
                "5+ runs in current campaign without a break"
            ),
            "declining_positions": (
                "Declining finishing positions over last 3 runs"
            ),
            "weight_increase": (
                "Weight increase without class drop"
            ),
            "quick_turnaround": (
                "Quick turnaround — less than 10 days since last run"
            ),
        },
        "blockers": {
            "won_last_time": (
                "CANNOT assign E if horse won last time out. "
                "A recent winner is not exhausted."
            ),
            "market_shortening": (
                "CANNOT assign E if horse is shortening in market. "
                "Market contradicts exhaustion narrative."
            ),
        },
        "day1_lesson": (
            "Exhausted requires physiological evidence, not narrative "
            "convenience. At Wolverhampton, Alondra was tagged E despite "
            "being the shortening favourite. She finished 2nd."
        ),
    },
    "H": {
        "name": "Honest",
        "description": (
            "Horse runs consistently to its rating. Reliable but unlikely "
            "to dramatically outperform. This is the DEFAULT tag when "
            "evidence is insufficient for P/T/E/S."
        ),
        "min_evidence": 1,
        "evidence_types": {
            "consistent_form": (
                "Consistent form profile — finishes within 2-3 positions "
                "of expected rating, no dramatic swings"
            ),
        },
        "blockers": {},
        "day1_lesson": (
            "H is not a throwaway — it means 'this horse runs to its "
            "rating'. At Wolverhampton, Faster Bee was tagged H with "
            "'lacks capacity to win' — he won at 21.42 BSP."
        ),
    },
    "S": {
        "name": "Speculative",
        "description": (
            "Highest uncertainty tag. Insufficient data to classify "
            "with confidence. Selections tagged S should NEVER be "
            "Top Strike on chaos tracks."
        ),
        "min_evidence": 1,
        "evidence_types": {
            "first_time_conditions": (
                "First-time surface/distance — no form reference"
            ),
            "no_form_reference": (
                "No form reference at this level/class"
            ),
            "market_volatility": (
                "Significant market volatility — erratic price movements"
            ),
            "unproven_combination": (
                "Unproven trainer/horse combination at this track"
            ),
        },
        "blockers": {},
        "chaos_track_rule": (
            "S-tagged horses should NEVER be Top Strike on chaos tracks "
            "(chaos rating >= 3). Day 1: Cressida Wildes was tagged S "
            "and dismissed — she won at 9.71 BSP."
        ),
        "day1_lesson": (
            "The S tag on a winner in a 5-runner field was a dismissal, "
            "not a flag. In small fields on chaos tracks, every runner "
            "is a live contender."
        ),
    },
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class TagValidation:
    """Result of validating a proposed tag assignment.

    Attributes:
        horse: Name of the horse.
        proposed_tag: The tag that was proposed.
        validity: VALID or INVALID.
        evidence_provided: List of evidence codes provided.
        evidence_met: List of evidence codes that matched requirements.
        evidence_missing: List of evidence codes still needed.
        blockers_triggered: List of blocker reasons that prevent this tag.
        reasoning: Human-readable explanation of the validation result.
        confidence: Confidence score 0.0-1.0.
    """
    horse: str
    proposed_tag: RPDTag
    validity: TagValidity
    evidence_provided: List[str]
    evidence_met: List[str]
    evidence_missing: List[str]
    blockers_triggered: List[str]
    reasoning: str
    confidence: float = 0.0


@dataclass
class TagSuggestion:
    """Suggested tag based on available evidence.

    Attributes:
        horse: Name of the horse.
        suggested_tag: The recommended RPD-C tag.
        confidence: Confidence score 0.0-1.0.
        evidence_match: Dict mapping tag → list of matched evidence.
        reasoning: Human-readable explanation.
        alternatives: List of (tag, confidence) tuples for runner-up tags.
    """
    horse: str
    suggested_tag: RPDTag
    confidence: float
    evidence_match: Dict[str, List[str]]
    reasoning: str
    alternatives: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class TagAuditResult:
    """Post-race audit of tag accuracy.

    Attributes:
        total_predictions: Total number of predictions audited.
        correct_tags: Number of tags deemed accurate post-race.
        accuracy_pct: Overall tag accuracy percentage.
        tag_breakdown: Dict mapping tag → {correct, total, accuracy}.
        lessons: List of lessons learned from incorrect tags.
    """
    total_predictions: int
    correct_tags: int
    accuracy_pct: float
    tag_breakdown: Dict[str, Dict[str, Any]]
    lessons: List[str]


# ---------------------------------------------------------------------------
# RPD-C v2 Engine
# ---------------------------------------------------------------------------

class RPDv2Engine:
    """Tightened RPD-C tag system with mandatory evidence requirements.

    Every tag assignment now requires MINIMUM EVIDENCE before it can be
    applied. This prevents the Wolverhampton failure mode where tags
    were assigned based on narrative rather than data.

    The engine enforces:
        1. Minimum evidence counts per tag.
        2. Blocker conditions that prevent tag assignment.
        3. Confidence scoring based on evidence quality.
        4. Post-race audit capability for continuous learning.

    Usage:
        >>> engine = RPDv2Engine(db_path="velo.db")
        >>> result = engine.validate_tag("Alondra", "E",
        ...     ["long_campaign", "declining_positions"])
        >>> suggestion = engine.suggest_tag("Cressida Wildes",
        ...     ["consistent_form", "first_time_conditions"])
    """

    def __init__(self, db_path: str = "velo_oracle.db"):
        """Initialise the RPD-C v2 Engine.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.evidence_defs = EVIDENCE_DEFINITIONS
        self._evidence_weights: Dict[str, float] = {}
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
        """Create or migrate the rpd_validation table."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rpd_validation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    horse TEXT NOT NULL,
                    race_id TEXT,
                    track TEXT,
                    race_date TEXT,
                    proposed_tag TEXT NOT NULL,
                    final_tag TEXT,
                    validity TEXT,
                    evidence_provided TEXT,
                    evidence_met TEXT,
                    evidence_missing TEXT,
                    blockers_triggered TEXT,
                    confidence REAL DEFAULT 0.0,
                    reasoning TEXT,
                    actual_finish_pos INTEGER,
                    actual_bsp REAL,
                    tag_correct INTEGER,
                    post_race_notes TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rpd_validation_horse
                ON rpd_validation(horse)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_rpd_validation_tag
                ON rpd_validation(proposed_tag)
            """)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Core Methods
    # ------------------------------------------------------------------

    def validate_tag(self, horse: str, tag: str,
                     evidence_list: List[str],
                     market_shortening: bool = False,
                     won_last_time: bool = False) -> TagValidation:
        """Validate whether a proposed tag meets minimum evidence requirements.

        Args:
            horse: Name of the horse.
            tag: Proposed RPD-C tag (P/T/E/H/S).
            evidence_list: List of evidence code strings.
            market_shortening: Whether the horse is shortening in market.
            won_last_time: Whether the horse won its last race.

        Returns:
            TagValidation with VALID/INVALID verdict and full reasoning.
        """
        tag_upper = tag.strip().upper()
        if tag_upper not in self.evidence_defs:
            return TagValidation(
                horse=horse,
                proposed_tag=RPDTag(tag_upper) if tag_upper in RPDTag.__members__ else RPDTag.H,
                validity=TagValidity.INVALID,
                evidence_provided=evidence_list,
                evidence_met=[],
                evidence_missing=[],
                blockers_triggered=[f"Unknown tag: {tag}"],
                reasoning=f"Tag '{tag}' is not a valid RPD-C tag.",
                confidence=0.0
            )

        tag_def = self.evidence_defs[tag_upper]
        rpd_tag = RPDTag(tag_upper)

        # Check blockers
        blockers_triggered = []
        if market_shortening and "market_shortening" in tag_def.get("blockers", {}):
            blockers_triggered.append(tag_def["blockers"]["market_shortening"])
        if won_last_time and "won_last_time" in tag_def.get("blockers", {}):
            blockers_triggered.append(tag_def["blockers"]["won_last_time"])

        if blockers_triggered:
            result = TagValidation(
                horse=horse,
                proposed_tag=rpd_tag,
                validity=TagValidity.INVALID,
                evidence_provided=evidence_list,
                evidence_met=[],
                evidence_missing=list(tag_def["evidence_types"].keys()),
                blockers_triggered=blockers_triggered,
                reasoning=(
                    f"Tag '{tag_upper}' ({tag_def['name']}) BLOCKED for "
                    f"{horse}: {'; '.join(blockers_triggered)}"
                ),
                confidence=0.0
            )
            self._store_validation(result)
            return result

        # Check evidence
        valid_evidence_codes = set(tag_def["evidence_types"].keys())
        evidence_met = [e for e in evidence_list if e in valid_evidence_codes]
        evidence_missing = [e for e in valid_evidence_codes if e not in evidence_list]
        min_required = tag_def["min_evidence"]

        is_valid = len(evidence_met) >= min_required

        # Calculate confidence
        if len(valid_evidence_codes) > 0:
            base_confidence = len(evidence_met) / len(valid_evidence_codes)
        else:
            base_confidence = 0.5

        # Confidence boost for T tag
        if tag_upper == "T" and "trainer_track_strike" in evidence_list:
            base_confidence = min(1.0, base_confidence + 0.15)

        # Apply evidence weights if calibrated
        for ev in evidence_met:
            weight = self._evidence_weights.get(f"{tag_upper}_{ev}", 1.0)
            base_confidence *= weight

        confidence = round(min(1.0, max(0.0, base_confidence)), 3)

        if is_valid:
            reasoning = (
                f"Tag '{tag_upper}' ({tag_def['name']}) VALID for {horse}. "
                f"{len(evidence_met)}/{min_required} minimum evidence met. "
                f"Evidence: {', '.join(evidence_met)}."
            )
        else:
            reasoning = (
                f"Tag '{tag_upper}' ({tag_def['name']}) INVALID for {horse}. "
                f"Only {len(evidence_met)}/{min_required} minimum evidence met. "
                f"Missing: {', '.join(evidence_missing[:min_required - len(evidence_met)])}."
            )

        # Append Day 1 lesson if relevant
        if tag_def.get("day1_lesson"):
            reasoning += f" Day 1 lesson: {tag_def['day1_lesson']}"

        result = TagValidation(
            horse=horse,
            proposed_tag=rpd_tag,
            validity=TagValidity.VALID if is_valid else TagValidity.INVALID,
            evidence_provided=evidence_list,
            evidence_met=evidence_met,
            evidence_missing=evidence_missing,
            blockers_triggered=blockers_triggered,
            reasoning=reasoning,
            confidence=confidence
        )

        self._store_validation(result)
        return result

    def suggest_tag(self, horse: str, evidence_list: List[str],
                    market_shortening: bool = False,
                    won_last_time: bool = False) -> TagSuggestion:
        """Suggest the best-fit RPD-C tag based on available evidence.

        Evaluates all tags against the evidence and returns the one with
        the highest confidence. If no tag meets minimum evidence, defaults
        to H (Honest).

        Args:
            horse: Name of the horse.
            evidence_list: List of evidence code strings.
            market_shortening: Whether the horse is shortening in market.
            won_last_time: Whether the horse won its last race.

        Returns:
            TagSuggestion with recommended tag and confidence.
        """
        scores: Dict[str, float] = {}
        evidence_matches: Dict[str, List[str]] = {}

        for tag_code, tag_def in self.evidence_defs.items():
            # Check blockers
            blocked = False
            if market_shortening and "market_shortening" in tag_def.get("blockers", {}):
                blocked = True
            if won_last_time and "won_last_time" in tag_def.get("blockers", {}):
                blocked = True

            if blocked:
                scores[tag_code] = 0.0
                evidence_matches[tag_code] = []
                continue

            valid_codes = set(tag_def["evidence_types"].keys())
            matched = [e for e in evidence_list if e in valid_codes]
            evidence_matches[tag_code] = matched

            min_req = tag_def["min_evidence"]
            if len(matched) >= min_req:
                score = len(matched) / max(len(valid_codes), 1)
                # Boost for exceeding minimum
                score += 0.1 * (len(matched) - min_req)
            else:
                # Below minimum — heavily penalise
                score = (len(matched) / max(min_req, 1)) * 0.3

            scores[tag_code] = round(min(1.0, score), 3)

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # If best score is very low, default to H
        best_tag, best_score = ranked[0]
        if best_score < 0.2:
            best_tag = "H"
            best_score = 0.4  # Default confidence for H

        alternatives = [
            (tag, score) for tag, score in ranked[1:4] if score > 0.0
        ]

        reasoning_parts = [
            f"Suggested tag for {horse}: {best_tag} "
            f"({self.evidence_defs[best_tag]['name']}) "
            f"with confidence {best_score:.1%}."
        ]
        if evidence_matches.get(best_tag):
            reasoning_parts.append(
                f"Matched evidence: {', '.join(evidence_matches[best_tag])}."
            )
        if best_tag == "H" and best_score <= 0.4:
            reasoning_parts.append(
                "H assigned as default — insufficient evidence for "
                "any other tag. H means 'runs to rating'."
            )

        return TagSuggestion(
            horse=horse,
            suggested_tag=RPDTag(best_tag),
            confidence=best_score,
            evidence_match=evidence_matches,
            reasoning=" ".join(reasoning_parts),
            alternatives=alternatives
        )

    def tag_audit(self, predictions: List[Dict[str, Any]],
                  results: List[Dict[str, Any]]) -> TagAuditResult:
        """Post-race tag accuracy assessment.

        Compares predicted tags against actual race outcomes to measure
        RPD-C accuracy and generate lessons.

        Args:
            predictions: List of dicts with keys:
                horse, tag, confidence, role (top_strike/value/danger/etc.)
            results: List of dicts with keys:
                horse, finish_pos, bsp, won (bool)

        Returns:
            TagAuditResult with accuracy metrics and lessons.
        """
        results_map = {r["horse"]: r for r in results}
        tag_stats: Dict[str, Dict[str, int]] = {
            t: {"correct": 0, "total": 0} for t in RPDTag.__members__
        }
        correct = 0
        total = 0
        lessons = []

        for pred in predictions:
            horse = pred["horse"]
            tag = pred["tag"].upper()
            result = results_map.get(horse)
            if not result:
                continue

            total += 1
            finish = result.get("finish_pos", 99)
            won = result.get("won", False)
            bsp = result.get("bsp", 0)

            tag_correct = self._assess_tag_accuracy(tag, finish, won, bsp)

            if tag in tag_stats:
                tag_stats[tag]["total"] += 1
                if tag_correct:
                    tag_stats[tag]["correct"] += 1
                    correct += 1
                else:
                    lesson = self._generate_tag_lesson(horse, tag, finish, won, bsp)
                    if lesson:
                        lessons.append(lesson)

            # Store audit result
            self._store_audit(horse, tag, tag_correct, finish, bsp)

        accuracy = (correct / total * 100.0) if total > 0 else 0.0

        breakdown = {}
        for tag, stats in tag_stats.items():
            t = stats["total"]
            c = stats["correct"]
            breakdown[tag] = {
                "correct": c,
                "total": t,
                "accuracy": round((c / t * 100.0) if t > 0 else 0.0, 1)
            }

        return TagAuditResult(
            total_predictions=total,
            correct_tags=correct,
            accuracy_pct=round(accuracy, 1),
            tag_breakdown=breakdown,
            lessons=lessons
        )

    def get_evidence_requirements(self, tag: str) -> Dict[str, Any]:
        """Return the evidence checklist for a given tag.

        Args:
            tag: RPD-C tag code (P/T/E/H/S).

        Returns:
            Dict with tag definition including evidence types, minimums,
            blockers, and Day 1 lessons.
        """
        tag_upper = tag.strip().upper()
        if tag_upper not in self.evidence_defs:
            return {"error": f"Unknown tag: {tag}"}
        return dict(self.evidence_defs[tag_upper])

    def recalibrate_from_sigma(self, sigma_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Adjust evidence weights based on sigma evaluation results.

        Analyses sigma audit data to identify which evidence types are
        most predictive and adjusts internal weights accordingly.

        Args:
            sigma_data: List of sigma evaluation dicts with keys:
                horse, tag, evidence_used (list), tag_correct (bool),
                finish_pos, bsp

        Returns:
            Dict with recalibration summary: weights_updated, adjustments.
        """
        # Count evidence type effectiveness
        evidence_performance: Dict[str, Dict[str, int]] = {}

        for entry in sigma_data:
            tag = entry.get("tag", "").upper()
            evidence_used = entry.get("evidence_used", [])
            tag_correct = entry.get("tag_correct", False)

            for ev in evidence_used:
                key = f"{tag}_{ev}"
                if key not in evidence_performance:
                    evidence_performance[key] = {"correct": 0, "total": 0}
                evidence_performance[key]["total"] += 1
                if tag_correct:
                    evidence_performance[key]["correct"] += 1

        # Calculate new weights
        adjustments = {}
        for key, perf in evidence_performance.items():
            if perf["total"] >= 3:  # Minimum sample size
                accuracy = perf["correct"] / perf["total"]
                # Weight: 0.5 (poor) to 1.5 (excellent)
                weight = 0.5 + accuracy
                self._evidence_weights[key] = weight
                adjustments[key] = {
                    "accuracy": round(accuracy, 3),
                    "weight": round(weight, 3),
                    "sample_size": perf["total"]
                }

        return {
            "weights_updated": len(adjustments),
            "adjustments": adjustments,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _assess_tag_accuracy(self, tag: str, finish: int,
                             won: bool, bsp: float) -> bool:
        """Determine if a tag was accurate given the race result.

        Args:
            tag: The RPD-C tag assigned.
            finish: Finishing position.
            won: Whether the horse won.
            bsp: Betfair Starting Price.

        Returns:
            True if the tag was a reasonable assessment.
        """
        if tag == "T":
            # Target should win or finish in top 2
            return finish <= 2
        elif tag == "P":
            # Prep should NOT win (if it does, tag was wrong)
            return not won
        elif tag == "E":
            # Exhausted should finish poorly (bottom half or worse)
            return finish >= 4 and not won
        elif tag == "H":
            # Honest should finish mid-pack, not win at big prices
            # If won at short price, H could still be valid
            if won and bsp > 10.0:
                return False  # H horse shouldn't win at big prices
            return True  # H is generous — most results are "honest"
        elif tag == "S":
            # Speculative — hard to assess, but if it wins, S was wrong
            # (should have been elevated)
            return not won
        return False

    def _generate_tag_lesson(self, horse: str, tag: str,
                             finish: int, won: bool,
                             bsp: float) -> Optional[str]:
        """Generate a lesson from an incorrect tag.

        Args:
            horse: Name of the horse.
            tag: The incorrect tag.
            finish: Finishing position.
            won: Whether the horse won.
            bsp: BSP.

        Returns:
            Lesson string or None.
        """
        if tag == "E" and won:
            return (
                f"LESSON: {horse} tagged E (Exhausted) but WON. "
                f"Exhausted requires physiological evidence. "
                f"Review evidence chain."
            )
        if tag == "H" and won and bsp > 10.0:
            return (
                f"LESSON: {horse} tagged H (Honest) but won at "
                f"{bsp:.2f} BSP. H means 'runs to rating' — a win "
                f"at this price suggests the tag underestimated ability."
            )
        if tag == "S" and won:
            return (
                f"LESSON: {horse} tagged S (Speculative) but WON at "
                f"{bsp:.2f} BSP. The S tag was a dismissal, not a flag. "
                f"Review whether evidence supported a higher tag."
            )
        if tag == "T" and finish > 3:
            return (
                f"LESSON: {horse} tagged T (Target) but finished "
                f"{finish}. Target signals may have been misread."
            )
        if tag == "P" and won:
            return (
                f"LESSON: {horse} tagged P (Prep) but WON. "
                f"Prep tag should not be assigned to market-ready horses."
            )
        return None

    def _store_validation(self, result: TagValidation) -> None:
        """Store a tag validation result in the database."""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO rpd_validation (
                    horse, proposed_tag, validity,
                    evidence_provided, evidence_met, evidence_missing,
                    blockers_triggered, confidence, reasoning, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.horse,
                result.proposed_tag.value,
                result.validity.value,
                json.dumps(result.evidence_provided),
                json.dumps(result.evidence_met),
                json.dumps(result.evidence_missing),
                json.dumps(result.blockers_triggered),
                result.confidence,
                result.reasoning,
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
        finally:
            conn.close()

    def _store_audit(self, horse: str, tag: str,
                     tag_correct: bool, finish: int,
                     bsp: float) -> None:
        """Store a post-race audit result."""
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO rpd_validation (
                    horse, proposed_tag, final_tag,
                    actual_finish_pos, actual_bsp, tag_correct,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                horse, tag, tag,
                finish, bsp,
                1 if tag_correct else 0,
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
        finally:
            conn.close()
