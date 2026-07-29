"""
Tests for VFU-28: Markov State Engine Gap Audit
scripts/ops/vfu_markov_state_audit.py

Coverage:
  - _norm: lowercasing, special chars
  - load_markov_cards: reads jsonl, empty dir
  - load_sigma_index: reads sigma results, only June
  - analyse: per-state SR, join counts, root_cause, verdict
  - build_brief: header, state table, verdict
  - main(): no data case, writes outputs
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_markov_state_audit import (
    _norm,
    load_markov_cards,
    load_sigma_index,
    analyse,
    build_brief,
    main,
    VFU_VERSION,
    MIN_ROWS_PER_STATE,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_markov_file(tmp_path: Path, date_tag: str, rows: list[dict]) -> None:
    d = tmp_path / "data" / "markov"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"markov_state_card_{date_tag}.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def _make_sigma_file(tmp_path: Path, date_tag: str, rows: list[dict]) -> None:
    d = tmp_path / "data" / "sigma_results"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"sigma_results_{date_tag}.json").write_text(
        json.dumps({"rows": rows}), encoding="utf-8"
    )


def _mrow(race_id="100", horse="Dreamasar", state="CASH_RUN", conf="HIGH") -> dict:
    return {"race_id": race_id, "horse": horse, "state": state,
            "confidence": conf, "evidence": []}


def _srow(race_id="100", predicted="Dreamasar", outcome="WIN") -> dict:
    return {"race_id": race_id, "predicted": predicted, "outcome": outcome,
            "velo_prime_prob": 0.55, "assigned_product": "WIN_ONLY", "ew_outcome": None}


# ── _norm ────────────────────────────────────────────────────────────────────

class TestNorm:
    def test_lowercase(self):
        assert _norm("Dreamasar") == "dreamasar"

    def test_removes_aw(self):
        assert "aw" not in _norm("Course (AW)")

    def test_none(self):
        assert _norm(None) == ""


# ── load_markov_cards ─────────────────────────────────────────────────────────

class TestLoadMarkovCards:
    def test_loads_jsonl(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_markov_state_audit as mod
        monkeypatch.setattr(mod, "MARKOV_DIR", tmp_path / "data" / "markov")
        _make_markov_file(tmp_path, "2026_06_03", [_mrow("100"), _mrow("200")])
        rows = load_markov_cards(tmp_path / "data" / "markov")
        assert len(rows) == 2

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "data" / "markov"
        d.mkdir(parents=True, exist_ok=True)
        rows = load_markov_cards(d)
        assert rows == []


# ── load_sigma_index ──────────────────────────────────────────────────────────

class TestLoadSigmaIndex:
    def test_builds_index(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_markov_state_audit as mod
        monkeypatch.setattr(mod, "SIGMA_DIR", tmp_path / "data" / "sigma_results")
        _make_sigma_file(tmp_path, "2026_06_03", [_srow("100", "Dreamasar", "WIN")])
        idx = load_sigma_index(tmp_path / "data" / "sigma_results")
        assert ("100", "dreamasar") in idx
        assert idx[("100", "dreamasar")] == "WIN"

    def test_empty_sigma_dir(self, tmp_path):
        d = tmp_path / "data" / "sigma_results"
        d.mkdir(parents=True, exist_ok=True)
        idx = load_sigma_index(d)
        assert idx == {}


# ── analyse ───────────────────────────────────────────────────────────────────

class TestAnalyse:
    def test_per_state_sr_computed(self):
        # 2 CASH_RUN rows: 1 WIN, 1 MISS
        markov_rows = [_mrow("100", "Dreamasar", "CASH_RUN"), _mrow("200", "Lucky Star", "CASH_RUN")]
        sigma_idx = {
            ("100", "dreamasar"): "WIN",
            ("200", "lucky star"): "MISS",
        }
        r = analyse(markov_rows, sigma_idx)
        ps = {s["state"]: s for s in r["per_state_sr"]}
        assert ps["CASH_RUN"]["n"] == 2
        assert ps["CASH_RUN"]["wins"] == 1
        assert ps["CASH_RUN"]["sr"] == pytest.approx(0.5)

    def test_unknown_pct_computed(self):
        rows = [_mrow("100", "A", "UNKNOWN")] * 7 + [_mrow("200", "B", "CASH_RUN")] * 3
        sigma_idx = {}
        r = analyse(rows, sigma_idx)
        assert r["unknown_pct"] == pytest.approx(0.70)

    def test_gap_documented_verdict_with_data(self):
        # Use horse names without digits so _norm doesn't strip them
        names = ["alpha", "bravo", "charlie", "delta", "echo",
                 "foxtrot", "golf", "hotel", "india", "juliet",
                 "kilo", "lima", "mike", "nova", "oscar"]
        markov_rows = [_mrow(str(i), names[i].title(), "CASH_RUN") for i in range(15)]
        sigma_idx = {(str(i), names[i]): "WIN" for i in range(10)}
        r = analyse(markov_rows, sigma_idx)
        assert r["verdict"] == "MARKOV_GAP_DOCUMENTED"

    def test_insufficient_overlap_verdict(self):
        markov_rows = [_mrow("100", "Dreamasar", "CASH_RUN")]
        sigma_idx = {}  # no matches
        r = analyse(markov_rows, sigma_idx)
        assert r["verdict"] == "MARKOV_GAP_INSUFFICIENT_OVERLAP"

    def test_root_cause_present(self):
        r = analyse([_mrow()], {})
        assert len(r["root_cause"]) >= 3
        assert any("PASSPORT" in rc for rc in r["root_cause"])

    def test_classification_codes(self):
        r = analyse([_mrow()], {})
        assert "VFU_28_MARKOV_GAP_DIAGNOSTIC_COMPLETE" in r["classification_codes"]
        assert "REPORT_ONLY" in r["classification_codes"]

    def test_state_insufficient_data_label(self):
        # Only 1 row for CASH_RUN — less than MIN_ROWS_PER_STATE
        markov_rows = [_mrow("100", "Dreamasar", "CASH_RUN")]
        sigma_idx = {("100", "dreamasar"): "WIN"}
        r = analyse(markov_rows, sigma_idx)
        ps = {s["state"]: s for s in r["per_state_sr"]}
        assert ps["CASH_RUN"]["verdict"] == "INSUFFICIENT_DATA"

    def test_vfu_version_present(self):
        r = analyse([_mrow()], {})
        assert r["vfu28_validation_version"] == VFU_VERSION


# ── build_brief ───────────────────────────────────────────────────────────────

class TestBuildBrief:
    def _summary(self):
        return {
            "vfu28_validation_version": VFU_VERSION,
            "dates_with_markov_output": ["2026-06-03", "2026-06-04"],
            "total_runners_classified": 846,
            "state_distribution": {"UNKNOWN": 590, "SETUP_RUN": 251, "MARK_PROTECTION": 5},
            "confidence_distribution": {"LOW": 841, "MED": 5},
            "unknown_pct": 0.70,
            "high_conf_n": 0,
            "sigma_joined_n": 5,
            "sigma_unjoined_n": 841,
            "per_state_sr": [
                {"state": "UNKNOWN", "n": 0, "wins": 0, "sr": None, "verdict": "INSUFFICIENT_DATA"},
                {"state": "SETUP_RUN", "n": 5, "wins": 1, "sr": 0.20, "verdict": "INSUFFICIENT_DATA"},
            ],
            "root_cause": ["PASSPORT_COVERAGE_GAP: blah"],
            "verdict": "MARKOV_GAP_DOCUMENTED",
            "fade_signal_quality": "NOT_OPERATIONAL_INSUFFICIENT_PASSPORT_DATA",
            "recommendation": "Archive passport feeds.",
            "classification_codes": ["VFU_28_MARKOV_GAP_DIAGNOSTIC_COMPLETE", "REPORT_ONLY"],
        }

    def test_has_header(self):
        brief = build_brief(self._summary())
        assert "VFU-28" in brief

    def test_has_state_table(self):
        brief = build_brief(self._summary())
        assert "UNKNOWN" in brief
        assert "SETUP_RUN" in brief

    def test_has_verdict(self):
        brief = build_brief(self._summary())
        assert "MARKOV_GAP_DOCUMENTED" in brief


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:
    def test_no_markov_data_verdict(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_markov_state_audit as mod
        markov_dir = tmp_path / "data" / "markov"
        markov_dir.mkdir(parents=True, exist_ok=True)
        sigma_dir = tmp_path / "data" / "sigma_results"
        sigma_dir.mkdir(parents=True, exist_ok=True)
        out_json = tmp_path / "data" / "reports" / "vfu_28.json"
        out_md = tmp_path / "data" / "reports" / "vfu_28.md"
        monkeypatch.setattr(mod, "MARKOV_DIR", markov_dir)
        monkeypatch.setattr(mod, "SIGMA_DIR", sigma_dir)
        monkeypatch.setattr(mod, "OUTPUT_JSON", out_json)
        monkeypatch.setattr(mod, "OUTPUT_MD", out_md)
        (tmp_path / "data" / "reports").mkdir(parents=True)

        result = main(markov_dir=markov_dir, sigma_dir=sigma_dir)
        assert result["verdict"] == "NO_MARKOV_DATA"
        assert out_json.exists()
        assert out_md.exists()

    def test_with_data_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_markov_state_audit as mod
        markov_dir = tmp_path / "data" / "markov"
        sigma_dir = tmp_path / "data" / "sigma_results"
        out_json = tmp_path / "data" / "reports" / "vfu_28.json"
        out_md = tmp_path / "data" / "reports" / "vfu_28.md"
        monkeypatch.setattr(mod, "MARKOV_DIR", markov_dir)
        monkeypatch.setattr(mod, "SIGMA_DIR", sigma_dir)
        monkeypatch.setattr(mod, "OUTPUT_JSON", out_json)
        monkeypatch.setattr(mod, "OUTPUT_MD", out_md)
        (tmp_path / "data" / "reports").mkdir(parents=True)

        _make_markov_file(tmp_path, "2026_06_03", [_mrow("100", "Dreamasar", "UNKNOWN")])
        _make_sigma_file(tmp_path, "2026_06_03", [_srow("100", "Dreamasar", "WIN")])

        result = main(markov_dir=markov_dir, sigma_dir=sigma_dir)
        assert result["vfu28_validation_version"] == VFU_VERSION
        assert "VFU_28_MARKOV_GAP_DIAGNOSTIC_COMPLETE" in result["classification_codes"]
        assert out_json.exists()
        loaded = json.loads(out_json.read_text())
        assert loaded["total_runners_classified"] == 1
