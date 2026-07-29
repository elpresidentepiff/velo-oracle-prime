"""
Tests for VFU-22: Prospective Validation — scripts/ops/vfu_prospective_validation.py

Coverage:
  - load_sigma_rows: date filtering, field extraction
  - analyse: zero rows, WIN/PLACED/MISS counting, WIN_LANE threshold, EW_CANDIDATE
  - analyse: signal verdict (HOLDING / DEGRADED / INSUFFICIENT_DATA)
  - build_brief: produces markdown with expected headers
  - main(): writes output files, returns summary dict
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_prospective_validation import (
    load_sigma_rows,
    analyse,
    build_brief,
    main,
    SIGNAL_THRESHOLD,
    HISTORICAL_BASELINE,
    MIN_ROWS_FOR_VERDICT,
    VFU_VERSION,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_sigma_file(tmp_path: Path, date_tag: str, rows: list[dict]) -> None:
    sigma_dir = tmp_path / "data" / "sigma_results"
    sigma_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date_tag.replace("_", "-"),
        "rows": rows,
    }
    (sigma_dir / f"sigma_results_{date_tag}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _row(outcome="WIN", vp=0.45, product="WIN_ONLY", ew_outcome=None):
    return {
        "race_id": "000",
        "predicted": "Test Horse",
        "outcome": outcome,
        "velo_prime_prob": vp,
        "assigned_product": product,
        "ew_outcome": ew_outcome,
    }


# ------------------------------------------------------------------
# load_sigma_rows
# ------------------------------------------------------------------

class TestLoadSigmaRows:
    def test_filters_by_cutoff(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_prospective_validation as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        _make_sigma_file(tmp_path, "2026_06_10", [_row()])
        _make_sigma_file(tmp_path, "2026_06_20", [_row(outcome="MISS")])
        rows = load_sigma_rows("2026-06-15", "2026-07-27")
        assert len(rows) == 1
        assert rows[0]["outcome"] == "MISS"

    def test_inclusive_endpoints(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_prospective_validation as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        _make_sigma_file(tmp_path, "2026_06_15", [_row(outcome="WIN")])
        _make_sigma_file(tmp_path, "2026_07_27", [_row(outcome="MISS")])
        rows = load_sigma_rows("2026-06-15", "2026-07-27")
        assert len(rows) == 2

    def test_no_files_returns_empty(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_prospective_validation as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        (tmp_path / "data" / "sigma_results").mkdir(parents=True, exist_ok=True)
        rows = load_sigma_rows("2026-06-15", "2026-07-27")
        assert rows == []

    def test_bad_json_skipped(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_prospective_validation as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        sigma_dir = tmp_path / "data" / "sigma_results"
        sigma_dir.mkdir(parents=True, exist_ok=True)
        (sigma_dir / "sigma_results_2026_06_20.json").write_text("not json", encoding="utf-8")
        rows = load_sigma_rows("2026-06-15", "2026-07-27")
        assert rows == []


# ------------------------------------------------------------------
# analyse
# ------------------------------------------------------------------

class TestAnalyse:
    def test_empty_rows(self):
        m = analyse([])
        assert m["n"] == 0

    def test_basic_counts(self):
        rows = [_row("WIN"), _row("PLACED"), _row("MISS"), _row("MISS")]
        m = analyse(rows)
        assert m["n"] == 4
        assert m["wins"] == 1
        assert m["frames"] == 2
        assert m["misses"] == 2
        assert m["sr"] == pytest.approx(0.25, abs=0.001)
        assert m["frame_rate"] == pytest.approx(0.50, abs=0.001)

    def test_win_lane_threshold(self):
        rows = [
            _row("WIN",  vp=0.50),   # above threshold
            _row("MISS", vp=0.30),   # below threshold
            _row("WIN",  vp=0.40),   # exactly at threshold — included
        ]
        m = analyse(rows)
        assert m["win_lane_n"] == 2
        assert m["win_lane_wins"] == 2
        assert m["win_lane_sr"] == pytest.approx(1.0, abs=0.001)

    def test_win_lane_below_threshold_excluded(self):
        rows = [_row("WIN", vp=0.39)]
        m = analyse(rows)
        assert m["win_lane_n"] == 0
        assert m["win_lane_sr"] is None

    def test_ew_candidate_counting(self):
        rows = [
            _row("PLACED", vp=0.45, product="EW_CANDIDATE", ew_outcome="EW_PLACE"),
            _row("WIN",    vp=0.50, product="EW_CANDIDATE", ew_outcome="EW_WIN"),
            _row("MISS",   vp=0.45, product="EW_CANDIDATE", ew_outcome=None),
            _row("WIN",    vp=0.50, product="WIN_ONLY",     ew_outcome=None),
        ]
        m = analyse(rows)
        assert m["ew_candidate_n"] == 3
        assert m["ew_candidate_placed"] == 2   # EW_PLACE + EW_WIN only

    def test_signal_verdict_insufficient_data(self):
        rows = [_row("WIN", vp=0.45)] * (MIN_ROWS_FOR_VERDICT - 1)
        m = analyse(rows)
        assert m["signal_verdict"] == "INSUFFICIENT_DATA"

    def test_signal_verdict_holding(self):
        # Need >= MIN_ROWS_FOR_VERDICT rows in WIN_LANE with SR >= 80% of baseline
        baseline_sr = HISTORICAL_BASELINE["win_lane_sr"]   # 0.416
        n = MIN_ROWS_FOR_VERDICT
        wins_needed = int(n * baseline_sr * 0.80) + 1       # just above 80% of baseline
        rows = (
            [_row("WIN",  vp=0.45)] * wins_needed +
            [_row("MISS", vp=0.45)] * (n - wins_needed)
        )
        m = analyse(rows)
        assert m["signal_verdict"] == "SIGNAL_HOLDING"

    def test_signal_verdict_degraded_major(self):
        # SR far below 60% of baseline
        n = MIN_ROWS_FOR_VERDICT
        rows = (
            [_row("WIN",  vp=0.45)] * 2 +
            [_row("MISS", vp=0.45)] * (n - 2)
        )
        m = analyse(rows)
        assert m["signal_verdict"] == "SIGNAL_DEGRADED_MAJOR"

    def test_vp_none_treated_as_zero(self):
        rows = [{"outcome": "WIN", "velo_prime_prob": None,
                 "assigned_product": "WIN_ONLY", "ew_outcome": None}]
        m = analyse(rows)
        assert m["win_lane_n"] == 0


# ------------------------------------------------------------------
# build_brief
# ------------------------------------------------------------------

class TestBuildBrief:
    def _summary(self):
        return {
            "cutoff": "2026-06-15",
            "through": "2026-07-27",
            "metrics": {
                "n": 50, "wins": 10, "frames": 20,
                "win_lane_n": 30, "win_lane_wins": 12, "win_lane_frames": 18,
                "win_lane_sr": 0.400, "win_lane_frame_rate": 0.600,
                "ew_candidate_n": 8, "ew_candidate_placed": 5,
                "ew_candidate_place_rate": 0.625,
                "signal_verdict": "SIGNAL_HOLDING",
            },
            "classification_codes": ["VFU_22_PROSPECTIVE_VALIDATION_COMPLETE"],
        }

    def test_has_header(self):
        brief = build_brief(self._summary())
        assert "VFU-22" in brief

    def test_has_signal_verdict(self):
        brief = build_brief(self._summary())
        assert "SIGNAL_HOLDING" in brief

    def test_has_period(self):
        brief = build_brief(self._summary())
        assert "2026-06-15" in brief


# ------------------------------------------------------------------
# main() integration
# ------------------------------------------------------------------

class TestMain:
    def _setup_data(self, tmp_path: Path) -> None:
        rows_a = [_row("WIN", vp=0.50)] * 5 + [_row("MISS", vp=0.45)] * 10
        rows_b = [_row("PLACED", vp=0.42, product="EW_CANDIDATE", ew_outcome="EW_PLACE")] * 3
        _make_sigma_file(tmp_path, "2026_06_20", rows_a)
        _make_sigma_file(tmp_path, "2026_07_05", rows_b)

    def test_main_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_prospective_validation as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        monkeypatch.setattr(module, "OUTPUT_SUMMARY",
                            tmp_path / "data" / "reports" / "vfu_22_summary.json")
        monkeypatch.setattr(module, "OUTPUT_BRIEF",
                            tmp_path / "data" / "reports" / "vfu_22_brief.md")
        (tmp_path / "data" / "reports").mkdir(parents=True, exist_ok=True)
        self._setup_data(tmp_path)

        summary = main("2026-06-15", "2026-07-27")

        assert summary["metrics"]["n"] == 18
        assert summary["metrics"]["wins"] == 5
        assert summary["vfu22_validation_version"] == VFU_VERSION
        assert "VFU_22_PROSPECTIVE_VALIDATION_COMPLETE" in summary["classification_codes"]
        assert "NO_SUPABASE_WRITES" in summary["classification_codes"]

        out = tmp_path / "data" / "reports" / "vfu_22_summary.json"
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["metrics"]["n"] == 18

    def test_empty_period_returns_zero_n(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_prospective_validation as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        monkeypatch.setattr(module, "OUTPUT_SUMMARY",
                            tmp_path / "data" / "reports" / "vfu_22_summary.json")
        monkeypatch.setattr(module, "OUTPUT_BRIEF",
                            tmp_path / "data" / "reports" / "vfu_22_brief.md")
        (tmp_path / "data" / "reports").mkdir(parents=True, exist_ok=True)
        (tmp_path / "data" / "sigma_results").mkdir(parents=True, exist_ok=True)

        summary = main("2099-01-01", "2099-12-31")
        assert summary["metrics"]["n"] == 0
