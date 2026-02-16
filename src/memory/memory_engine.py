"""
VÉLØ PRIME — Persistent Memory Engine
=======================================
The brain's long-term storage. Every race, every prediction, every result,
every lesson — stored, indexed, and queryable across sessions.

This is how VÉLØ learns. Not from vibes. From data.

Usage:
    from src.memory.memory_engine import VeloMemoryEngine
    mem = VeloMemoryEngine("data/velo_memory.db")
    mem.store_race({...})
"""

import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schema import init_database, get_schema_version


def _uid() -> str:
    """Generate a short unique ID."""
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.utcnow().isoformat()


def _json(obj: Any) -> Optional[str]:
    """Safely serialize to JSON string."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    return json.dumps(obj)


def _from_json(text: Optional[str]) -> Any:
    """Safely deserialize from JSON string."""
    if text is None:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert sqlite3.Row to plain dict."""
    if row is None:
        return {}
    return dict(row)


class VeloMemoryEngine:
    """
    VÉLØ Persistent Memory Engine.

    Stores and retrieves race data, predictions, results, sigma evaluations,
    trainer/jockey patterns, course bias, RPD validation, and market behaviour.
    """

    def __init__(self, db_path: str = "data/velo_memory.db"):
        self.db_path = db_path
        self.conn = init_database(db_path)
        self._version = get_schema_version(self.conn)

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    # ─────────────────────────────────────────
    # RACE STORAGE
    # ─────────────────────────────────────────

    def store_race(self, race_data: dict) -> str:
        """
        Store a race record.
        race_data must include at minimum: race_id, date, course.
        Returns the race_id.
        """
        race_id = race_data.get("race_id", _uid())
        self.conn.execute(
            """INSERT OR REPLACE INTO races
               (race_id, date, course, time, race_type, class, distance,
                going, field_size, prize, rail_position, weather, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                race_id,
                race_data.get("date", _now()[:10]),
                race_data.get("course", ""),
                race_data.get("time"),
                race_data.get("race_type"),
                race_data.get("class"),
                race_data.get("distance"),
                race_data.get("going"),
                race_data.get("field_size"),
                race_data.get("prize"),
                race_data.get("rail_position"),
                race_data.get("weather"),
                _now(),
            ),
        )
        self.conn.commit()
        return race_id

    def store_runners(self, race_id: str, runners_list: List[dict]) -> List[str]:
        """
        Store runner records for a race.
        Each runner dict should have horse_name at minimum.
        Returns list of runner_ids.
        """
        ids = []
        for r in runners_list:
            runner_id = r.get("runner_id", f"{race_id}_{_uid()}")
            self.conn.execute(
                """INSERT OR REPLACE INTO runners
                   (runner_id, race_id, horse_name, trainer, jockey, age, weight,
                    "OR", RPR, TS, form_figures, draw, headgear,
                    days_since_run, spotlight_notes, rpd_tag)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    runner_id,
                    race_id,
                    r.get("horse_name", ""),
                    r.get("trainer"),
                    r.get("jockey"),
                    r.get("age"),
                    r.get("weight"),
                    r.get("OR") or r.get("or_rating"),
                    r.get("RPR") or r.get("rpr"),
                    r.get("TS") or r.get("ts"),
                    r.get("form_figures") or r.get("form"),
                    r.get("draw"),
                    r.get("headgear"),
                    r.get("days_since_run"),
                    r.get("spotlight_notes"),
                    r.get("rpd_tag"),
                ),
            )
            ids.append(runner_id)
        self.conn.commit()
        return ids

    def store_prediction(self, race_id: str, prediction_dict: dict) -> str:
        """
        Store a prediction for a race.
        Returns the prediction_id.
        """
        pred_id = prediction_dict.get("prediction_id", f"pred_{_uid()}")
        self.conn.execute(
            """INSERT OR REPLACE INTO predictions
               (prediction_id, race_id, date, top_strike, value_pick,
                danger_horse, confidence_band, scenario_primary,
                scenario_secondary, threat_flags, full_analysis_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pred_id,
                race_id,
                prediction_dict.get("date", _now()[:10]),
                prediction_dict.get("top_strike"),
                prediction_dict.get("value_pick"),
                prediction_dict.get("danger_horse"),
                prediction_dict.get("confidence_band"),
                prediction_dict.get("scenario_primary"),
                prediction_dict.get("scenario_secondary"),
                _json(prediction_dict.get("threat_flags")),
                prediction_dict.get("full_analysis_text"),
            ),
        )
        self.conn.commit()
        return pred_id

    def store_results(self, race_id: str, results_dict: dict) -> str:
        """
        Store results for a race.
        results_dict should include positions (list of dicts), winning_time, non_runners.
        Returns the result_id.
        """
        result_id = results_dict.get("result_id", f"res_{_uid()}")
        self.conn.execute(
            """INSERT OR REPLACE INTO results
               (result_id, race_id, date, positions, winning_time, non_runners)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                result_id,
                race_id,
                results_dict.get("date", _now()[:10]),
                _json(results_dict.get("positions")),
                results_dict.get("winning_time"),
                _json(results_dict.get("non_runners")),
            ),
        )
        self.conn.commit()
        return result_id

    # ─────────────────────────────────────────
    # SIGMA EVALUATION
    # ─────────────────────────────────────────

    def run_sigma_evaluation(self, race_id: str) -> Optional[str]:
        """
        Auto-compare prediction vs result for a race.
        Calculates hit/place/miss for top_strike, value_pick, danger_horse.
        Stores and returns the eval_id.
        """
        pred = self.conn.execute(
            "SELECT * FROM predictions WHERE race_id = ?", (race_id,)
        ).fetchone()
        res = self.conn.execute(
            "SELECT * FROM results WHERE race_id = ?", (race_id,)
        ).fetchone()

        if not pred or not res:
            return None

        pred = _row_to_dict(pred)
        res = _row_to_dict(res)
        positions = _from_json(res.get("positions")) or []

        # Build lookup: horse_name -> position
        pos_map: Dict[str, int] = {}
        for p in positions:
            name = (p.get("horse_name") or "").strip().lower()
            pos = p.get("position")
            if name and pos is not None:
                try:
                    pos_map[name] = int(pos)
                except (ValueError, TypeError):
                    pass

        def _evaluate(horse_name: Optional[str]) -> str:
            if not horse_name:
                return "miss"
            key = horse_name.strip().lower()
            pos = pos_map.get(key)
            if pos is None:
                return "miss"
            if pos == 1:
                return "hit"
            if pos <= 3:
                return "place"
            return "miss"

        top_result = _evaluate(pred.get("top_strike"))
        value_result = _evaluate(pred.get("value_pick"))
        danger_result = _evaluate(pred.get("danger_horse"))

        # Signal quality: simple scoring
        score = 0.0
        for r in [top_result, value_result, danger_result]:
            if r == "hit":
                score += 1.0
            elif r == "place":
                score += 0.5
        signal_quality = round(score / 3.0, 3)

        eval_id = f"sigma_{_uid()}"
        self.conn.execute(
            """INSERT OR REPLACE INTO sigma_evaluations
               (eval_id, race_id, date, top_strike_result, value_result,
                danger_result, signal_quality, narrative_traps,
                bias_adjustments, weight_changes, lessons_learned)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                eval_id,
                race_id,
                pred.get("date", _now()[:10]),
                top_result,
                value_result,
                danger_result,
                signal_quality,
                None,
                None,
                None,
                None,
            ),
        )
        self.conn.commit()
        return eval_id

    # ─────────────────────────────────────────
    # PATTERN QUERIES
    # ─────────────────────────────────────────

    def query_trainer_history(
        self, trainer: str, course: Optional[str] = None, going: Optional[str] = None
    ) -> List[dict]:
        """Return historical trainer patterns, optionally filtered."""
        sql = "SELECT * FROM trainer_patterns WHERE trainer = ?"
        params: list = [trainer]
        if course:
            sql += " AND (course = ? OR course = '_ALL_')"
            params.append(course)
        if going:
            sql += " AND (going = ? OR going = '_ALL_')"
            params.append(going)
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def query_jockey_history(
        self, jockey: str, course: Optional[str] = None, going: Optional[str] = None
    ) -> List[dict]:
        """Return historical jockey patterns, optionally filtered."""
        sql = "SELECT * FROM jockey_patterns WHERE jockey = ?"
        params: list = [jockey]
        if course:
            sql += " AND (course = ? OR course = '_ALL_')"
            params.append(course)
        if going:
            sql += " AND (going = ? OR going = '_ALL_')"
            params.append(going)
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def query_course_bias(
        self,
        course: str,
        going: Optional[str] = None,
        distance: Optional[str] = None,
    ) -> List[dict]:
        """Return course bias data, optionally filtered."""
        sql = "SELECT * FROM course_bias WHERE course = ?"
        params: list = [course]
        if going:
            sql += " AND (going = ? OR going = '_ALL_')"
            params.append(going)
        if distance:
            sql += " AND (distance = ? OR distance = '_ALL_')"
            params.append(distance)
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ─────────────────────────────────────────
    # PATTERN UPDATES (recalculate from results)
    # ─────────────────────────────────────────

    def update_trainer_patterns(self, race_id: str) -> int:
        """
        Recalculate trainer patterns from all stored results involving
        trainers who ran in the given race. Returns count of patterns updated.
        """
        # Get trainers from this race
        runners = self.conn.execute(
            "SELECT DISTINCT trainer FROM runners WHERE race_id = ? AND trainer IS NOT NULL",
            (race_id,),
        ).fetchall()

        updated = 0
        for row in runners:
            trainer = row["trainer"]
            updated += self._recalc_trainer(trainer)
        return updated

    def _recalc_trainer(self, trainer: str) -> int:
        """Recalculate all pattern rows for a given trainer."""
        # Get all races this trainer has runners in that also have results
        sql = """
            SELECT r.race_id, r.course, r.going, r.race_type,
                   ru.horse_name, ru."OR" as or_rating,
                   res.positions
            FROM runners ru
            JOIN races r ON ru.race_id = r.race_id
            JOIN results res ON r.race_id = res.race_id
            WHERE ru.trainer = ?
        """
        rows = self.conn.execute(sql, (trainer,)).fetchall()
        if not rows:
            return 0

        # Aggregate by (course, going, race_type) and also (_ALL_, _ALL_, _ALL_)
        from collections import defaultdict

        buckets: Dict[Tuple[str, str, str], list] = defaultdict(list)
        for row in rows:
            row = _row_to_dict(row)
            course = row.get("course") or "_ALL_"
            going = row.get("going") or "_ALL_"
            race_type = row.get("race_type") or "_ALL_"
            positions = _from_json(row.get("positions")) or []
            horse = (row.get("horse_name") or "").strip().lower()

            pos = None
            for p in positions:
                if (p.get("horse_name") or "").strip().lower() == horse:
                    try:
                        pos = int(p.get("position", 99))
                    except (ValueError, TypeError):
                        pos = 99
                    break

            entry = {
                "or_rating": row.get("or_rating"),
                "position": pos,
            }
            buckets[(course, going, race_type)].append(entry)
            buckets[("_ALL_", "_ALL_", "_ALL_")].append(entry)

        count = 0
        for (course, going, race_type), entries in buckets.items():
            runs = len(entries)
            wins = sum(1 for e in entries if e["position"] == 1)
            places = sum(1 for e in entries if e["position"] is not None and e["position"] <= 3)
            or_vals = [e["or_rating"] for e in entries if e["or_rating"] is not None]
            avg_or = round(sum(or_vals) / len(or_vals), 1) if or_vals else 0.0
            strike = round(wins / runs, 4) if runs else 0.0

            self.conn.execute(
                """INSERT OR REPLACE INTO trainer_patterns
                   (trainer, course, going, race_type, runs, wins, places,
                    strike_rate, avg_or, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trainer, course, going, race_type, runs, wins, places,
                 strike, avg_or, _now()),
            )
            count += 1
        self.conn.commit()
        return count

    def update_jockey_patterns(self, race_id: str) -> int:
        """Recalculate jockey patterns from stored results. Returns count updated."""
        runners = self.conn.execute(
            "SELECT DISTINCT jockey FROM runners WHERE race_id = ? AND jockey IS NOT NULL",
            (race_id,),
        ).fetchall()

        updated = 0
        for row in runners:
            jockey = row["jockey"]
            updated += self._recalc_jockey(jockey)
        return updated

    def _recalc_jockey(self, jockey: str) -> int:
        """Recalculate all pattern rows for a given jockey."""
        sql = """
            SELECT r.race_id, r.course, r.going, r.race_type,
                   ru.horse_name, res.positions
            FROM runners ru
            JOIN races r ON ru.race_id = r.race_id
            JOIN results res ON r.race_id = res.race_id
            WHERE ru.jockey = ?
        """
        rows = self.conn.execute(sql, (jockey,)).fetchall()
        if not rows:
            return 0

        from collections import defaultdict

        buckets: Dict[Tuple[str, str, str], list] = defaultdict(list)
        for row in rows:
            row = _row_to_dict(row)
            course = row.get("course") or "_ALL_"
            going = row.get("going") or "_ALL_"
            race_type = row.get("race_type") or "_ALL_"
            positions = _from_json(row.get("positions")) or []
            horse = (row.get("horse_name") or "").strip().lower()

            pos = None
            for p in positions:
                if (p.get("horse_name") or "").strip().lower() == horse:
                    try:
                        pos = int(p.get("position", 99))
                    except (ValueError, TypeError):
                        pos = 99
                    break

            buckets[(course, going, race_type)].append({"position": pos})
            buckets[("_ALL_", "_ALL_", "_ALL_")].append({"position": pos})

        count = 0
        for (course, going, race_type), entries in buckets.items():
            runs = len(entries)
            wins = sum(1 for e in entries if e["position"] == 1)
            places = sum(1 for e in entries if e["position"] is not None and e["position"] <= 3)
            strike = round(wins / runs, 4) if runs else 0.0

            self.conn.execute(
                """INSERT OR REPLACE INTO jockey_patterns
                   (jockey, course, going, race_type, runs, wins, places,
                    strike_rate, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (jockey, course, going, race_type, runs, wins, places,
                 strike, _now()),
            )
            count += 1
        self.conn.commit()
        return count

    def update_course_bias(self, race_id: str) -> int:
        """
        Recalculate course bias from all stored results at the same course.
        Returns count of bias records updated.
        """
        race = self.conn.execute(
            "SELECT course FROM races WHERE race_id = ?", (race_id,)
        ).fetchone()
        if not race:
            return 0

        course = race["course"]
        sql = """
            SELECT r.going, r.distance, r.rail_position,
                   res.positions
            FROM races r
            JOIN results res ON r.race_id = res.race_id
            WHERE r.course = ?
        """
        rows = self.conn.execute(sql, (course,)).fetchall()
        if not rows:
            return 0

        from collections import defaultdict

        buckets: Dict[Tuple[str, str], list] = defaultdict(list)
        for row in rows:
            row = _row_to_dict(row)
            going = row.get("going") or "_ALL_"
            distance = row.get("distance") or "_ALL_"
            positions = _from_json(row.get("positions")) or []

            winner_draw = None
            for p in positions:
                if p.get("position") == 1 or p.get("position") == "1":
                    winner_draw = p.get("draw")
                    break

            buckets[(going, distance)].append({
                "rail_position": row.get("rail_position"),
                "winner_draw": winner_draw,
            })

        count = 0
        for (going, distance), entries in buckets.items():
            sample = len(entries)
            draws = [e["winner_draw"] for e in entries if e["winner_draw"] is not None]
            draw_bias = None
            if draws:
                try:
                    avg_draw = sum(int(d) for d in draws) / len(draws)
                    if avg_draw <= 3:
                        draw_bias = "low_draw_advantage"
                    elif avg_draw >= 8:
                        draw_bias = "high_draw_advantage"
                    else:
                        draw_bias = "neutral"
                except (ValueError, TypeError):
                    draw_bias = "insufficient_data"

            self.conn.execute(
                """INSERT OR REPLACE INTO course_bias
                   (course, going, distance, rail_position, pace_bias,
                    draw_bias, sample_size, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (course, going, distance, None, None, draw_bias, sample, _now()),
            )
            count += 1
        self.conn.commit()
        return count

    # ─────────────────────────────────────────
    # RPD VALIDATION
    # ─────────────────────────────────────────

    def validate_rpd_tag(
        self, runner_id: str, actual_position: int, actual_bsp: float
    ) -> Optional[str]:
        """
        Validate an RPD tag against actual results.
        Returns rpd_id or None if runner not found.
        """
        runner = self.conn.execute(
            "SELECT * FROM runners WHERE runner_id = ?", (runner_id,)
        ).fetchone()
        if not runner:
            return None

        runner = _row_to_dict(runner)
        rpd_tag = runner.get("rpd_tag")
        race_id = runner.get("race_id")

        # Determine if tag was validated (simplistic: P tag + top 3 = validated)
        tag_validated = False
        predicted_intent = None
        if rpd_tag:
            tag_upper = rpd_tag.upper()
            if "P" in tag_upper:
                predicted_intent = "proven"
                tag_validated = actual_position <= 3
            elif "T" in tag_upper:
                predicted_intent = "tentative"
                tag_validated = actual_position <= 5
            elif "E" in tag_upper:
                predicted_intent = "exposed"
                tag_validated = actual_position > 3
            elif "H" in tag_upper:
                predicted_intent = "handicap_blot"
                tag_validated = actual_position <= 3
            elif "S" in tag_upper:
                predicted_intent = "speculative"
                tag_validated = actual_position <= 2

        rpd_id = f"rpd_{_uid()}"
        self.conn.execute(
            """INSERT OR REPLACE INTO rpd_validation
               (rpd_id, runner_id, race_id, rpd_tag, predicted_intent,
                actual_position, actual_bsp, tag_validated, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rpd_id,
                runner_id,
                race_id,
                rpd_tag,
                predicted_intent,
                actual_position,
                actual_bsp,
                tag_validated,
                None,
            ),
        )
        self.conn.commit()
        return rpd_id

    # ─────────────────────────────────────────
    # MARKET BEHAVIOUR
    # ─────────────────────────────────────────

    def log_market_behaviour(
        self,
        runner_id: str,
        morning_price: float,
        sp: float,
        bsp: float,
    ) -> str:
        """
        Log market behaviour for a runner.
        Calculates drift percentage and type.
        Returns market_id.
        """
        runner = self.conn.execute(
            "SELECT race_id FROM runners WHERE runner_id = ?", (runner_id,)
        ).fetchone()
        race_id = runner["race_id"] if runner else "unknown"

        drift_pct = 0.0
        if morning_price and morning_price > 0:
            drift_pct = round(((bsp - morning_price) / morning_price) * 100, 2)

        # Classify drift
        if abs(drift_pct) < 10:
            drift_type = "noise"
        else:
            drift_type = "informative"

        steam_flag = drift_pct < -15  # Significant shortening

        market_id = f"mkt_{_uid()}"
        self.conn.execute(
            """INSERT OR REPLACE INTO market_behaviour
               (market_id, runner_id, race_id, morning_price, sp, bsp,
                drift_pct, drift_type, steam_flag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (market_id, runner_id, race_id, morning_price, sp, bsp,
             drift_pct, drift_type, steam_flag),
        )
        self.conn.commit()
        return market_id

    # ─────────────────────────────────────────
    # PRE-RACE CONTEXT
    # ─────────────────────────────────────────

    def get_pre_race_context(
        self,
        course: str,
        trainers_list: List[str],
        jockeys_list: List[str],
    ) -> dict:
        """
        Pull all relevant historical intelligence before analysis.
        Returns a context dict with trainer patterns, jockey patterns,
        course bias, and recent sigma trends for this course.
        """
        context: Dict[str, Any] = {
            "course": course,
            "generated_at": _now(),
            "trainer_patterns": {},
            "jockey_patterns": {},
            "course_bias": [],
            "recent_sigma_at_course": [],
        }

        for trainer in trainers_list:
            patterns = self.query_trainer_history(trainer, course=course)
            if patterns:
                context["trainer_patterns"][trainer] = patterns

        for jockey in jockeys_list:
            patterns = self.query_jockey_history(jockey, course=course)
            if patterns:
                context["jockey_patterns"][jockey] = patterns

        context["course_bias"] = self.query_course_bias(course)

        # Recent sigma evaluations at this course
        sql = """
            SELECT se.* FROM sigma_evaluations se
            JOIN races r ON se.race_id = r.race_id
            WHERE r.course = ?
            ORDER BY se.date DESC
            LIMIT 20
        """
        rows = self.conn.execute(sql, (course,)).fetchall()
        context["recent_sigma_at_course"] = [_row_to_dict(r) for r in rows]

        return context

    # ─────────────────────────────────────────
    # SYSTEM STATS
    # ─────────────────────────────────────────

    def get_system_stats(self) -> dict:
        """
        Overall performance statistics.
        Returns hit rates, value strike rates, sigma trends.
        """
        stats: Dict[str, Any] = {}

        # Counts
        stats["total_races"] = self.conn.execute("SELECT COUNT(*) FROM races").fetchone()[0]
        stats["total_runners"] = self.conn.execute("SELECT COUNT(*) FROM runners").fetchone()[0]
        stats["total_predictions"] = self.conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        stats["total_results"] = self.conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        stats["total_evaluations"] = self.conn.execute("SELECT COUNT(*) FROM sigma_evaluations").fetchone()[0]

        # Hit rates
        evals = self.conn.execute("SELECT * FROM sigma_evaluations").fetchall()
        if evals:
            total = len(evals)
            ts_hits = sum(1 for e in evals if e["top_strike_result"] == "hit")
            ts_places = sum(1 for e in evals if e["top_strike_result"] == "place")
            vp_hits = sum(1 for e in evals if e["value_result"] == "hit")
            vp_places = sum(1 for e in evals if e["value_result"] == "place")

            stats["top_strike_hit_rate"] = round(ts_hits / total, 4)
            stats["top_strike_place_rate"] = round((ts_hits + ts_places) / total, 4)
            stats["value_hit_rate"] = round(vp_hits / total, 4)
            stats["value_place_rate"] = round((vp_hits + vp_places) / total, 4)

            qualities = [e["signal_quality"] for e in evals if e["signal_quality"] is not None]
            stats["avg_signal_quality"] = round(sum(qualities) / len(qualities), 4) if qualities else 0.0
        else:
            stats["top_strike_hit_rate"] = 0.0
            stats["top_strike_place_rate"] = 0.0
            stats["value_hit_rate"] = 0.0
            stats["value_place_rate"] = 0.0
            stats["avg_signal_quality"] = 0.0

        stats["schema_version"] = self._version
        return stats

    # ─────────────────────────────────────────
    # SIGMA REPORT EXPORT
    # ─────────────────────────────────────────

    def export_sigma_report(self, date_from: str, date_to: str) -> str:
        """
        Generate a Markdown performance report for a date range.
        Returns the report as a string.
        """
        evals = self.conn.execute(
            """SELECT se.*, r.course, r.race_type
               FROM sigma_evaluations se
               JOIN races r ON se.race_id = r.race_id
               WHERE se.date BETWEEN ? AND ?
               ORDER BY se.date""",
            (date_from, date_to),
        ).fetchall()

        if not evals:
            return f"# VÉLØ Sigma Report\n\nNo evaluations found for {date_from} to {date_to}.\n"

        total = len(evals)
        ts_hits = sum(1 for e in evals if e["top_strike_result"] == "hit")
        ts_places = sum(1 for e in evals if e["top_strike_result"] == "place")
        vp_hits = sum(1 for e in evals if e["value_result"] == "hit")
        dg_hits = sum(1 for e in evals if e["danger_result"] == "hit")
        dg_places = sum(1 for e in evals if e["danger_result"] == "place")
        qualities = [e["signal_quality"] for e in evals if e["signal_quality"] is not None]
        avg_q = round(sum(qualities) / len(qualities), 3) if qualities else 0.0

        lines = [
            f"# VÉLØ SIGMA Performance Report",
            f"**Period:** {date_from} → {date_to}",
            f"**Races Evaluated:** {total}",
            "",
            "## Strike Rates",
            "",
            "| Metric | Count | Rate |",
            "|--------|-------|------|",
            f"| Top Strike — Win | {ts_hits} | {round(ts_hits/total*100,1)}% |",
            f"| Top Strike — Place | {ts_hits+ts_places} | {round((ts_hits+ts_places)/total*100,1)}% |",
            f"| Value Pick — Win | {vp_hits} | {round(vp_hits/total*100,1)}% |",
            f"| Danger Horse — Win | {dg_hits} | {round(dg_hits/total*100,1)}% |",
            f"| Danger Horse — Place | {dg_hits+dg_places} | {round((dg_hits+dg_places)/total*100,1)}% |",
            "",
            f"**Average Signal Quality:** {avg_q}",
            "",
            "## Race-by-Race",
            "",
            "| Date | Course | Top Strike | Value | Danger | Quality |",
            "|------|--------|------------|-------|--------|---------|",
        ]

        for e in evals:
            e = _row_to_dict(e)
            lines.append(
                f"| {e.get('date','')} | {e.get('course','')} | "
                f"{e.get('top_strike_result','')} | {e.get('value_result','')} | "
                f"{e.get('danger_result','')} | {e.get('signal_quality','')} |"
            )

        lines.append("")
        lines.append("---")
        lines.append(f"*Generated by VÉLØ Memory Engine v{self._version}*")
        return "\n".join(lines)

    # ─────────────────────────────────────────
    # UTILITY
    # ─────────────────────────────────────────

    def get_race(self, race_id: str) -> Optional[dict]:
        """Retrieve a single race record."""
        row = self.conn.execute("SELECT * FROM races WHERE race_id = ?", (race_id,)).fetchone()
        return _row_to_dict(row) if row else None

    def get_runners(self, race_id: str) -> List[dict]:
        """Retrieve all runners for a race."""
        rows = self.conn.execute("SELECT * FROM runners WHERE race_id = ?", (race_id,)).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_prediction(self, race_id: str) -> Optional[dict]:
        """Retrieve prediction for a race."""
        row = self.conn.execute(
            "SELECT * FROM predictions WHERE race_id = ? ORDER BY created_at DESC LIMIT 1",
            (race_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None

    def get_result(self, race_id: str) -> Optional[dict]:
        """Retrieve result for a race."""
        row = self.conn.execute(
            "SELECT * FROM results WHERE race_id = ? ORDER BY created_at DESC LIMIT 1",
            (race_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None

    def get_sigma(self, race_id: str) -> Optional[dict]:
        """Retrieve sigma evaluation for a race."""
        row = self.conn.execute(
            "SELECT * FROM sigma_evaluations WHERE race_id = ? ORDER BY created_at DESC LIMIT 1",
            (race_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None

    def list_races(self, date: Optional[str] = None, course: Optional[str] = None, limit: int = 50) -> List[dict]:
        """List races with optional filters."""
        sql = "SELECT * FROM races WHERE 1=1"
        params: list = []
        if date:
            sql += " AND date = ?"
            params.append(date)
        if course:
            sql += " AND course = ?"
            params.append(course)
        sql += " ORDER BY date DESC, time DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
