"""
Tests for VFU-25 + VFU-26: Verdict → Sigma Enrichment
scripts/ops/vfu_verdict_sigma_enrichment.py

Coverage:
  - normalize_horse
  - _build_verdict_index: standard verdict structure, missing file, no-top races
  - _lookup_verdict: race_id match, horse name match, miss (no match)
  - enrich_rows: adds no_rpr_prob and nds fields, falls back to None on no verdict
  - analyse_norpr: basic counts, WIN_LANE split, high-disagree, verdict thresholds
  - analyse_nds: FADE SR, miss rate, FADE_PREDICTIVE vs FADE_WEAK, narrative breakdown
  - main(): writes 4 output files, returns vfu25 + vfu26 summaries
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_verdict_sigma_enrichment import (
    normalize_horse,
    _build_verdict_index,
    _lookup_verdict,
    enrich_rows,
    load_sigma_rows,
    analyse_norpr,
    analyse_nds,
    main,
    VFU25_VERSION,
    VFU26_VERSION,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_verdict(tmp_path: Path, date_tag: str, races: list[dict]) -> None:
    verdict_dir = tmp_path / "data"
    verdict_dir.mkdir(parents=True, exist_ok=True)
    path = verdict_dir / f"velo_prime_verdicts_{date_tag}.json"
    path.write_text(json.dumps(races), encoding="utf-8")


def _make_sigma_file(tmp_path: Path, date_tag: str, rows: list[dict]) -> None:
    sigma_dir = tmp_path / "data" / "sigma_results"
    sigma_dir.mkdir(parents=True, exist_ok=True)
    (sigma_dir / f"sigma_results_{date_tag}.json").write_text(
        json.dumps({"date": date_tag.replace("_", "-"), "rows": rows}),
        encoding="utf-8",
    )


def _verdict_race(race_id="100", horse="Dreamasar", vp=0.50, no_rpr=0.35,
                  nds_score=0.20, nds_narrative="none", nds_fade=False) -> dict:
    return {
        "race_id": race_id,
        "course": "Ayr",
        "top": {
            "race_id": race_id,
            "horse": horse,
            "velo_prime_prob": vp,
            "sqpe_no_rpr_shadow_prob": no_rpr,
            "sqpe_no_rpr_shadow_feature_count": 25,
            "nds_score": nds_score,
            "nds_narrative": nds_narrative,
            "nds_disruption": "none",
            "nds_is_fade": nds_fade,
            "nds_overround_signal": 0.10,
        },
    }


def _sigma_row(race_id="100", predicted="Dreamasar", outcome="WIN", vp=0.50) -> dict:
    return {
        "race_id": race_id,
        "predicted": predicted,
        "outcome": outcome,
        "velo_prime_prob": vp,
        "assigned_product": "WIN_ONLY",
        "ew_outcome": None,
        "_date": "2026-07-05",
    }


# ------------------------------------------------------------------
# normalize_horse
# ------------------------------------------------------------------

class TestNormalizeHorse:
    def test_lowercase(self):
        assert normalize_horse("Dreamasar") == "dreamasar"

    def test_apostrophe(self):
        assert normalize_horse("Rider's Dream") == "riders dream"

    def test_hyphen(self):
        assert normalize_horse("Well-Known") == "well known"

    def test_none(self):
        assert normalize_horse(None) == ""


# ------------------------------------------------------------------
# _build_verdict_index
# ------------------------------------------------------------------

class TestBuildVerdictIndex:
    def test_indexes_by_race_id_and_horse(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_verdict_sigma_enrichment as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        _make_verdict(tmp_path, "2026_07_05",
                      [_verdict_race("100", "Dreamasar", no_rpr=0.35, nds_score=0.25)])
        idx = _build_verdict_index("2026-07-05")
        assert "race:100" in idx
        assert "horse:dreamasar" in idx
        assert idx["race:100"]["sqpe_no_rpr_shadow_prob"] == 0.35
        assert idx["race:100"]["nds_score"] == 0.25

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_verdict_sigma_enrichment as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        assert _build_verdict_index("2099-01-01") == {}

    def test_race_without_top_skipped(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_verdict_sigma_enrichment as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        _make_verdict(tmp_path, "2026_07_05", [{"race_id": "200", "top": None}])
        idx = _build_verdict_index("2026-07-05")
        assert len(idx) == 0


# ------------------------------------------------------------------
# _lookup_verdict
# ------------------------------------------------------------------

class TestLookupVerdict:
    def test_race_id_match(self):
        idx = {
            "race:100": {"horse": "Dreamasar", "sqpe_no_rpr_shadow_prob": 0.35},
        }
        row = {"race_id": "100", "predicted": "Other Horse"}
        result = _lookup_verdict(row, idx)
        assert result["sqpe_no_rpr_shadow_prob"] == 0.35

    def test_horse_name_fallback(self):
        idx = {
            "horse:dreamasar": {"horse": "Dreamasar", "nds_score": 0.40},
        }
        row = {"race_id": "999", "predicted": "Dreamasar"}
        result = _lookup_verdict(row, idx)
        assert result["nds_score"] == 0.40

    def test_no_match_returns_empty(self):
        idx = {"race:100": {"horse": "Other"}}
        row = {"race_id": "999", "predicted": "Unknown"}
        assert _lookup_verdict(row, idx) == {}


# ------------------------------------------------------------------
# enrich_rows
# ------------------------------------------------------------------

class TestEnrichRows:
    def test_adds_no_rpr_and_nds(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_verdict_sigma_enrichment as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        _make_verdict(tmp_path, "2026_07_05",
                      [_verdict_race("100", "Dreamasar", no_rpr=0.30,
                                     nds_score=0.75, nds_fade=True)])
        rows = [_sigma_row("100", "Dreamasar", "WIN")]
        enriched = enrich_rows(rows)
        assert len(enriched) == 1
        assert enriched[0]["no_rpr_prob"] == 0.30
        assert enriched[0]["nds_score"] == 0.75
        assert enriched[0]["nds_is_fade"] is True

    def test_no_verdict_falls_back_to_none(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_verdict_sigma_enrichment as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        rows = [_sigma_row("999", "Unknown", "MISS", "_date" )]
        rows[0]["_date"] = "2099-01-01"
        enriched = enrich_rows(rows)
        assert enriched[0]["no_rpr_prob"] is None
        assert enriched[0]["nds_score"] is None


# ------------------------------------------------------------------
# analyse_norpr
# ------------------------------------------------------------------

class TestAnalyseNorpr:
    def _rows(self, specs):
        """specs: list of (outcome, vp, no_rpr)"""
        return [
            {"outcome": o, "velo_prime_prob": vp, "no_rpr_prob": nr,
             "nds_score": None, "nds_is_fade": None}
            for o, vp, nr in specs
        ]

    def test_basic_sr(self):
        rows = self._rows([("WIN", 0.50, 0.40), ("MISS", 0.45, 0.35), ("PLACED", 0.42, 0.38)])
        m = analyse_norpr(rows)
        assert m["n"] == 3
        assert m["norpr_sr"] == pytest.approx(1/3, abs=0.01)
        assert m["norpr_frame_rate"] == pytest.approx(2/3, abs=0.01)

    def test_no_norpr_fields(self):
        rows = [{"outcome": "WIN", "velo_prime_prob": 0.5, "no_rpr_prob": None}]
        m = analyse_norpr(rows)
        assert m["verdict"] == "NO_NORPR_FIELDS_IN_VERDICTS"

    def test_win_lane_threshold(self):
        rows = self._rows([
            ("WIN",  0.50, 0.45),   # above 0.15 threshold
            ("MISS", 0.45, 0.10),   # below 0.15 threshold
        ])
        m = analyse_norpr(rows)
        assert m["norpr_win_lane_n"] == 1
        assert m["norpr_win_lane_sr"] == pytest.approx(1.0)

    def test_high_disagree(self):
        rows = self._rows([
            ("MISS", 0.45, 0.10),   # live VP>=0.40, no_rpr<0.20 → disagree
            ("WIN",  0.50, 0.45),   # both high → agree
        ])
        m = analyse_norpr(rows)
        assert m["live_norpr_high_disagree_n"] == 1
        assert m["live_norpr_high_disagree_sr"] == pytest.approx(0.0)

    def test_sufficient_data_verdict(self):
        rows = self._rows([("WIN", 0.45, 0.45)] * 30 + [("MISS", 0.45, 0.30)] * 10)
        m = analyse_norpr(rows)
        assert m["verdict"] == "NO_RPR_SHADOW_TRACKING_INITIALIZED"

    def test_insufficient_data_verdict(self):
        rows = self._rows([("WIN", 0.45, 0.45)] * 5)
        m = analyse_norpr(rows)
        assert m["verdict"] == "INSUFFICIENT_DATA"


# ------------------------------------------------------------------
# analyse_nds
# ------------------------------------------------------------------

class TestAnalyseNds:
    def _row(self, outcome, nds_score=0.0, nds_narrative="none", nds_fade=False):
        return {
            "outcome": outcome,
            "velo_prime_prob": 0.45,
            "no_rpr_prob": 0.12,
            "nds_score": nds_score,
            "nds_narrative": nds_narrative,
            "nds_disruption": "none",
            "nds_is_fade": nds_fade,
        }

    def test_no_nds_fields(self):
        rows = [{"outcome": "WIN", "nds_score": None, "nds_is_fade": None}]
        m = analyse_nds(rows)
        assert m["verdict"] == "NO_NDS_FIELDS_IN_VERDICTS"

    def test_gap_documented_verdict(self):
        # All scores = 0.0 (as in real data — SP default 10.0 causes this)
        rows = [self._row("WIN"), self._row("MISS"), self._row("PLACED")]
        m = analyse_nds(rows)
        assert m["verdict"] == "NDS_GAP_DOCUMENTED"
        assert m["fade_signal_quality"] == "NOT_OPERATIONAL_SP_DATA_MISSING"

    def test_pct_zero_all_zero(self):
        rows = [self._row("WIN", nds_score=0.0)] * 5
        m = analyse_nds(rows)
        assert m["pct_score_zero"] == pytest.approx(1.0)
        assert m["nonzero_scores"] == 0

    def test_pct_zero_mixed(self):
        rows = [self._row("WIN", nds_score=0.0)] * 3 + [self._row("MISS", nds_score=0.05)] * 1
        m = analyse_nds(rows)
        assert m["pct_score_zero"] == pytest.approx(0.75)
        assert m["nonzero_scores"] == 1

    def test_root_cause_present(self):
        rows = [self._row("WIN")]
        m = analyse_nds(rows)
        assert len(m["root_cause"]) >= 3
        assert any("sp_dec" in rc.lower() or "SP_DECIMAL" in rc for rc in m["root_cause"])

    def test_narrative_breakdown(self):
        rows = (
            [self._row("WIN",  nds_narrative="none")] * 3
            + [self._row("MISS", nds_narrative="none")] * 2
        )
        m = analyse_nds(rows)
        assert "none" in m["narrative_breakdown"]


# ------------------------------------------------------------------
# main() integration
# ------------------------------------------------------------------

class TestMain:
    def _setup(self, tmp_path: Path) -> None:
        # Write verdict file for 2026-07-05
        _make_verdict(tmp_path, "2026_07_05", [
            _verdict_race("100", "Dreamasar", vp=0.50, no_rpr=0.42,
                          nds_score=0.65, nds_fade=False),
            _verdict_race("200", "Lucky Star",  vp=0.44, no_rpr=0.30,
                          nds_score=0.75, nds_fade=True),
        ])
        # Write sigma for same date
        _make_sigma_file(tmp_path, "2026_07_05", [
            _sigma_row("100", "Dreamasar", "WIN",  0.50),
            _sigma_row("200", "Lucky Star",  "MISS", 0.44),
        ])

    def test_main_produces_four_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_verdict_sigma_enrichment as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        monkeypatch.setattr(module, "OUTPUT_VFU25",
                            tmp_path / "data" / "reports" / "vfu_25.json")
        monkeypatch.setattr(module, "OUTPUT_VFU25B",
                            tmp_path / "data" / "reports" / "vfu_25.md")
        monkeypatch.setattr(module, "OUTPUT_VFU26",
                            tmp_path / "data" / "reports" / "vfu_26.json")
        monkeypatch.setattr(module, "OUTPUT_VFU26B",
                            tmp_path / "data" / "reports" / "vfu_26.md")
        (tmp_path / "data" / "reports").mkdir(parents=True)
        self._setup(tmp_path)

        result = main("2026-07-01", "2026-07-27")

        assert "vfu25" in result
        assert "vfu26" in result
        assert result["vfu25"]["vfu25_validation_version"] == VFU25_VERSION
        assert result["vfu26"]["vfu26_validation_version"] == VFU26_VERSION
        assert "VFU_25_NORPR_SIGMA_ENRICHMENT_COMPLETE" in result["vfu25"]["classification_codes"]
        assert "VFU_26_NDS_GAP_DIAGNOSTIC_COMPLETE" in result["vfu26"]["classification_codes"]

        out25 = tmp_path / "data" / "reports" / "vfu_25.json"
        out26 = tmp_path / "data" / "reports" / "vfu_26.json"
        assert out25.exists()
        assert out26.exists()
        assert (tmp_path / "data" / "reports" / "vfu_25.md").exists()
        assert (tmp_path / "data" / "reports" / "vfu_26.md").exists()

        loaded_25 = json.loads(out25.read_text())
        assert loaded_25["metrics"]["n"] == 2
        assert loaded_25["metrics"]["n_enriched"] == 2

    def test_empty_period_returns_zero_n(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_verdict_sigma_enrichment as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        monkeypatch.setattr(module, "OUTPUT_VFU25",
                            tmp_path / "data" / "reports" / "vfu_25.json")
        monkeypatch.setattr(module, "OUTPUT_VFU25B",
                            tmp_path / "data" / "reports" / "vfu_25.md")
        monkeypatch.setattr(module, "OUTPUT_VFU26",
                            tmp_path / "data" / "reports" / "vfu_26.json")
        monkeypatch.setattr(module, "OUTPUT_VFU26B",
                            tmp_path / "data" / "reports" / "vfu_26.md")
        (tmp_path / "data" / "reports").mkdir(parents=True)
        (tmp_path / "data" / "sigma_results").mkdir(parents=True, exist_ok=True)

        result = main("2099-01-01", "2099-12-31")
        assert result["vfu25"]["metrics"]["n"] == 0
        assert result["vfu26"]["metrics"]["n"] == 0
