"""
VÉLØ Oracle Prime — Phase 1: Integration Module
=================================================

Module: src/phase1_integration.py
Purpose: Wires all four Phase 1 modules together and provides unified
         pre-race and post-race interfaces.

This module is the operational bridge between the four Phase 1 engines:
    1. Market Constraint Engine — BSP drift hard gate
    2. RPD-C v2 Calibration Engine — evidence-based tag system
    3. Scenario Evidence Gate — scenario code validation
    4. Track Profile Database — pre-loaded track intelligence

Usage:
    >>> from src.phase1_integration import Phase1Integration
    >>> p1 = Phase1Integration(db_path="velo_oracle.db")
    >>> brief = p1.pre_race_check(race_data)
    >>> audit = p1.post_race_audit(predictions, results)

Author: VÉLØ Oracle Prime — Phase 1 Build
Date: 2026-02-16
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.constraints.market_engine import (
    MarketConstraintEngine, MarketThresholds,
    DriftClassification, ConstraintVerdict
)
from src.rpd.rpd_v2 import RPDv2Engine, RPDTag, TagValidity
from src.scenarios.evidence_gate import (
    ScenarioEvidenceGate, ScenarioVerdict
)
from src.tracks.track_profiles import TrackProfileDB


class Phase1Integration:
    """Unified Phase 1 integration layer.

    Wires all four Phase 1 modules together and provides:
        - pre_race_check(): Consolidated pre-race intelligence brief.
        - post_race_audit(): Consolidated post-race audit across all modules.

    This is the single entry point for Phase 1 functionality.

    Attributes:
        market_engine: MarketConstraintEngine instance.
        rpd_engine: RPDv2Engine instance.
        scenario_gate: ScenarioEvidenceGate instance.
        track_db: TrackProfileDB instance.
    """

    def __init__(self, db_path: str = "velo_oracle.db",
                 market_thresholds: Optional[MarketThresholds] = None):
        """Initialise all Phase 1 modules.

        Args:
            db_path: Path to the SQLite database file (shared across modules).
            market_thresholds: Optional custom market thresholds.
        """
        self.db_path = db_path
        self.market_engine = MarketConstraintEngine(
            db_path=db_path, thresholds=market_thresholds
        )
        self.rpd_engine = RPDv2Engine(db_path=db_path)
        self.scenario_gate = ScenarioEvidenceGate(db_path=db_path)
        self.track_db = TrackProfileDB(db_path=db_path, auto_load=True)

    def pre_race_check(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all four modules and produce a consolidated pre-race brief.

        This is the primary pre-race entry point. It:
            1. Retrieves track intelligence.
            2. Generates market constraint report for all runners.
            3. Validates proposed RPD-C tags for each runner.
            4. Validates proposed scenario codes.
            5. Produces a consolidated intelligence brief.

        Args:
            race_data: Dict with keys:
                - race_id (str): Unique race identifier.
                - track (str): Track name.
                - distance (str): Race distance.
                - going (str): Official going.
                - race_date (str): Date of the race.
                - runners (list of dict): Each runner has:
                    - horse (str)
                    - morning_price (float)
                    - bsp (float, estimated or actual)
                    - isp (float, optional)
                    - is_favourite (bool)
                    - proposed_tag (str, optional): Proposed RPD-C tag
                    - tag_evidence (list of str, optional): Evidence for tag
                    - market_shortening (bool, optional)
                    - won_last_time (bool, optional)
                - proposed_scenario (str, optional): Proposed scenario code
                - scenario_signals (list of str, optional): Signals for scenario

        Returns:
            Dict with consolidated pre-race intelligence:
                - race_id, track, distance, going
                - track_context (str): Track intelligence brief
                - chaos_rating (int): Track chaos rating
                - market_report (dict): Full market constraint report
                - runner_assessments (list): Per-runner tag validations
                - scenario_validation (dict): Scenario validation result
                - alerts (list): Critical alerts requiring attention
                - summary (str): Executive summary
        """
        track = race_data.get("track", "Unknown")
        distance = race_data.get("distance", "Unknown")
        going = race_data.get("going", "Unknown")
        race_id = race_data.get("race_id", "unknown")
        runners = race_data.get("runners", [])

        # 1. Track Intelligence
        track_context = self.track_db.pre_race_context(track, distance, going)
        chaos_rating = self.track_db.get_chaos_rating(track) or 3

        # 2. Market Constraint Report
        market_report = self.market_engine.generate_market_report(race_data)

        # 3. RPD-C Tag Validation for each runner
        runner_assessments = []
        alerts = []

        for runner in runners:
            horse = runner.get("horse", "Unknown")
            proposed_tag = runner.get("proposed_tag")
            tag_evidence = runner.get("tag_evidence", [])
            market_shortening = runner.get("market_shortening", False)
            won_last_time = runner.get("won_last_time", False)
            is_favourite = runner.get("is_favourite", False)

            assessment = {"horse": horse}

            # Market constraint check
            morning_price = runner.get("morning_price", 0)
            bsp = runner.get("bsp", 0)

            if morning_price > 0 and bsp > 0:
                drift = self.market_engine.analyse_drift(
                    horse, morning_price, bsp
                )
                assessment["drift"] = {
                    "classification": drift.classification.value,
                    "pct_change": drift.pct_change,
                    "description": drift.description
                }

                # Auto-detect market shortening for tag validation
                if drift.classification == DriftClassification.STEAMER:
                    market_shortening = True

                # Favourite override check
                if proposed_tag and is_favourite:
                    override_check = self.market_engine.favourite_override_check(
                        horse, proposed_tag,
                        {"morning_price": morning_price, "bsp": bsp,
                         "is_favourite": is_favourite}
                    )
                    if override_check.verdict == ConstraintVerdict.BLOCKED:
                        alerts.append(
                            f"🚫 BLOCKED: {override_check.message}"
                        )
                        assessment["favourite_override"] = {
                            "verdict": "BLOCKED",
                            "message": override_check.message
                        }

                # BSP/ISP divergence
                isp = runner.get("isp")
                if isp and isp > 0:
                    divergence = self.market_engine.bsp_isp_divergence(
                        horse, bsp, isp
                    )
                    assessment["divergence"] = {
                        "pct": divergence.divergence_pct,
                        "flagged": divergence.flagged,
                        "interpretation": divergence.interpretation
                    }
                    if divergence.flagged:
                        alerts.append(
                            f"⚠ DIVERGENCE: {divergence.interpretation}"
                        )

            # Tag validation
            if proposed_tag:
                tag_result = self.rpd_engine.validate_tag(
                    horse, proposed_tag, tag_evidence,
                    market_shortening=market_shortening,
                    won_last_time=won_last_time
                )
                assessment["tag_validation"] = {
                    "proposed": proposed_tag,
                    "validity": tag_result.validity.value,
                    "confidence": tag_result.confidence,
                    "reasoning": tag_result.reasoning,
                    "evidence_met": tag_result.evidence_met,
                    "evidence_missing": tag_result.evidence_missing,
                    "blockers": tag_result.blockers_triggered
                }
                if tag_result.validity == TagValidity.INVALID:
                    alerts.append(
                        f"⚠ TAG INVALID: {tag_result.reasoning}"
                    )
            else:
                # Suggest a tag
                suggestion = self.rpd_engine.suggest_tag(
                    horse, tag_evidence,
                    market_shortening=market_shortening,
                    won_last_time=won_last_time
                )
                assessment["tag_suggestion"] = {
                    "suggested": suggestion.suggested_tag.value,
                    "confidence": suggestion.confidence,
                    "reasoning": suggestion.reasoning
                }

            runner_assessments.append(assessment)

        # 4. Scenario Validation
        scenario_validation = None
        proposed_scenario = race_data.get("proposed_scenario")
        scenario_signals = race_data.get("scenario_signals", [])

        if proposed_scenario:
            if proposed_scenario.upper() == "S6":
                scenario_result = self.scenario_gate.s6_hard_gate(
                    scenario_signals
                )
            else:
                scenario_result = self.scenario_gate.validate_scenario(
                    proposed_scenario, scenario_signals
                )
            scenario_validation = {
                "code": scenario_result.code,
                "verdict": scenario_result.verdict.value,
                "confidence": scenario_result.confidence,
                "reasoning": scenario_result.reasoning,
                "signals_met": scenario_result.signals_met,
                "signals_missing": scenario_result.signals_missing
            }
            if scenario_result.verdict == ScenarioVerdict.REJECTED:
                alerts.append(
                    f"🚫 SCENARIO REJECTED: {scenario_result.reasoning}"
                )
        elif scenario_signals:
            suggestion = self.scenario_gate.suggest_scenario(scenario_signals)
            scenario_validation = {
                "suggested_code": suggestion.suggested_code,
                "confidence": suggestion.confidence,
                "reasoning": suggestion.reasoning,
                "alternatives": suggestion.alternatives
            }

        # 5. Chaos Track Warning
        if chaos_rating >= 4:
            alerts.insert(0,
                f"🔴 HIGH CHAOS TRACK ({chaos_rating}/5) — "
                f"RPD-C layer MANDATORY. Reduce Top Strike confidence. "
                f"S-tagged horses CANNOT be Top Strike."
            )
        elif chaos_rating >= 3:
            alerts.insert(0,
                f"🟡 ELEVATED CHAOS ({chaos_rating}/5) — "
                f"RPD-C layer recommended. Review all dismissals."
            )

        # 6. Executive Summary
        summary_parts = [
            f"PRE-RACE CHECK: {track} — {distance} — {going}",
            f"Chaos Rating: {chaos_rating}/5",
            f"Runners: {len(runners)}",
            f"Alerts: {len(alerts)}",
        ]

        steamer_count = market_report.get("constraint_counts", {}).get("steamers", 0)
        drifter_count = market_report.get("constraint_counts", {}).get("drifters", 0)
        if steamer_count:
            summary_parts.append(f"Steamers: {steamer_count}")
        if drifter_count:
            summary_parts.append(f"Drifters: {drifter_count}")

        return {
            "race_id": race_id,
            "track": track,
            "distance": distance,
            "going": going,
            "track_context": track_context,
            "chaos_rating": chaos_rating,
            "market_report": market_report,
            "runner_assessments": runner_assessments,
            "scenario_validation": scenario_validation,
            "alerts": alerts,
            "summary": " | ".join(summary_parts),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def post_race_audit(self, predictions: List[Dict[str, Any]],
                        results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run all four modules' audit functions for post-race analysis.

        This is the primary post-race entry point. It:
            1. Audits RPD-C tag accuracy.
            2. Audits scenario code accuracy.
            3. Generates market behaviour analysis.
            4. Produces consolidated audit report.

        Args:
            predictions: List of prediction dicts with keys:
                - horse (str)
                - tag (str): RPD-C tag assigned
                - confidence (float)
                - role (str): top_strike / value / danger / etc.
                - scenario_code (str)
                - race_id (str)
            results: List of result dicts with keys:
                - horse (str)
                - finish_pos (int)
                - bsp (float)
                - won (bool)
                - actual_scenario (str, optional)
                - race_id (str)

        Returns:
            Dict with consolidated audit:
                - tag_audit: RPD-C tag accuracy results
                - scenario_audit: Scenario code accuracy results
                - combined_accuracy: Overall system accuracy metrics
                - lessons: Combined lessons from all modules
                - recommendations: Actionable recommendations
        """
        # 1. RPD-C Tag Audit
        tag_audit = self.rpd_engine.tag_audit(predictions, results)

        # 2. Scenario Audit
        scenario_predictions = [
            p for p in predictions if p.get("scenario_code")
        ]
        scenario_results = [
            r for r in results if r.get("actual_scenario")
        ]
        scenario_audit = self.scenario_gate.scenario_audit(
            scenario_predictions, scenario_results
        )

        # 3. Combined Lessons
        all_lessons = []
        all_lessons.extend(tag_audit.lessons)
        all_lessons.extend(scenario_audit.lessons)

        # 4. Recommendations
        recommendations = []

        if tag_audit.accuracy_pct < 50:
            recommendations.append(
                "RPD-C tag accuracy below 50% — review evidence "
                "requirements and consider recalibration."
            )

        # Check for specific tag failures
        for tag, stats in tag_audit.tag_breakdown.items():
            if stats["total"] >= 3 and stats["accuracy"] < 30:
                recommendations.append(
                    f"Tag '{tag}' accuracy critically low "
                    f"({stats['accuracy']:.0f}%) — review evidence "
                    f"definitions for this tag."
                )

        if scenario_audit.accuracy_pct < 40:
            recommendations.append(
                "Scenario accuracy below 40% — review signal "
                "requirements and consider S8 as default for "
                "chaos tracks."
            )

        # Check for S6 overuse
        s6_stats = scenario_audit.code_breakdown.get("S6", {})
        if s6_stats.get("total", 0) >= 2 and s6_stats.get("accuracy", 100) < 30:
            recommendations.append(
                "S6 (Hidden Intent) overuse detected with low accuracy. "
                "Enforce market_shortening hard requirement."
            )

        return {
            "tag_audit": {
                "total": tag_audit.total_predictions,
                "correct": tag_audit.correct_tags,
                "accuracy_pct": tag_audit.accuracy_pct,
                "breakdown": tag_audit.tag_breakdown,
                "lessons": tag_audit.lessons
            },
            "scenario_audit": {
                "total": scenario_audit.total_predictions,
                "correct": scenario_audit.correct_scenarios,
                "accuracy_pct": scenario_audit.accuracy_pct,
                "breakdown": scenario_audit.code_breakdown,
                "lessons": scenario_audit.lessons
            },
            "combined_accuracy": {
                "tag_accuracy": tag_audit.accuracy_pct,
                "scenario_accuracy": scenario_audit.accuracy_pct,
                "overall": round(
                    (tag_audit.accuracy_pct + scenario_audit.accuracy_pct) / 2,
                    1
                ) if (tag_audit.total_predictions > 0
                      and scenario_audit.total_predictions > 0)
                else tag_audit.accuracy_pct or scenario_audit.accuracy_pct
            },
            "lessons": all_lessons,
            "recommendations": recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Return the current status of all Phase 1 modules.

        Returns:
            Dict with module status information.
        """
        track_count = self.track_db.get_track_count()
        aw_tracks = len(self.track_db.get_aw_tracks())

        return {
            "phase": "Phase 1",
            "version": "1.0.0",
            "modules": {
                "market_constraint_engine": {
                    "status": "ACTIVE",
                    "thresholds": {
                        "steam_pct": self.market_engine.thresholds.steam_pct,
                        "drift_pct": self.market_engine.thresholds.drift_pct,
                        "divergence_pct": self.market_engine.thresholds.divergence_pct,
                    }
                },
                "rpd_v2_engine": {
                    "status": "ACTIVE",
                    "tags": list(RPDTag.__members__.keys()),
                    "evidence_weights_calibrated": len(
                        self.rpd_engine._evidence_weights
                    ) > 0
                },
                "scenario_evidence_gate": {
                    "status": "ACTIVE",
                    "scenarios": list(
                        self.scenario_gate.scenario_defs.keys()
                    ),
                },
                "track_profile_db": {
                    "status": "ACTIVE",
                    "total_tracks": track_count,
                    "aw_tracks": aw_tracks,
                    "turf_tracks": track_count - aw_tracks,
                }
            },
            "database": self.db_path,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
