"""
Tests for run_post_race_truth_loop.py — Layer 4 Post-Race Truth Loop.

Coverage:
  - All 6 core_miss_type classifications
  - gate_upgrade_result (helped / overfired / not_triggered)
  - ew_flag_result (helped / missed / not_triggered)
  - archetype_correct logic (WIN / PLACED / MISS / trap / chaos)
  - state_tag_truths (bullish/bearish/neutral per tag)
  - build_summary aggregates
  - weekly rollup accumulation
  - Schema A and Schema B verdict loading
"""
import json
import pytest
from pathlib import Path

# Ensure repo root is on path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.run_post_race_truth_loop import (
    _classify_core_miss,
    _classify_archetype,
    _classify_gate,
    _classify_ew,
    _state_tag_truths,
    build_truth_record,
    build_summary,
    build_weekly_rollup,
    _load_verdicts,
    _load_sigma_rows,
    TRUTH_DIR,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _top(
    horse="Test Horse",
    race_id="100",
    velo_prime_prob=0.50,
    sp_dec=5.0,
    race_archetype="Structure",
    archetype_trap_flag=False,
    archetype_suppression=False,
    tie_gate_fires=False,
    tie_gate_tier_upgrade=None,
    tie_gate_ew_flag=False,
    tie_gate_signal_count=0,
    horse_state=None,
    race_tier="A",
    course="Ayr",
    off_time="14:30",
) -> dict:
    return {
        "horse": horse,
        "race_id": race_id,
        "velo_prime_prob": velo_prime_prob,
        "sp_dec": sp_dec,
        "race_archetype": race_archetype,
        "archetype_label": race_archetype,
        "archetype_confidence": "high",
        "archetype_trap_flag": archetype_trap_flag,
        "archetype_suppression": archetype_suppression,
        "tie_gate_fires": tie_gate_fires,
        "tie_gate_tier_upgrade": tie_gate_tier_upgrade,
        "tie_gate_ew_flag": tie_gate_ew_flag,
        "tie_gate_signal_count": tie_gate_signal_count,
        "horse_state": horse_state or {
            "readiness_state": "warming",
            "release_state": "hidden",
            "market_state": "ignored",
            "race_fit_state": "weak",
            "chaos_exposure": "low",
        },
        "_race_tier": race_tier,
        "_race_course": course,
        "_race_off_time": off_time,
    }


def _sigma(
    race_id="100",
    outcome="WIN",
    miss_class=None,
    ew_outcome=None,
    actual_name="Test Horse",
    winner_sp=5.0,
    course="Ayr",
    off="14:30",
) -> dict:
    return {
        "race_id": race_id,
        "outcome": outcome,
        "miss_class": miss_class,
        "ew_outcome": ew_outcome,
        "actual_name": actual_name,
        "winner_sp": winner_sp,
        "course": course,
        "off": off,
    }


# ------------------------------------------------------------------
# core_miss_type
# ------------------------------------------------------------------

class TestClassifyCoreMiss:
    def test_win_returns_none(self):
        assert _classify_core_miss(_top(), "WIN") is None

    def test_placed_no_suppression(self):
        t = _top(archetype_suppression=False)
        assert _classify_core_miss(t, "PLACED") == "right_horse_wrong_tier"

    def test_placed_with_suppression(self):
        t = _top(archetype_suppression=True)
        assert _classify_core_miss(t, "PLACED") == "wrong_suppression"

    def test_miss_trap_flag(self):
        t = _top(archetype_trap_flag=True)
        assert _classify_core_miss(t, "MISS") == "wrong_trap_read"

    def test_miss_trap_takes_priority_over_release(self):
        t = _top(
            archetype_trap_flag=True,
            horse_state={"release_state": "hidden", "readiness_state": "warming",
                         "market_state": "ignored", "race_fit_state": "weak", "chaos_exposure": "low"},
        )
        assert _classify_core_miss(t, "MISS") == "wrong_trap_read"

    def test_miss_hidden_release(self):
        t = _top(horse_state={
            "readiness_state": "warming", "release_state": "hidden",
            "market_state": "ignored", "race_fit_state": "weak", "chaos_exposure": "low",
        })
        assert _classify_core_miss(t, "MISS") == "wrong_release_read"

    def test_miss_concealed_release(self):
        t = _top(horse_state={
            "readiness_state": "warming", "release_state": "concealed",
            "market_state": "ignored", "race_fit_state": "weak", "chaos_exposure": "low",
        })
        assert _classify_core_miss(t, "MISS") == "wrong_release_read"

    def test_miss_high_chaos(self):
        t = _top(horse_state={
            "readiness_state": "warming", "release_state": "live",
            "market_state": "ignored", "race_fit_state": "weak", "chaos_exposure": "high",
        })
        assert _classify_core_miss(t, "MISS") == "wrong_chaos_read"

    def test_miss_extreme_chaos(self):
        t = _top(horse_state={
            "readiness_state": "warming", "release_state": "live",
            "market_state": "ignored", "race_fit_state": "weak", "chaos_exposure": "extreme",
        })
        assert _classify_core_miss(t, "MISS") == "wrong_chaos_read"

    def test_miss_generic(self):
        t = _top(horse_state={
            "readiness_state": "warming", "release_state": "live",
            "market_state": "ignored", "race_fit_state": "weak", "chaos_exposure": "low",
        })
        assert _classify_core_miss(t, "MISS") == "wrong_top_horse"


# ------------------------------------------------------------------
# gate_upgrade_result
# ------------------------------------------------------------------

class TestClassifyGate:
    def test_not_triggered(self):
        t = _top(tie_gate_fires=False)
        assert _classify_gate(t, True) == "not_triggered"
        assert _classify_gate(t, False) == "not_triggered"

    def test_helped_when_placed(self):
        t = _top(tie_gate_fires=True)
        assert _classify_gate(t, True) == "helped"

    def test_overfired_when_missed(self):
        t = _top(tie_gate_fires=True)
        assert _classify_gate(t, False) == "overfired"


# ------------------------------------------------------------------
# ew_flag_result
# ------------------------------------------------------------------

class TestClassifyEW:
    def test_not_triggered(self):
        t = _top(tie_gate_ew_flag=False)
        assert _classify_ew(t, None) == "not_triggered"
        assert _classify_ew(t, "EW_PLACE") == "not_triggered"

    def test_helped_ew_place(self):
        t = _top(tie_gate_ew_flag=True)
        assert _classify_ew(t, "EW_PLACE") == "helped"

    def test_helped_ew_win(self):
        t = _top(tie_gate_ew_flag=True)
        assert _classify_ew(t, "EW_WIN") == "helped"

    def test_missed_no_place(self):
        t = _top(tie_gate_ew_flag=True)
        assert _classify_ew(t, None) == "missed"


# ------------------------------------------------------------------
# archetype_correct
# ------------------------------------------------------------------

class TestClassifyArchetype:
    def test_win_always_correct(self):
        assert _classify_archetype(_top(), "WIN", None) is True

    def test_placed_non_trap_correct(self):
        t = _top(archetype_trap_flag=False)
        assert _classify_archetype(t, "PLACED", None) is True

    def test_placed_trap_incorrect(self):
        t = _top(archetype_trap_flag=True)
        assert _classify_archetype(t, "PLACED", None) is False

    def test_miss_trap_flag_correct(self):
        t = _top(archetype_trap_flag=True)
        assert _classify_archetype(t, "MISS", "mid_priced_won") is True

    def test_miss_chaos_outsider_correct(self):
        t = _top(race_archetype="Chaos")
        assert _classify_archetype(t, "MISS", "outsider_won") is True

    def test_miss_chaos_short_fav_incorrect(self):
        t = _top(race_archetype="Chaos")
        assert _classify_archetype(t, "MISS", "short_fav_won") is False

    def test_miss_structure_incorrect(self):
        t = _top(race_archetype="Structure", archetype_trap_flag=False)
        assert _classify_archetype(t, "MISS", "mid_priced_won") is False


# ------------------------------------------------------------------
# state_tag_truths
# ------------------------------------------------------------------

class TestStateTagTruths:
    def _hs(self, **kw) -> dict:
        base = {
            "readiness_state": "warming", "release_state": "live",
            "market_state": "ignored", "race_fit_state": "weak", "chaos_exposure": "low",
        }
        base.update(kw)
        return base

    def test_bullish_readiness_placed(self):
        t = _top(horse_state=self._hs(readiness_state="peak"))
        assert _state_tag_truths(t, True)["state_truth_readiness"] is True

    def test_bullish_readiness_missed(self):
        t = _top(horse_state=self._hs(readiness_state="ready"))
        assert _state_tag_truths(t, False)["state_truth_readiness"] is False

    def test_bearish_readiness_missed(self):
        t = _top(horse_state=self._hs(readiness_state="stale"))
        assert _state_tag_truths(t, False)["state_truth_readiness"] is True

    def test_neutral_readiness_returns_none(self):
        t = _top(horse_state=self._hs(readiness_state="warming"))
        assert _state_tag_truths(t, True)["state_truth_readiness"] is None

    def test_bullish_release_placed(self):
        t = _top(horse_state=self._hs(release_state="live"))
        assert _state_tag_truths(t, True)["state_truth_release"] is True

    def test_bearish_release_missed(self):
        t = _top(horse_state=self._hs(release_state="hidden"))
        assert _state_tag_truths(t, False)["state_truth_release"] is True

    def test_bullish_market_placed(self):
        t = _top(horse_state=self._hs(market_state="quietly_backed"))
        assert _state_tag_truths(t, True)["state_truth_market"] is True

    def test_bearish_market_missed(self):
        t = _top(horse_state=self._hs(market_state="drifting"))
        assert _state_tag_truths(t, False)["state_truth_market"] is True

    def test_neutral_market_returns_none(self):
        t = _top(horse_state=self._hs(market_state="ignored"))
        assert _state_tag_truths(t, True)["state_truth_market"] is None

    def test_bullish_race_fit_placed(self):
        t = _top(horse_state=self._hs(race_fit_state="strong"))
        assert _state_tag_truths(t, True)["state_truth_race_fit"] is True

    def test_bearish_race_fit_missed(self):
        t = _top(horse_state=self._hs(race_fit_state="weak"))
        assert _state_tag_truths(t, False)["state_truth_race_fit"] is True

    def test_chaos_high_missed_correct(self):
        t = _top(horse_state=self._hs(chaos_exposure="high"))
        assert _state_tag_truths(t, False)["state_truth_chaos"] is True

    def test_chaos_high_placed_incorrect(self):
        t = _top(horse_state=self._hs(chaos_exposure="high"))
        assert _state_tag_truths(t, True)["state_truth_chaos"] is False

    def test_chaos_low_placed_correct(self):
        t = _top(horse_state=self._hs(chaos_exposure="low"))
        assert _state_tag_truths(t, True)["state_truth_chaos"] is True

    def test_chaos_low_missed_incorrect(self):
        t = _top(horse_state=self._hs(chaos_exposure="low"))
        assert _state_tag_truths(t, False)["state_truth_chaos"] is False

    def test_chaos_medium_returns_none(self):
        t = _top(horse_state=self._hs(chaos_exposure="medium"))
        assert _state_tag_truths(t, True)["state_truth_chaos"] is None


# ------------------------------------------------------------------
# build_truth_record
# ------------------------------------------------------------------

class TestBuildTruthRecord:
    def test_win_record_fields(self):
        t = _top(race_id="200", velo_prime_prob=0.55)
        s = _sigma(race_id="200", outcome="WIN", actual_name="Test Horse")
        r = build_truth_record("200", t, s, "2026-07-27")
        assert r["top_horse_won"] is True
        assert r["top_horse_placed"] is True
        assert r["core_miss_type"] is None
        assert r["gate_upgrade_result"] == "not_triggered"
        assert r["archetype_correct"] is True
        assert r["race_id"] == "200"
        assert r["race_date"] == "2026-07-27"

    def test_miss_record_low_confidence_winner_note(self):
        # Low-confidence WIN gets a learning note
        t = _top(race_id="201", velo_prime_prob=0.30)
        s = _sigma(race_id="201", outcome="WIN")
        r = build_truth_record("201", t, s, "2026-07-27")
        assert any("low_confidence_winner" in n for n in r["learning_notes"])

    def test_gate_overfired_note(self):
        t = _top(race_id="202", tie_gate_fires=True, tie_gate_tier_upgrade="B")
        s = _sigma(race_id="202", outcome="MISS", miss_class="mid_priced_won")
        r = build_truth_record("202", t, s, "2026-07-27")
        assert r["gate_upgrade_result"] == "overfired"
        assert any("gate_overfired" in n for n in r["learning_notes"])

    def test_trap_placed_note(self):
        t = _top(race_id="203", archetype_trap_flag=True)
        s = _sigma(race_id="203", outcome="WIN")
        r = build_truth_record("203", t, s, "2026-07-27")
        assert any("trap_flagged_but_horse_placed" in n for n in r["learning_notes"])

    def test_course_falls_back_to_sigma(self):
        t = _top(race_id="204")
        t["_race_course"] = None
        s = _sigma(race_id="204", outcome="WIN", course="Cheltenham")
        r = build_truth_record("204", t, s, "2026-07-27")
        assert r["course"] == "Cheltenham"


# ------------------------------------------------------------------
# build_summary
# ------------------------------------------------------------------

class TestBuildSummary:
    def _make_records(self):
        t_win  = _top(race_id="10")
        t_miss = _top(race_id="11")
        t_plc  = _top(race_id="12")
        return [
            build_truth_record("10", t_win,  _sigma(race_id="10", outcome="WIN"),  "2026-07-27"),
            build_truth_record("11", t_miss, _sigma(race_id="11", outcome="MISS", miss_class="mid_priced_won"), "2026-07-27"),
            build_truth_record("12", t_plc,  _sigma(race_id="12", outcome="PLACED"), "2026-07-27"),
        ]

    def test_counts(self):
        records = self._make_records()
        s = build_summary(records, "2026-07-27")
        assert s["races_evaluated"] == 3
        assert s["wins"] == 1
        assert s["placed"] == 2  # WIN + PLACED
        assert abs(s["sr"] - 1/3) < 0.001
        assert abs(s["place_rate"] - 2/3) < 0.001

    def test_miss_type_breakdown_present(self):
        records = self._make_records()
        s = build_summary(records, "2026-07-27")
        assert "miss_type_breakdown" in s
        # WIN: None, PLACED: right_horse_wrong_tier, MISS: wrong_release_read — 2 types total
        assert sum(s["miss_type_breakdown"].values()) == 2
        assert "wrong_release_read" in s["miss_type_breakdown"]

    def test_empty_records(self):
        s = build_summary([], "2026-07-27")
        assert s["races_evaluated"] == 0

    def test_archetype_stats_present(self):
        records = self._make_records()
        s = build_summary(records, "2026-07-27")
        assert "archetype_stats" in s
        assert "Structure" in s["archetype_stats"]

    def test_state_truth_rates_present(self):
        records = self._make_records()
        s = build_summary(records, "2026-07-27")
        assert "state_truth_rates" in s
        assert "state_truth_market" in s["state_truth_rates"]


# ------------------------------------------------------------------
# weekly rollup
# ------------------------------------------------------------------

class TestWeeklyRollup:
    def test_rollup_reads_multiple_dates(self, tmp_path, monkeypatch):
        import scripts.ops.run_post_race_truth_loop as module
        monkeypatch.setattr(module, "TRUTH_DIR", tmp_path)

        from datetime import date as dt, timedelta
        base = dt(2026, 7, 27)

        # Write 3 days of truth JSONL
        for i in range(3):
            d = base - timedelta(days=i)
            tag = d.strftime("%Y_%m_%d")
            record = {
                "top_horse_won": i == 0,
                "top_horse_placed": i <= 1,
                "core_miss_type": "wrong_top_horse" if i == 2 else None,
                "assigned_archetype": "Structure",
                "gate_upgrade_result": "not_triggered",
                "ew_flag_result": "not_triggered",
                "state_truth_readiness": None,
                "state_truth_release": None,
                "state_truth_market": True,
                "state_truth_race_fit": None,
                "state_truth_chaos": True,
            }
            p = tmp_path / f"truth_loop_{tag}.jsonl"
            p.write_text(json.dumps(record) + "\n", encoding="utf-8")

        rollup = build_weekly_rollup(base)
        assert rollup["races_evaluated"] == 3
        assert len(rollup["dates_loaded"]) == 3
        assert rollup["overall_sr"] == pytest.approx(1/3, abs=0.01)
        assert "state_reliability" in rollup
        assert rollup["gate_precision"]["fired"] == 0
        assert rollup["most_common_miss_type"] == ("wrong_top_horse", 1)

    def test_rollup_empty_returns_zero(self, tmp_path, monkeypatch):
        import scripts.ops.run_post_race_truth_loop as module
        monkeypatch.setattr(module, "TRUTH_DIR", tmp_path)
        from datetime import date as dt
        rollup = build_weekly_rollup(dt(2026, 7, 27))
        assert rollup["races_evaluated"] == 0


# ------------------------------------------------------------------
# Schema A / B verdict loading
# ------------------------------------------------------------------

class TestLoadVerdicts:
    def test_schema_b_loaded(self, tmp_path, monkeypatch):
        import scripts.ops.run_post_race_truth_loop as module
        monkeypatch.setattr(module, "ROOT", tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        verdict_b = [{"race_id": "50", "tier": "A", "course": "Ayr", "off_time": "14:30", "top": {
            "horse": "Test", "race_id": "50", "velo_prime_prob": 0.5,
        }}]
        (data_dir / "velo_prime_verdicts_2026_07_27.json").write_text(json.dumps(verdict_b))
        result = module._load_verdicts("2026_07_27")
        assert "50" in result
        assert result["50"]["horse"] == "Test"
        assert result["50"]["_race_tier"] == "A"

    def test_schema_a_loaded(self, tmp_path, monkeypatch):
        import scripts.ops.run_post_race_truth_loop as module
        monkeypatch.setattr(module, "ROOT", tmp_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        verdict_a = [{
            "race_id": "60", "tier": "B", "top_rank_horse_id": "999",
            "full_analysis": {"predictions": [
                {"horse_id": "999", "horse": "Old Schema", "velo_prime_prob": 0.45},
                {"horse_id": "888", "horse": "Other", "velo_prime_prob": 0.30},
            ]},
        }]
        (data_dir / "velo_prime_verdicts_2026_07_25.json").write_text(json.dumps(verdict_a))
        result = module._load_verdicts("2026_07_25")
        assert "60" in result
        assert result["60"]["horse"] == "Old Schema"
        assert result["60"]["_race_tier"] == "B"

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import scripts.ops.run_post_race_truth_loop as module
        monkeypatch.setattr(module, "ROOT", tmp_path)
        (tmp_path / "data").mkdir()
        result = module._load_verdicts("2099_01_01")
        assert result == {}


class TestLoadSigmaRows:
    def test_sigma_rows_loaded(self, tmp_path, monkeypatch):
        import scripts.ops.run_post_race_truth_loop as module
        monkeypatch.setattr(module, "ROOT", tmp_path)
        sigma_dir = tmp_path / "data" / "sigma_results"
        sigma_dir.mkdir(parents=True)
        data = {"rows": [
            {"race_id": "70", "outcome": "WIN", "miss_class": None, "ew_outcome": None,
             "actual_name": "Winner", "winner_sp": 3.0, "course": "York", "off": "15:00"},
        ]}
        (sigma_dir / "sigma_results_2026_07_27.json").write_text(json.dumps(data))
        result = module._load_sigma_rows("2026_07_27")
        assert "70" in result
        assert result["70"]["outcome"] == "WIN"

    def test_missing_sigma_returns_empty(self, tmp_path, monkeypatch):
        import scripts.ops.run_post_race_truth_loop as module
        monkeypatch.setattr(module, "ROOT", tmp_path)
        (tmp_path / "data" / "sigma_results").mkdir(parents=True)
        result = module._load_sigma_rows("2099_01_01")
        assert result == {}
