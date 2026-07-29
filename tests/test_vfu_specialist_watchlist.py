"""
Tests for VFU-23: Specialist Watchlist Validation — scripts/ops/vfu_specialist_watchlist.py

Coverage:
  - normalize_name: strips, lowercases, apostrophe/hyphen handling
  - load_specialists: list-of-dicts format (matching VFU-17 output)
  - load_sigma_rows: attaches _date field, date-range filtering
  - evaluate_specialist: NO_PROSPECTIVE_APPEARANCES, INSUFFICIENT_DATA,
                         SPECIALIST_CONFIRMED, SPECIALIST_DEGRADED
  - build_brief: produces markdown with confirmed/degraded sections
  - main(): writes output files, returns summary dict
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_specialist_watchlist import (
    normalize_name,
    load_specialists,
    load_sigma_rows,
    evaluate_specialist,
    build_brief,
    main,
    HISTORICAL_PLACE_RATE_THRESHOLD,
    VFU_VERSION,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_sigma_file(tmp_path: Path, date_tag: str, rows: list[dict]) -> None:
    sigma_dir = tmp_path / "data" / "sigma_results"
    sigma_dir.mkdir(parents=True, exist_ok=True)
    (sigma_dir / f"sigma_results_{date_tag}.json").write_text(
        json.dumps({"date": date_tag.replace("_", "-"), "rows": rows}),
        encoding="utf-8",
    )


def _srow(predicted: str, outcome: str = "MISS", vp: float = 0.40):
    return {
        "race_id": "999",
        "course": "Cheltenham",
        "predicted": predicted,
        "outcome": outcome,
        "velo_prime_prob": vp,
        "assigned_product": "WIN_ONLY",
        "ew_outcome": None,
    }


def _make_specialist_file(tmp_path: Path, names: list[str]) -> Path:
    reports_dir = tmp_path / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "vfu_17_place_specialist_candidates.json"
    path.write_text(json.dumps([{"horse_name": n} for n in names]), encoding="utf-8")
    return path


# ------------------------------------------------------------------
# normalize_name
# ------------------------------------------------------------------

class TestNormalizeName:
    def test_lowercase_and_strip(self):
        assert normalize_name("  Canaria Queen  ") == "canaria queen"

    def test_apostrophe(self):
        assert normalize_name("Rider's Dream") == "riders dream"

    def test_hyphen(self):
        assert normalize_name("Galaxy-Wonder") == "galaxy wonder"

    def test_none_returns_empty(self):
        assert normalize_name(None) == ""


# ------------------------------------------------------------------
# load_specialists
# ------------------------------------------------------------------

class TestLoadSpecialists:
    def test_list_of_dicts(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_specialist_watchlist as module
        spec_path = _make_specialist_file(tmp_path, ["canaria queen", "galaxy wonder"])
        monkeypatch.setattr(module, "SPECIALIST_SOURCE", spec_path)
        result = load_specialists()
        assert len(result) == 2
        assert result[0]["horse_name"] == "canaria queen"

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_specialist_watchlist as module
        monkeypatch.setattr(module, "SPECIALIST_SOURCE", tmp_path / "nonexistent.json")
        assert load_specialists() == []


# ------------------------------------------------------------------
# load_sigma_rows (adds _date)
# ------------------------------------------------------------------

class TestLoadSigmaRowsSpecialist:
    def test_adds_date_field(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_specialist_watchlist as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        _make_sigma_file(tmp_path, "2026_07_05", [_srow("Canaria Queen", "WIN")])
        rows = load_sigma_rows("2026-06-15", "2026-07-27")
        assert len(rows) == 1
        assert rows[0]["_date"] == "2026-07-05"

    def test_date_filter_excludes_before_cutoff(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_specialist_watchlist as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        _make_sigma_file(tmp_path, "2026_06_10", [_srow("Horse A")])  # excluded
        _make_sigma_file(tmp_path, "2026_06_20", [_srow("Horse B")])  # included
        rows = load_sigma_rows("2026-06-15", "2026-07-27")
        assert len(rows) == 1
        assert rows[0]["predicted"] == "Horse B"


# ------------------------------------------------------------------
# evaluate_specialist
# ------------------------------------------------------------------

class TestEvaluateSpecialist:
    def test_no_appearances(self):
        result = evaluate_specialist("unknown horse", [_srow("other horse", "WIN")])
        assert result["verdict"] == "NO_PROSPECTIVE_APPEARANCES"
        assert result["prospective_n"] == 0

    def test_insufficient_data_one_appearance(self):
        rows = [_srow("Canaria Queen", "PLACED")]
        result = evaluate_specialist("Canaria Queen", rows)
        assert result["verdict"] == "INSUFFICIENT_DATA"
        assert result["prospective_n"] == 1

    def test_specialist_confirmed(self):
        # 3 out of 4 placed = 0.75 >= 0.667 threshold
        rows = [
            _srow("Canaria Queen", "PLACED"),
            _srow("Canaria Queen", "PLACED"),
            _srow("Canaria Queen", "PLACED"),
            _srow("Canaria Queen", "MISS"),
        ]
        result = evaluate_specialist("Canaria Queen", rows)
        assert result["verdict"] == "SPECIALIST_CONFIRMED"
        assert result["prospective_frame_rate"] == pytest.approx(0.75, abs=0.001)

    def test_specialist_confirmed_win_counts_as_frame(self):
        # 2 wins + 1 placed out of 4 = 75% frame rate → CONFIRMED. Also checks WIN counts as frame.
        rows = [
            _srow("Galaxy Wonder", "WIN"),
            _srow("Galaxy Wonder", "WIN"),
            _srow("Galaxy Wonder", "PLACED"),
            _srow("Galaxy Wonder", "MISS"),
        ]
        result = evaluate_specialist("Galaxy Wonder", rows)
        assert result["verdict"] == "SPECIALIST_CONFIRMED"
        assert result["prospective_wins"] == 2
        assert result["prospective_frames"] == 3

    def test_specialist_degraded(self):
        # 0 out of 3 placed = 0.0 < threshold
        rows = [_srow("Navy Light", "MISS")] * 3
        result = evaluate_specialist("Navy Light", rows)
        assert result["verdict"] == "SPECIALIST_DEGRADED"
        assert result["prospective_frame_rate"] == 0.0

    def test_name_matching_case_insensitive(self):
        rows = [_srow("CANARIA QUEEN", "WIN"), _srow("Canaria Queen", "PLACED")]
        result = evaluate_specialist("canaria queen", rows)
        assert result["prospective_n"] == 2

    def test_appearances_contain_date_course_outcome(self):
        import scripts.ops.vfu_specialist_watchlist as module
        rows = [{**_srow("Canaria Queen", "WIN"), "_date": "2026-07-05", "course": "Ayr"}]
        result = evaluate_specialist("Canaria Queen", rows)
        assert len(result["appearances"]) == 1
        assert result["appearances"][0]["date"] == "2026-07-05"
        assert result["appearances"][0]["course"] == "Ayr"
        assert result["appearances"][0]["outcome"] == "WIN"


# ------------------------------------------------------------------
# build_brief
# ------------------------------------------------------------------

class TestBuildBrief:
    def _summary(self):
        return {
            "cutoff": "2026-06-15",
            "through": "2026-07-27",
            "total_prospective_rows": 50,
            "total_specialist_appearances": 8,
            "results": [
                {"horse_name": "canaria queen", "prospective_n": 3, "prospective_wins": 0,
                 "prospective_frames": 2, "prospective_sr": 0.0, "prospective_frame_rate": 0.667,
                 "verdict": "SPECIALIST_CONFIRMED"},
                {"horse_name": "galaxy wonder", "prospective_n": 3, "prospective_wins": 0,
                 "prospective_frames": 0, "prospective_sr": 0.0, "prospective_frame_rate": 0.0,
                 "verdict": "SPECIALIST_DEGRADED"},
            ],
            "classification_codes": ["VFU_23_SPECIALIST_WATCHLIST_COMPLETE"],
        }

    def test_has_header(self):
        assert "VFU-23" in build_brief(self._summary())

    def test_confirmed_section_present(self):
        brief = build_brief(self._summary())
        assert "Confirmed Specialists" in brief
        assert "canaria queen" in brief

    def test_degraded_section_present(self):
        brief = build_brief(self._summary())
        assert "Degraded Specialists" in brief
        assert "galaxy wonder" in brief


# ------------------------------------------------------------------
# main() integration
# ------------------------------------------------------------------

class TestMain:
    def _setup(self, tmp_path: Path) -> None:
        _make_specialist_file(tmp_path, ["canaria queen", "galaxy wonder", "navy light"])
        _make_sigma_file(tmp_path, "2026_07_05", [
            # canaria queen: 3 placed out of 3 = 1.0 frame rate → CONFIRMED
            _srow("Canaria Queen", "PLACED"),
            _srow("Canaria Queen", "WIN"),
            _srow("Canaria Queen", "PLACED"),
            # navy light: 0 placed out of 3 = 0.0 → DEGRADED
            _srow("Navy Light",    "MISS"),
            _srow("Navy Light",    "MISS"),
            _srow("Navy Light",    "MISS"),
        ])

    def test_main_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_specialist_watchlist as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        monkeypatch.setattr(module, "SPECIALIST_SOURCE",
                            tmp_path / "data" / "reports" / "vfu_17_place_specialist_candidates.json")
        monkeypatch.setattr(module, "OUTPUT_SUMMARY",
                            tmp_path / "data" / "reports" / "vfu_23_summary.json")
        monkeypatch.setattr(module, "OUTPUT_BRIEF",
                            tmp_path / "data" / "reports" / "vfu_23_brief.md")
        (tmp_path / "data" / "reports").mkdir(parents=True, exist_ok=True)
        self._setup(tmp_path)

        summary = main("2026-06-15", "2026-07-27")

        assert summary["specialists_checked"] == 3
        assert summary["total_specialist_appearances"] == 6
        assert summary["vfu23_validation_version"] == VFU_VERSION
        assert "VFU_23_SPECIALIST_WATCHLIST_COMPLETE" in summary["classification_codes"]
        assert "NO_SUPABASE_WRITES" in summary["classification_codes"]

        # canaria queen: 2/3 frames = CONFIRMED
        # galaxy wonder: 0 appearances = NO_PROSPECTIVE_APPEARANCES
        # navy light: 0/3 frames = DEGRADED
        by_name = {r["horse_name"]: r for r in summary["results"]}
        assert by_name["canaria queen"]["verdict"] == "SPECIALIST_CONFIRMED"
        assert by_name["galaxy wonder"]["verdict"] == "NO_PROSPECTIVE_APPEARANCES"
        assert by_name["navy light"]["verdict"] == "SPECIALIST_DEGRADED"

        out = tmp_path / "data" / "reports" / "vfu_23_summary.json"
        assert out.exists()
