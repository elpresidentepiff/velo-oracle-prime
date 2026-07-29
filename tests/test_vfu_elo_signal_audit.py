"""
Tests for VFU-27: Extended Elo Signal Audit
scripts/ops/vfu_elo_signal_audit.py

Coverage:
  - load_verdict_index: indexes by race_id, missing file, no top
  - load_sigma_rows: date filtering, inclusive endpoints, _date field
  - _fired: each sidecar threshold, None value
  - run_tournament: correct/incorrect/missed events, Elo changes, no verdict
  - analyse: verdict labels, baseline drift, fire rate, insufficient fires
  - build_brief: header, table, classifications
  - main(): writes outputs, correct structure
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_elo_signal_audit import (
    load_verdict_index,
    load_sigma_rows,
    _fired,
    run_tournament,
    analyse,
    build_brief,
    main,
    VFU_VERSION,
    SIDECARS,
    STARTING_ELO,
    K_CORRECT,
    K_INCORRECT,
    K_MISSED,
    MIN_FIRES_FOR_VERDICT,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_verdict_file(tmp_path: Path, date_tag: str, races: list[dict]) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / f"velo_prime_verdicts_{date_tag}.json").write_text(
        json.dumps(races), encoding="utf-8"
    )


def _make_sigma_file(tmp_path: Path, date_tag: str, rows: list[dict]) -> None:
    d = tmp_path / "data" / "sigma_results"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"sigma_results_{date_tag}.json").write_text(
        json.dumps({"date": date_tag.replace("_", "-"), "rows": rows}),
        encoding="utf-8",
    )


def _top(race_id="100", impr=0.50, mds=0.50, place_p=0.80, comment=0.30) -> dict:
    return {
        "race_id": race_id,
        "horse": "Dreamasar",
        "velo_prime_prob": 0.55,
        "improvement_score": impr,
        "market_deception_score": mds,
        "place_prob": place_p,
        "comment_intel_score": comment,
    }


def _sigma_row(race_id="100", outcome="WIN") -> dict:
    return {
        "race_id": race_id,
        "predicted": "Dreamasar",
        "outcome": outcome,
        "velo_prime_prob": 0.55,
        "assigned_product": "WIN_ONLY",
        "ew_outcome": None,
    }


# ── load_verdict_index ──────────────────────────────────────────────────────

class TestLoadVerdictIndex:
    def test_indexes_by_race_id(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_elo_signal_audit as mod
        monkeypatch.setattr(mod, "DATA", tmp_path / "data")
        _make_verdict_file(tmp_path, "2026_07_05", [{"top": _top("100")}])
        idx = load_verdict_index(tmp_path / "data")
        assert "100" in idx
        assert idx["100"]["improvement_score"] == 0.50

    def test_no_top_skipped(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_elo_signal_audit as mod
        monkeypatch.setattr(mod, "DATA", tmp_path / "data")
        _make_verdict_file(tmp_path, "2026_07_05", [{"top": None}, {"race_id": "200"}])
        idx = load_verdict_index(tmp_path / "data")
        assert len(idx) == 0

    def test_empty_data_dir(self, tmp_path):
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        idx = load_verdict_index(tmp_path / "data")
        assert idx == {}


# ── load_sigma_rows ─────────────────────────────────────────────────────────

class TestLoadSigmaRows:
    def test_date_filtering(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_elo_signal_audit as mod
        sigma_dir = tmp_path / "data" / "sigma_results"
        _make_sigma_file(tmp_path, "2026_07_01", [_sigma_row("1")])
        _make_sigma_file(tmp_path, "2026_07_10", [_sigma_row("2")])
        _make_sigma_file(tmp_path, "2026_07_20", [_sigma_row("3")])
        rows = load_sigma_rows("2026-07-01", "2026-07-10", sigma_dir)
        race_ids = [r["race_id"] for r in rows]
        assert "1" in race_ids
        assert "2" in race_ids
        assert "3" not in race_ids

    def test_inclusive_endpoints(self, tmp_path):
        sigma_dir = tmp_path / "data" / "sigma_results"
        _make_sigma_file(tmp_path, "2026_07_01", [_sigma_row("A")])
        _make_sigma_file(tmp_path, "2026_07_31", [_sigma_row("B")])
        rows = load_sigma_rows("2026-07-01", "2026-07-31", sigma_dir)
        ids = [r["race_id"] for r in rows]
        assert "A" in ids and "B" in ids

    def test_adds_date_field(self, tmp_path):
        sigma_dir = tmp_path / "data" / "sigma_results"
        _make_sigma_file(tmp_path, "2026_07_05", [_sigma_row("1")])
        rows = load_sigma_rows("2026-07-01", "2026-07-31", sigma_dir)
        assert rows[0]["_date"] == "2026-07-05"

    def test_empty_range(self, tmp_path):
        sigma_dir = tmp_path / "data" / "sigma_results"
        rows = load_sigma_rows("2099-01-01", "2099-12-31", sigma_dir)
        assert rows == []


# ── _fired ──────────────────────────────────────────────────────────────────

class TestFired:
    def test_improvement_above(self):
        assert _fired({"improvement_score": 0.31}, "improvement_score") is True

    def test_improvement_below(self):
        assert _fired({"improvement_score": 0.30}, "improvement_score") is False

    def test_mds_above(self):
        assert _fired({"market_deception_score": 0.35}, "market_deception_score") is True

    def test_place_prob_above(self):
        assert _fired({"place_prob": 0.51}, "place_prob") is True

    def test_comment_above(self):
        assert _fired({"comment_intel_score": 0.51}, "comment_intel_score") is True

    def test_none_value_returns_false(self):
        assert _fired({"improvement_score": None}, "improvement_score") is False

    def test_missing_field_returns_false(self):
        assert _fired({}, "improvement_score") is False


# ── run_tournament ───────────────────────────────────────────────────────────

class TestRunTournament:
    def _rows(self, outcomes_verdicts):
        """List of (outcome, impr, mds, place_p, comment) tuples."""
        rows = []
        for i, (outcome, impr, mds, place_p, comment) in enumerate(outcomes_verdicts):
            rows.append(_sigma_row(str(i), outcome))
            rows[-1]["_date"] = "2026-07-05"
        return rows

    def _idx(self, outcomes_verdicts):
        idx = {}
        for i, (_, impr, mds, place_p, comment) in enumerate(outcomes_verdicts):
            idx[str(i)] = _top(str(i), impr, mds, place_p, comment)
        return idx

    def test_correct_fire_adds_k(self):
        rows = [_sigma_row("0", "WIN")]
        rows[0]["_date"] = "2026-07-05"
        idx = {"0": _top("0", impr=0.50)}
        r = run_tournament(rows, idx)
        s = r["stats"]["improvement_score"]
        assert s["elo"] == STARTING_ELO + K_CORRECT
        assert s["n_correct"] == 1

    def test_incorrect_fire_subtracts_k(self):
        rows = [_sigma_row("0", "MISS")]
        rows[0]["_date"] = "2026-07-05"
        idx = {"0": _top("0", impr=0.50)}
        r = run_tournament(rows, idx)
        s = r["stats"]["improvement_score"]
        assert s["elo"] == STARTING_ELO + K_INCORRECT
        assert s["n_missed"] == 1

    def test_missed_winner_applies_k_missed(self):
        rows = [_sigma_row("0", "WIN")]
        rows[0]["_date"] = "2026-07-05"
        # improvement_score below threshold → no fire
        idx = {"0": _top("0", impr=0.10)}
        r = run_tournament(rows, idx)
        s = r["stats"]["improvement_score"]
        assert s["elo"] == STARTING_ELO + K_MISSED
        assert s["n_no_fire_win"] == 1

    def test_no_fire_miss_no_elo_change(self):
        rows = [_sigma_row("0", "MISS")]
        rows[0]["_date"] = "2026-07-05"
        idx = {"0": _top("0", impr=0.10)}
        r = run_tournament(rows, idx)
        s = r["stats"]["improvement_score"]
        assert s["elo"] == STARTING_ELO

    def test_no_verdict_counted(self):
        rows = [_sigma_row("999", "WIN")]
        rows[0]["_date"] = "2026-07-05"
        r = run_tournament(rows, {})
        assert r["n_no_verdict"] == 1
        assert r["n_enriched"] == 0

    def test_n_enriched_count(self):
        rows = [_sigma_row("0", "WIN"), _sigma_row("1", "MISS")]
        for row in rows: row["_date"] = "2026-07-05"
        idx = {"0": _top("0"), "1": _top("1")}
        r = run_tournament(rows, idx)
        assert r["n_enriched"] == 2


# ── analyse ──────────────────────────────────────────────────────────────────

class TestAnalyse:
    def _base_result(self, fires=25, correct=12):
        stats = {k: {"n_fired": 0, "n_correct": 0, "n_missed": 0, "n_no_fire_win": 0, "elo": STARTING_ELO}
                 for k in SIDECARS}
        stats["improvement_score"]["n_fired"] = fires
        stats["improvement_score"]["n_correct"] = correct
        stats["improvement_score"]["n_missed"] = fires - correct
        stats["improvement_score"]["elo"] = 1100
        return {"stats": stats, "n_rows": 100, "n_enriched": 100, "n_no_verdict": 0}

    def test_strong_verdict(self):
        r = analyse(self._base_result(fires=30, correct=15))
        impr = next(x for x in r["rankings"] if x["sidecar"] == "improvement_score")
        assert impr["verdict"] == "ELO_SIGNAL_STRONG"
        assert impr["strike_rate"] == pytest.approx(0.50)

    def test_moderate_verdict(self):
        r = analyse(self._base_result(fires=30, correct=11))
        impr = next(x for x in r["rankings"] if x["sidecar"] == "improvement_score")
        assert impr["verdict"] == "ELO_SIGNAL_MODERATE"

    def test_weak_verdict(self):
        r = analyse(self._base_result(fires=30, correct=5))
        impr = next(x for x in r["rankings"] if x["sidecar"] == "improvement_score")
        assert impr["verdict"] == "ELO_SIGNAL_WEAK"

    def test_insufficient_fires(self):
        r = analyse(self._base_result(fires=MIN_FIRES_FOR_VERDICT - 1, correct=5))
        impr = next(x for x in r["rankings"] if x["sidecar"] == "improvement_score")
        assert impr["verdict"] == "INSUFFICIENT_FIRES"

    def test_elo_drift_computed(self):
        r = analyse(self._base_result(fires=30, correct=15))
        impr = next(x for x in r["rankings"] if x["sidecar"] == "improvement_score")
        # baseline Elo for improvement_score is 848
        assert impr["elo_drift"] == 1100 - 848

    def test_rankings_sorted_by_elo(self):
        r = analyse(self._base_result(fires=25, correct=12))
        elos = [x["elo"] for x in r["rankings"]]
        assert elos == sorted(elos, reverse=True)

    def test_classification_codes(self):
        r = analyse(self._base_result())
        assert "VFU_27_ELO_SIGNAL_AUDIT_COMPLETE" in r["classification_codes"]
        assert "REPORT_ONLY" in r["classification_codes"]


# ── build_brief ──────────────────────────────────────────────────────────────

class TestBuildBrief:
    def test_has_header(self):
        r = analyse({"stats": {k: {"n_fired": 0, "n_correct": 0, "n_missed": 0, "n_no_fire_win": 0, "elo": STARTING_ELO} for k in SIDECARS},
                     "n_rows": 10, "n_enriched": 10, "n_no_verdict": 0})
        brief = build_brief(r)
        assert "VFU-27" in brief

    def test_has_sidecar_table(self):
        r = analyse({"stats": {k: {"n_fired": 0, "n_correct": 0, "n_missed": 0, "n_no_fire_win": 0, "elo": STARTING_ELO} for k in SIDECARS},
                     "n_rows": 10, "n_enriched": 10, "n_no_verdict": 0})
        brief = build_brief(r)
        assert "improvement_score" in brief
        assert "market_deception_score" in brief


# ── main() ──────────────────────────────────────────────────────────────────

class TestMain:
    def _setup(self, tmp_path: Path) -> None:
        _make_verdict_file(tmp_path, "2026_07_05",
                           [{"top": _top("100", impr=0.50, mds=0.50, place_p=0.80, comment=0.60)}])
        _make_sigma_file(tmp_path, "2026_07_05",
                         [_sigma_row("100", "WIN"), _sigma_row("200", "MISS")])

    def test_main_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_elo_signal_audit as mod
        data_dir = tmp_path / "data"
        sigma_dir = data_dir / "sigma_results"
        out_json = data_dir / "reports" / "vfu_27.json"
        out_md = data_dir / "reports" / "vfu_27.md"
        monkeypatch.setattr(mod, "OUTPUT_JSON", out_json)
        monkeypatch.setattr(mod, "OUTPUT_MD", out_md)
        (data_dir / "reports").mkdir(parents=True)
        self._setup(tmp_path)

        result = main("2026-07-01", "2026-07-31",
                      data_dir=data_dir, sigma_dir=sigma_dir)

        assert result["vfu27_validation_version"] == VFU_VERSION
        assert result["n_enriched"] == 1  # only race 100 matched verdict
        assert "VFU_27_ELO_SIGNAL_AUDIT_COMPLETE" in result["classification_codes"]
        assert out_json.exists()
        assert out_md.exists()
        loaded = json.loads(out_json.read_text())
        assert "rankings" in loaded

    def test_empty_data_returns_zero_enriched(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_elo_signal_audit as mod
        data_dir = tmp_path / "data"
        sigma_dir = data_dir / "sigma_results"
        out_json = data_dir / "reports" / "vfu_27.json"
        out_md = data_dir / "reports" / "vfu_27.md"
        monkeypatch.setattr(mod, "OUTPUT_JSON", out_json)
        monkeypatch.setattr(mod, "OUTPUT_MD", out_md)
        (data_dir / "reports").mkdir(parents=True)
        sigma_dir.mkdir(parents=True, exist_ok=True)

        result = main("2099-01-01", "2099-12-31",
                      data_dir=data_dir, sigma_dir=sigma_dir)
        assert result["n_enriched"] == 0
