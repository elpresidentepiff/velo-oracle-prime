"""
VÉLØ PRIME — RPD-C Validation Engine
======================================
Validates Racing Post Digest tags against actual race outcomes.
Tracks accuracy per tag type (P/T/E/H/S) and generates
recalibration reports for weight adjustment.

RPD Tag Types:
  P — Proven (consistent performer, should hit top 3)
  T — Tentative (improving, should hit top 5)
  E — Exposed (form declining, likely out of frame)
  H — Handicap Blot (well-handicapped, should outperform)
  S — Speculative (longshot with upside, needs top 2 to validate)

Usage:
    from src.memory.rpd_validator import RPDValidator
    from src.memory.memory_engine import VeloMemoryEngine

    mem = VeloMemoryEngine("data/velo_memory.db")
    rpd = RPDValidator(mem)
    rpd.validate_batch("race_001")
    report = rpd.recalibration_report()
"""

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .memory_engine import VeloMemoryEngine, _from_json, _row_to_dict


# Tag definitions with expected position thresholds
TAG_DEFINITIONS = {
    "P": {"name": "Proven", "win_threshold": 1, "place_threshold": 3, "description": "Consistent performer"},
    "T": {"name": "Tentative", "win_threshold": 1, "place_threshold": 5, "description": "Improving form"},
    "E": {"name": "Exposed", "win_threshold": None, "place_threshold": None, "description": "Form declining — expected out of frame"},
    "H": {"name": "Handicap Blot", "win_threshold": 1, "place_threshold": 3, "description": "Well-handicapped, should outperform"},
    "S": {"name": "Speculative", "win_threshold": 1, "place_threshold": 2, "description": "Longshot with upside"},
}


class RPDValidator:
    """
    Validates RPD tags against actual race results.
    Provides accuracy statistics and recalibration recommendations.
    """

    def __init__(self, memory: VeloMemoryEngine):
        self.memory = memory
        self.conn = memory.conn

    def validate_batch(self, race_id: str) -> List[dict]:
        """
        Validate all RPD tags for runners in a given race against results.

        Args:
            race_id: The race identifier.

        Returns:
            List of validation result dicts.
        """
        runners = self.conn.execute(
            "SELECT * FROM runners WHERE race_id = ?", (race_id,)
        ).fetchall()

        result_row = self.conn.execute(
            "SELECT * FROM results WHERE race_id = ?", (race_id,)
        ).fetchone()

        if not result_row:
            return []

        positions_data = _from_json(result_row["positions"]) or []

        # Build position lookup
        pos_map: Dict[str, dict] = {}
        for p in positions_data:
            name = (p.get("horse_name") or "").strip().lower()
            if name:
                pos_map[name] = p

        validations = []
        for runner in runners:
            runner = _row_to_dict(runner)
            rpd_tag = runner.get("rpd_tag")
            if not rpd_tag:
                continue

            horse_name = (runner.get("horse_name") or "").strip().lower()
            pos_entry = pos_map.get(horse_name, {})

            actual_position = None
            actual_bsp = None
            try:
                actual_position = int(pos_entry.get("position", 99))
            except (ValueError, TypeError):
                actual_position = 99
            try:
                actual_bsp = float(pos_entry.get("bsp", 0))
            except (ValueError, TypeError):
                actual_bsp = 0.0

            # Validate using memory engine
            rpd_id = self.memory.validate_rpd_tag(
                runner["runner_id"], actual_position, actual_bsp
            )

            validations.append({
                "rpd_id": rpd_id,
                "runner_id": runner["runner_id"],
                "horse_name": runner.get("horse_name"),
                "rpd_tag": rpd_tag,
                "actual_position": actual_position,
                "actual_bsp": actual_bsp,
                "validated": self._is_tag_valid(rpd_tag, actual_position),
            })

        return validations

    def _is_tag_valid(self, rpd_tag: str, actual_position: int) -> bool:
        """Check if a tag prediction was correct given the actual position."""
        tag = rpd_tag.upper().strip()
        first_char = tag[0] if tag else ""
        defn = TAG_DEFINITIONS.get(first_char)
        if not defn:
            return False

        if first_char == "E":
            # Exposed: validated if horse finished outside top 3
            return actual_position > 3
        else:
            threshold = defn.get("place_threshold", 3)
            return actual_position <= threshold

    def get_tag_accuracy(self) -> Dict[str, dict]:
        """
        Return accuracy statistics per RPD tag type.

        Returns:
            Dict keyed by tag letter with counts and accuracy rates.
        """
        rows = self.conn.execute("SELECT * FROM rpd_validation").fetchall()
        if not rows:
            return {}

        stats: Dict[str, dict] = {}
        for tag_letter in TAG_DEFINITIONS:
            tag_rows = [
                r for r in rows
                if r["rpd_tag"] and r["rpd_tag"].upper().startswith(tag_letter)
            ]
            total = len(tag_rows)
            if total == 0:
                stats[tag_letter] = {
                    "tag_name": TAG_DEFINITIONS[tag_letter]["name"],
                    "total": 0,
                    "validated": 0,
                    "accuracy": 0.0,
                }
                continue

            validated = sum(1 for r in tag_rows if r["tag_validated"])
            stats[tag_letter] = {
                "tag_name": TAG_DEFINITIONS[tag_letter]["name"],
                "total": total,
                "validated": validated,
                "accuracy": round(validated / total, 4) if total else 0.0,
            }

        return stats

    def get_tag_accuracy_by_course(self, course: str) -> Dict[str, dict]:
        """
        Return RPD tag accuracy filtered by course.

        Args:
            course: Course name to filter by.

        Returns:
            Dict keyed by tag letter with course-specific accuracy.
        """
        rows = self.conn.execute(
            """SELECT rv.* FROM rpd_validation rv
               JOIN races r ON rv.race_id = r.race_id
               WHERE r.course = ?""",
            (course,),
        ).fetchall()

        if not rows:
            return {}

        stats: Dict[str, dict] = {}
        for tag_letter in TAG_DEFINITIONS:
            tag_rows = [
                r for r in rows
                if r["rpd_tag"] and r["rpd_tag"].upper().startswith(tag_letter)
            ]
            total = len(tag_rows)
            if total == 0:
                stats[tag_letter] = {
                    "tag_name": TAG_DEFINITIONS[tag_letter]["name"],
                    "course": course,
                    "total": 0,
                    "validated": 0,
                    "accuracy": 0.0,
                }
                continue

            validated = sum(1 for r in tag_rows if r["tag_validated"])
            stats[tag_letter] = {
                "tag_name": TAG_DEFINITIONS[tag_letter]["name"],
                "course": course,
                "total": total,
                "validated": validated,
                "accuracy": round(validated / total, 4) if total else 0.0,
            }

        return stats

    def recalibration_report(self) -> str:
        """
        Generate a recalibration report identifying which RPD tags
        need weight adjustment based on historical accuracy.

        Returns:
            Markdown-formatted report string.
        """
        accuracy = self.get_tag_accuracy()
        if not accuracy:
            return "# RPD-C Recalibration Report\n\nNo validation data available yet.\n"

        lines = [
            "# VÉLØ RPD-C Recalibration Report",
            "",
            "## Tag Accuracy Summary",
            "",
            "| Tag | Name | Total | Validated | Accuracy | Status |",
            "|-----|------|-------|-----------|----------|--------|",
        ]

        recommendations = []
        for tag_letter, data in sorted(accuracy.items()):
            acc = data["accuracy"]
            total = data["total"]

            if total < 5:
                status = "INSUFFICIENT DATA"
            elif acc >= 0.7:
                status = "STRONG"
            elif acc >= 0.5:
                status = "ACCEPTABLE"
            elif acc >= 0.3:
                status = "WEAK — NEEDS ADJUSTMENT"
                recommendations.append(
                    f"- **{tag_letter} ({data['tag_name']})**: Accuracy at {acc*100:.1f}%. "
                    f"Consider reducing weight in confidence calculations."
                )
            else:
                status = "FAILING — RECALIBRATE"
                recommendations.append(
                    f"- **{tag_letter} ({data['tag_name']})**: Accuracy at {acc*100:.1f}%. "
                    f"Tag is unreliable. Recommend significant weight reduction or redefinition."
                )

            lines.append(
                f"| {tag_letter} | {data['tag_name']} | {total} | "
                f"{data['validated']} | {acc*100:.1f}% | {status} |"
            )

        lines.append("")

        if recommendations:
            lines.append("## Recommendations")
            lines.append("")
            lines.extend(recommendations)
        else:
            lines.append("## Recommendations")
            lines.append("")
            lines.append("All tags performing within acceptable parameters. No recalibration needed.")

        lines.append("")
        lines.append("---")
        lines.append("*Generated by VÉLØ RPD-C Validation Engine*")
        return "\n".join(lines)

    def get_validation_details(self, race_id: Optional[str] = None) -> List[dict]:
        """
        Get detailed validation records, optionally filtered by race.

        Args:
            race_id: Optional race filter.

        Returns:
            List of validation record dicts.
        """
        if race_id:
            rows = self.conn.execute(
                "SELECT * FROM rpd_validation WHERE race_id = ?", (race_id,)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM rpd_validation ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
