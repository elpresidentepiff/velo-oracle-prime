"""
VÉLØ PRIME — Persistent Memory Test Suite
===========================================
Comprehensive tests for:
  - Database schema initialization
  - VeloMemoryEngine (store, query, evaluate)
  - RPDValidator (batch validation, accuracy, recalibration)
  - GitHubSync (path generation, status)
  - Integration CLI parsers
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.schema import init_database, get_schema_version, SCHEMA_VERSION
from src.memory.memory_engine import VeloMemoryEngine, _json, _from_json, _row_to_dict
from src.memory.rpd_validator import RPDValidator, TAG_DEFINITIONS
from src.memory.github_sync import GitHubSync
from src.memory.integrate import (
    parse_race_card_file,
    parse_analysis_file,
    parse_results_file,
)


class TestSchema(unittest.TestCase):
    """Test database schema initialization."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.db_path)

    def test_init_creates_all_tables(self):
        conn = init_database(self.db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]

        expected = [
            "course_bias",
            "jockey_patterns",
            "market_behaviour",
            "predictions",
            "races",
            "results",
            "rpd_validation",
            "runners",
            "schema_meta",
            "sigma_evaluations",
            "trainer_patterns",
        ]
        for name in expected:
            self.assertIn(name, table_names, f"Missing table: {name}")
        conn.close()

    def test_schema_version(self):
        conn = init_database(self.db_path)
        version = get_schema_version(conn)
        self.assertEqual(version, SCHEMA_VERSION)
        conn.close()

    def test_wal_mode_enabled(self):
        conn = init_database(self.db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "wal")
        conn.close()

    def test_foreign_keys_enabled(self):
        conn = init_database(self.db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(fk, 1)
        conn.close()

    def test_idempotent_init(self):
        """Calling init_database twice should not fail."""
        conn1 = init_database(self.db_path)
        conn1.close()
        conn2 = init_database(self.db_path)
        version = get_schema_version(conn2)
        self.assertEqual(version, SCHEMA_VERSION)
        conn2.close()


class TestVeloMemoryEngine(unittest.TestCase):
    """Test the core memory engine."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.mem = VeloMemoryEngine(self.tmp.name)

    def tearDown(self):
        self.mem.close()
        os.unlink(self.tmp.name)

    # ── Store & Retrieve ──

    def test_store_and_get_race(self):
        race_data = {
            "race_id": "R001",
            "date": "2026-02-16",
            "course": "Kempton",
            "time": "14:30",
            "race_type": "Handicap",
            "class": "4",
            "distance": "1m2f",
            "going": "Good to Soft",
            "field_size": 8,
        }
        rid = self.mem.store_race(race_data)
        self.assertEqual(rid, "R001")

        race = self.mem.get_race("R001")
        self.assertEqual(race["course"], "Kempton")
        self.assertEqual(race["going"], "Good to Soft")
        self.assertEqual(race["field_size"], 8)

    def test_store_and_get_runners(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        runners = [
            {"runner_id": "run_1", "horse_name": "Thunder Strike", "trainer": "M. Johnson",
             "jockey": "J. Smith", "age": 4, "OR": 85, "rpd_tag": "P"},
            {"runner_id": "run_2", "horse_name": "Lightning Bolt", "trainer": "S. Williams",
             "jockey": "A. Brown", "age": 3, "OR": 78, "rpd_tag": "T"},
            {"runner_id": "run_3", "horse_name": "Storm Chaser", "trainer": "T. Miller",
             "jockey": "R. Davis", "age": 5, "OR": 72, "rpd_tag": "E"},
        ]
        ids = self.mem.store_runners("R001", runners)
        self.assertEqual(len(ids), 3)

        stored = self.mem.get_runners("R001")
        self.assertEqual(len(stored), 3)
        names = {r["horse_name"] for r in stored}
        self.assertIn("Thunder Strike", names)
        self.assertIn("Lightning Bolt", names)

    def test_store_and_get_prediction(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        pred = {
            "top_strike": "Thunder Strike",
            "value_pick": "Lightning Bolt",
            "danger_horse": "Storm Chaser",
            "confidence_band": "HIGH",
            "scenario_primary": "Thunder Strike leads from front",
            "threat_flags": ["pace collapse", "soft ground specialist"],
        }
        pid = self.mem.store_prediction("R001", pred)
        self.assertTrue(pid.startswith("pred_"))

        stored = self.mem.get_prediction("R001")
        self.assertEqual(stored["top_strike"], "Thunder Strike")
        self.assertEqual(stored["confidence_band"], "HIGH")

    def test_store_and_get_results(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        results = {
            "date": "2026-02-16",
            "positions": [
                {"horse_name": "Lightning Bolt", "position": 1, "bsp": 3.5, "isp": 3.0},
                {"horse_name": "Thunder Strike", "position": 2, "bsp": 2.8, "isp": 2.5},
                {"horse_name": "Storm Chaser", "position": 3, "bsp": 6.0, "isp": 5.5},
            ],
            "winning_time": "2:05.3",
            "non_runners": ["Dark Cloud"],
        }
        rid = self.mem.store_results("R001", results)
        self.assertTrue(rid.startswith("res_"))

        stored = self.mem.get_result("R001")
        positions = _from_json(stored["positions"])
        self.assertEqual(len(positions), 3)
        self.assertEqual(positions[0]["horse_name"], "Lightning Bolt")

    # ── Sigma Evaluation ──

    def _setup_full_race(self):
        """Helper: set up a complete race with prediction and results."""
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_runners("R001", [
            {"runner_id": "run_1", "horse_name": "Thunder Strike", "trainer": "M. Johnson",
             "jockey": "J. Smith", "OR": 85, "rpd_tag": "P"},
            {"runner_id": "run_2", "horse_name": "Lightning Bolt", "trainer": "S. Williams",
             "jockey": "A. Brown", "OR": 78, "rpd_tag": "T"},
            {"runner_id": "run_3", "horse_name": "Storm Chaser", "trainer": "T. Miller",
             "jockey": "R. Davis", "OR": 72, "rpd_tag": "E"},
        ])
        self.mem.store_prediction("R001", {
            "top_strike": "Thunder Strike",
            "value_pick": "Lightning Bolt",
            "danger_horse": "Storm Chaser",
            "date": "2026-02-16",
        })
        self.mem.store_results("R001", {
            "date": "2026-02-16",
            "positions": [
                {"horse_name": "Lightning Bolt", "position": 1, "bsp": 3.5},
                {"horse_name": "Thunder Strike", "position": 2, "bsp": 2.8},
                {"horse_name": "Storm Chaser", "position": 3, "bsp": 6.0},
            ],
        })

    def test_sigma_evaluation_hit_place_miss(self):
        self._setup_full_race()
        eval_id = self.mem.run_sigma_evaluation("R001")
        self.assertIsNotNone(eval_id)

        sigma = self.mem.get_sigma("R001")
        self.assertEqual(sigma["top_strike_result"], "place")  # Thunder Strike = 2nd
        self.assertEqual(sigma["value_result"], "hit")  # Lightning Bolt = 1st
        self.assertEqual(sigma["danger_result"], "place")  # Storm Chaser = 3rd

    def test_sigma_signal_quality(self):
        self._setup_full_race()
        self.mem.run_sigma_evaluation("R001")
        sigma = self.mem.get_sigma("R001")
        # place(0.5) + hit(1.0) + place(0.5) = 2.0 / 3 = 0.667
        self.assertAlmostEqual(sigma["signal_quality"], 0.667, places=3)

    def test_sigma_no_prediction_returns_none(self):
        self.mem.store_race({"race_id": "R002", "date": "2026-02-16", "course": "Ascot"})
        self.mem.store_results("R002", {
            "date": "2026-02-16",
            "positions": [{"horse_name": "Test", "position": 1}],
        })
        result = self.mem.run_sigma_evaluation("R002")
        self.assertIsNone(result)

    # ── Pattern Queries ──

    def test_trainer_pattern_update_and_query(self):
        self._setup_full_race()
        count = self.mem.update_trainer_patterns("R001")
        self.assertGreater(count, 0)

        patterns = self.mem.query_trainer_history("M. Johnson")
        self.assertTrue(len(patterns) > 0)

        patterns_course = self.mem.query_trainer_history("M. Johnson", course="Kempton")
        self.assertTrue(len(patterns_course) > 0)

    def test_jockey_pattern_update_and_query(self):
        self._setup_full_race()
        count = self.mem.update_jockey_patterns("R001")
        self.assertGreater(count, 0)

        patterns = self.mem.query_jockey_history("J. Smith")
        self.assertTrue(len(patterns) > 0)

    def test_course_bias_update_and_query(self):
        self._setup_full_race()
        count = self.mem.update_course_bias("R001")
        self.assertGreater(count, 0)

        bias = self.mem.query_course_bias("Kempton")
        self.assertTrue(len(bias) > 0)

    # ── Market Behaviour ──

    def test_log_market_behaviour(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_runners("R001", [
            {"runner_id": "run_1", "horse_name": "Thunder Strike"},
        ])
        mid = self.mem.log_market_behaviour("run_1", 4.0, 3.5, 3.2)
        self.assertTrue(mid.startswith("mkt_"))

        row = self.mem.conn.execute(
            "SELECT * FROM market_behaviour WHERE market_id = ?", (mid,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["drift_pct"], -20.0)  # (3.2 - 4.0) / 4.0 * 100
        self.assertEqual(row["drift_type"], "informative")
        self.assertTrue(row["steam_flag"])

    def test_market_noise_drift(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_runners("R001", [
            {"runner_id": "run_1", "horse_name": "Thunder Strike"},
        ])
        mid = self.mem.log_market_behaviour("run_1", 4.0, 4.1, 4.2)
        row = self.mem.conn.execute(
            "SELECT * FROM market_behaviour WHERE market_id = ?", (mid,)
        ).fetchone()
        self.assertEqual(row["drift_type"], "noise")
        self.assertFalse(row["steam_flag"])

    # ── RPD Validation ──

    def test_validate_rpd_tag_proven(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_runners("R001", [
            {"runner_id": "run_1", "horse_name": "Thunder Strike", "rpd_tag": "P"},
        ])
        rpd_id = self.mem.validate_rpd_tag("run_1", 2, 3.5)
        self.assertIsNotNone(rpd_id)

        row = self.mem.conn.execute(
            "SELECT * FROM rpd_validation WHERE rpd_id = ?", (rpd_id,)
        ).fetchone()
        self.assertTrue(row["tag_validated"])  # P tag, position 2 <= 3
        self.assertEqual(row["predicted_intent"], "proven")

    def test_validate_rpd_tag_exposed(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_runners("R001", [
            {"runner_id": "run_3", "horse_name": "Storm Chaser", "rpd_tag": "E"},
        ])
        rpd_id = self.mem.validate_rpd_tag("run_3", 5, 8.0)
        row = self.mem.conn.execute(
            "SELECT * FROM rpd_validation WHERE rpd_id = ?", (rpd_id,)
        ).fetchone()
        self.assertTrue(row["tag_validated"])  # E tag, position 5 > 3 = validated
        self.assertEqual(row["predicted_intent"], "exposed")

    # ── Pre-Race Context ──

    def test_get_pre_race_context(self):
        self._setup_full_race()
        self.mem.update_trainer_patterns("R001")
        self.mem.update_jockey_patterns("R001")
        self.mem.run_sigma_evaluation("R001")

        context = self.mem.get_pre_race_context(
            "Kempton", ["M. Johnson"], ["J. Smith"]
        )
        self.assertEqual(context["course"], "Kempton")
        self.assertIn("M. Johnson", context["trainer_patterns"])
        self.assertIn("J. Smith", context["jockey_patterns"])

    # ── System Stats ──

    def test_get_system_stats(self):
        self._setup_full_race()
        self.mem.run_sigma_evaluation("R001")

        stats = self.mem.get_system_stats()
        self.assertEqual(stats["total_races"], 1)
        self.assertEqual(stats["total_runners"], 3)
        self.assertEqual(stats["total_predictions"], 1)
        self.assertEqual(stats["total_results"], 1)
        self.assertEqual(stats["total_evaluations"], 1)
        self.assertGreater(stats["avg_signal_quality"], 0)

    def test_empty_stats(self):
        stats = self.mem.get_system_stats()
        self.assertEqual(stats["total_races"], 0)
        self.assertEqual(stats["top_strike_hit_rate"], 0.0)

    # ── Sigma Report ──

    def test_export_sigma_report(self):
        self._setup_full_race()
        self.mem.run_sigma_evaluation("R001")

        report = self.mem.export_sigma_report("2026-02-01", "2026-02-28")
        self.assertIn("VÉLØ SIGMA Performance Report", report)
        self.assertIn("Kempton", report)
        self.assertIn("place", report)

    def test_export_sigma_report_empty(self):
        report = self.mem.export_sigma_report("2099-01-01", "2099-12-31")
        self.assertIn("No evaluations found", report)

    # ── List Races ──

    def test_list_races(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_race({"race_id": "R002", "date": "2026-02-16", "course": "Ascot"})
        self.mem.store_race({"race_id": "R003", "date": "2026-02-17", "course": "Kempton"})

        all_races = self.mem.list_races()
        self.assertEqual(len(all_races), 3)

        kempton = self.mem.list_races(course="Kempton")
        self.assertEqual(len(kempton), 2)

        feb16 = self.mem.list_races(date="2026-02-16")
        self.assertEqual(len(feb16), 2)

    # ── Upsert Behaviour ──

    def test_store_race_upsert(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton", "going": "Good"})
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton", "going": "Soft"})
        race = self.mem.get_race("R001")
        self.assertEqual(race["going"], "Soft")


class TestRPDValidator(unittest.TestCase):
    """Test the RPD-C Validation Engine."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.mem = VeloMemoryEngine(self.tmp.name)
        self.rpd = RPDValidator(self.mem)

    def tearDown(self):
        self.mem.close()
        os.unlink(self.tmp.name)

    def _setup_race_with_results(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_runners("R001", [
            {"runner_id": "run_1", "horse_name": "Thunder Strike", "rpd_tag": "P"},
            {"runner_id": "run_2", "horse_name": "Lightning Bolt", "rpd_tag": "T"},
            {"runner_id": "run_3", "horse_name": "Storm Chaser", "rpd_tag": "E"},
            {"runner_id": "run_4", "horse_name": "Dark Cloud", "rpd_tag": "H"},
            {"runner_id": "run_5", "horse_name": "Silver Arrow", "rpd_tag": "S"},
        ])
        self.mem.store_results("R001", {
            "date": "2026-02-16",
            "positions": [
                {"horse_name": "Thunder Strike", "position": 1, "bsp": 2.8},
                {"horse_name": "Lightning Bolt", "position": 3, "bsp": 4.0},
                {"horse_name": "Storm Chaser", "position": 5, "bsp": 8.0},
                {"horse_name": "Dark Cloud", "position": 2, "bsp": 6.0},
                {"horse_name": "Silver Arrow", "position": 4, "bsp": 12.0},
            ],
        })

    def test_validate_batch(self):
        self._setup_race_with_results()
        results = self.rpd.validate_batch("R001")
        self.assertEqual(len(results), 5)

        by_horse = {r["horse_name"]: r for r in results}
        self.assertTrue(by_horse["Thunder Strike"]["validated"])   # P, pos 1
        self.assertTrue(by_horse["Lightning Bolt"]["validated"])   # T, pos 3 <= 5
        self.assertTrue(by_horse["Storm Chaser"]["validated"])     # E, pos 5 > 3
        self.assertTrue(by_horse["Dark Cloud"]["validated"])       # H, pos 2 <= 3
        self.assertFalse(by_horse["Silver Arrow"]["validated"])    # S, pos 4 > 2

    def test_get_tag_accuracy(self):
        self._setup_race_with_results()
        self.rpd.validate_batch("R001")

        accuracy = self.rpd.get_tag_accuracy()
        self.assertIn("P", accuracy)
        self.assertEqual(accuracy["P"]["total"], 1)
        self.assertEqual(accuracy["P"]["validated"], 1)
        self.assertEqual(accuracy["P"]["accuracy"], 1.0)

        self.assertEqual(accuracy["S"]["total"], 1)
        self.assertEqual(accuracy["S"]["validated"], 0)
        self.assertEqual(accuracy["S"]["accuracy"], 0.0)

    def test_get_tag_accuracy_by_course(self):
        self._setup_race_with_results()
        self.rpd.validate_batch("R001")

        accuracy = self.rpd.get_tag_accuracy_by_course("Kempton")
        self.assertIn("P", accuracy)
        self.assertEqual(accuracy["P"]["course"], "Kempton")

        # Non-existent course
        empty = self.rpd.get_tag_accuracy_by_course("Nonexistent")
        self.assertEqual(len(empty), 0)

    def test_recalibration_report(self):
        self._setup_race_with_results()
        self.rpd.validate_batch("R001")

        report = self.rpd.recalibration_report()
        self.assertIn("RPD-C Recalibration Report", report)
        self.assertIn("Proven", report)

    def test_recalibration_report_empty(self):
        report = self.rpd.recalibration_report()
        self.assertIn("No validation data available", report)

    def test_validate_batch_no_results(self):
        self.mem.store_race({"race_id": "R001", "date": "2026-02-16", "course": "Kempton"})
        self.mem.store_runners("R001", [
            {"runner_id": "run_1", "horse_name": "Thunder Strike", "rpd_tag": "P"},
        ])
        results = self.rpd.validate_batch("R001")
        self.assertEqual(len(results), 0)

    def test_validation_details(self):
        self._setup_race_with_results()
        self.rpd.validate_batch("R001")

        details = self.rpd.get_validation_details("R001")
        self.assertEqual(len(details), 5)

        all_details = self.rpd.get_validation_details()
        self.assertEqual(len(all_details), 5)


class TestGitHubSync(unittest.TestCase):
    """Test the GitHub sync module."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Initialize a git repo in tmpdir
        os.system(f"cd {self.tmpdir} && git init && git config user.email 'test@test.com' && git config user.name 'Test'")
        os.system(f"cd {self.tmpdir} && touch README.md && git add . && git commit -m 'init'")
        self.sync = GitHubSync(repo_root=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ensure_dirs(self):
        for d in ["analyses", "sigma", "data", "reports/weekly"]:
            self.assertTrue((Path(self.tmpdir) / d).is_dir())

    def test_sanitize_course(self):
        self.assertEqual(self.sync._sanitize_course("Kempton Park"), "kempton_park")
        self.assertEqual(self.sync._sanitize_course("Ascot"), "ascot")
        self.assertEqual(self.sync._sanitize_course("Aintree"), "aintree")

    def test_auto_commit_analysis(self):
        # Create a temp analysis file
        analysis = Path(self.tmpdir) / "temp_analysis.md"
        analysis.write_text("# Test Analysis\nTop Strike: Thunder Strike\n")

        result = self.sync.auto_commit_analysis("2026-02-16", "Kempton", str(analysis))
        self.assertTrue(result)

        dest = Path(self.tmpdir) / "analyses" / "2026-02-16" / "kempton_analysis.md"
        self.assertTrue(dest.exists())

    def test_auto_commit_sigma(self):
        sigma = Path(self.tmpdir) / "temp_sigma.md"
        sigma.write_text("# Sigma Debrief\nSignal Quality: 0.667\n")

        result = self.sync.auto_commit_sigma("2026-02-16", "Kempton", str(sigma))
        self.assertTrue(result)

        dest = Path(self.tmpdir) / "sigma" / "2026-02-16" / "kempton_sigma.md"
        self.assertTrue(dest.exists())

    def test_auto_commit_database(self):
        db = Path(self.tmpdir) / "data" / "velo_memory.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_bytes(b"fake_db_content")

        result = self.sync.auto_commit_database(str(db))
        self.assertTrue(result)

    def test_get_status(self):
        status = self.sync.get_status()
        self.assertIn("branch", status)
        self.assertIn("dirty_files", status)
        self.assertIn("recent_commits", status)

    def test_commit_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.sync.auto_commit_analysis("2026-02-16", "Kempton", "/nonexistent/file.md")


class TestIntegrationParsers(unittest.TestCase):
    """Test the integration CLI parsers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_parse_json_race_card(self):
        card = {
            "race_id": "R001",
            "date": "2026-02-16",
            "course": "Kempton",
            "going": "Good to Soft",
            "distance": "1m2f",
            "runners": [
                {"id": "run_1", "name": "Thunder Strike", "trainer": "M. Johnson",
                 "jockey": "J. Smith", "age": 4},
                {"id": "run_2", "name": "Lightning Bolt", "trainer": "S. Williams",
                 "jockey": "A. Brown", "age": 3},
            ],
        }
        path = Path(self.tmpdir) / "card.json"
        path.write_text(json.dumps(card))

        race_data, runners = parse_race_card_file(str(path))
        self.assertEqual(race_data["race_id"], "R001")
        self.assertEqual(race_data["course"], "Kempton")
        self.assertEqual(len(runners), 2)
        self.assertEqual(runners[0]["horse_name"], "Thunder Strike")

    def test_parse_md_race_card(self):
        md_content = """# Kempton — 2026-02-16

Going: Good to Soft
Distance: 1m2f
Class 4

1. **Thunder Strike** (M. Johnson)
2. **Lightning Bolt** (S. Williams)
3. **Storm Chaser** (T. Miller)
"""
        path = Path(self.tmpdir) / "card.md"
        path.write_text(md_content)

        race_data, runners = parse_race_card_file(str(path))
        self.assertEqual(race_data["course"], "Kempton")
        self.assertEqual(race_data["going"], "Good to Soft")
        self.assertEqual(race_data["date"], "2026-02-16")

    def test_parse_analysis_file(self):
        analysis = """# Kempton 14:30 Analysis — 2026-02-16

Top Strike: Thunder Strike
Value Pick: Lightning Bolt
Danger Horse: Storm Chaser
Confidence: HIGH

Primary Scenario: Thunder Strike leads from the front on good ground
Secondary Scenario: Lightning Bolt comes from behind if pace collapses
"""
        path = Path(self.tmpdir) / "analysis.md"
        path.write_text(analysis)

        pred = parse_analysis_file(str(path))
        self.assertEqual(pred["top_strike"], "Thunder Strike")
        self.assertEqual(pred["value_pick"], "Lightning Bolt")
        self.assertEqual(pred["danger_horse"], "Storm Chaser")
        self.assertEqual(pred["confidence_band"], "HIGH")
        self.assertEqual(pred["date"], "2026-02-16")

    def test_parse_results_file_structured(self):
        results = {
            "date": "2026-02-16",
            "positions": [
                {"horse_name": "Lightning Bolt", "position": 1, "bsp": 3.5},
                {"horse_name": "Thunder Strike", "position": 2, "bsp": 2.8},
            ],
            "winning_time": "2:05.3",
        }
        path = Path(self.tmpdir) / "results.json"
        path.write_text(json.dumps(results))

        parsed = parse_results_file(str(path))
        self.assertEqual(len(parsed["positions"]), 2)
        self.assertEqual(parsed["winning_time"], "2:05.3")

    def test_parse_results_file_simple_format(self):
        results = {
            "winner": "run_2",
            "placed": ["run_2", "run_1", "run_3"],
            "starting_prices": {"run_1": 2.8, "run_2": 3.5, "run_3": 6.0},
        }
        path = Path(self.tmpdir) / "results.json"
        path.write_text(json.dumps(results))

        parsed = parse_results_file(str(path))
        self.assertEqual(len(parsed["positions"]), 3)
        self.assertEqual(parsed["positions"][0]["position"], 1)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_json_serialization(self):
        self.assertEqual(_json(None), None)
        self.assertEqual(_json("test"), "test")
        self.assertEqual(_json([1, 2, 3]), "[1, 2, 3]")
        self.assertEqual(_json({"a": 1}), '{"a": 1}')

    def test_json_deserialization(self):
        self.assertIsNone(_from_json(None))
        self.assertEqual(_from_json('[1, 2]'), [1, 2])
        self.assertEqual(_from_json('{"a": 1}'), {"a": 1})
        self.assertEqual(_from_json("not json"), "not json")

    def test_row_to_dict(self):
        self.assertEqual(_row_to_dict(None), {})


class TestMultiRacePatterns(unittest.TestCase):
    """Test pattern accumulation across multiple races."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.mem = VeloMemoryEngine(self.tmp.name)

    def tearDown(self):
        self.mem.close()
        os.unlink(self.tmp.name)

    def test_trainer_patterns_across_races(self):
        """Trainer patterns should accumulate across multiple races."""
        # Race 1: Trainer wins
        self.mem.store_race({"race_id": "R001", "date": "2026-02-10", "course": "Kempton",
                            "going": "Good", "race_type": "Handicap"})
        self.mem.store_runners("R001", [
            {"runner_id": "r1_1", "horse_name": "Alpha", "trainer": "T. Trainer", "OR": 80},
        ])
        self.mem.store_results("R001", {
            "date": "2026-02-10",
            "positions": [{"horse_name": "Alpha", "position": 1, "bsp": 3.0}],
        })

        # Race 2: Trainer places
        self.mem.store_race({"race_id": "R002", "date": "2026-02-12", "course": "Kempton",
                            "going": "Good", "race_type": "Handicap"})
        self.mem.store_runners("R002", [
            {"runner_id": "r2_1", "horse_name": "Beta", "trainer": "T. Trainer", "OR": 75},
        ])
        self.mem.store_results("R002", {
            "date": "2026-02-12",
            "positions": [
                {"horse_name": "Other", "position": 1},
                {"horse_name": "Beta", "position": 3, "bsp": 5.0},
            ],
        })

        self.mem.update_trainer_patterns("R001")
        self.mem.update_trainer_patterns("R002")

        patterns = self.mem.query_trainer_history("T. Trainer", course="Kempton")
        # Should have at least one pattern with 2 runs
        all_pattern = [p for p in patterns if p["course"] == "_ALL_"]
        self.assertTrue(any(p["runs"] >= 2 for p in all_pattern))

    def test_sigma_trends_over_time(self):
        """Multiple sigma evaluations should show trends."""
        for i in range(5):
            rid = f"R{i:03d}"
            self.mem.store_race({"race_id": rid, "date": f"2026-02-{10+i}", "course": "Kempton"})
            self.mem.store_prediction(rid, {
                "top_strike": "Horse A",
                "value_pick": "Horse B",
                "danger_horse": "Horse C",
                "date": f"2026-02-{10+i}",
            })
            # Alternate between wins and misses
            if i % 2 == 0:
                positions = [
                    {"horse_name": "Horse A", "position": 1},
                    {"horse_name": "Horse B", "position": 2},
                    {"horse_name": "Horse C", "position": 3},
                ]
            else:
                positions = [
                    {"horse_name": "Horse X", "position": 1},
                    {"horse_name": "Horse Y", "position": 2},
                    {"horse_name": "Horse Z", "position": 3},
                ]
            self.mem.store_results(rid, {"date": f"2026-02-{10+i}", "positions": positions})
            self.mem.run_sigma_evaluation(rid)

        stats = self.mem.get_system_stats()
        self.assertEqual(stats["total_evaluations"], 5)
        # Should have some hits and some misses
        self.assertGreater(stats["top_strike_hit_rate"], 0)
        self.assertLess(stats["top_strike_hit_rate"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
