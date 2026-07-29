"""
Tests for VFU-29: Intelligence Layer Retrospective
scripts/ops/vfu_intelligence_layer_audit.py

Coverage:
  - _rag_label: STRONG/SOLID/MARGINAL VP thresholds
  - load_verdict_index: indexes by race_id, skips no-top
  - load_sigma_rows: date filtering, _date field
  - analyse_rag: label counts, SR, lift, verdict labels, RAG signal
  - analyse_latent_gap / analyse_graph_gap: file counts, verdict, root_cause
  - build_brief: headers and tables
  - main(): outputs, correct structure
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_intelligence_layer_audit import (
    _rag_label,
    load_verdict_index,
    load_sigma_rows,
    analyse_rag,
    analyse_latent_gap,
    analyse_graph_gap,
    build_summary,
    build_brief,
    main,
    VFU_VERSION,
    VP_STRONG,
    VP_SOLID,
    RAG_LABELS,
    MIN_LABEL_N,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_verdict_file(tmp_path: Path, date_tag: str, races: list[dict]) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / f"velo_prime_verdicts_{date_tag}.json").write_text(
        json.dumps(races), encoding="utf-8"
    )


def _make_sigma_file(tmp_path: Path, date_tag: str, rows: list[dict]) -> None:
    d = tmp_path / "data" / "sigma_results"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"sigma_results_{date_tag}.json").write_text(
        json.dumps({"rows": rows}), encoding="utf-8"
    )


def _make_latent_file(tmp_path: Path, date_tag: str) -> None:
    d = tmp_path / "data" / "latent"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"latent_concepts_{date_tag}.jsonl").write_text("", encoding="utf-8")


def _make_graph_file(tmp_path: Path, date_tag: str) -> None:
    d = tmp_path / "data" / "graph"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"race_graph_{date_tag}.json").write_text("{}", encoding="utf-8")


def _top(race_id="100", vp=0.65, mds=0.40, impr=0.35, place_p=0.80) -> dict:
    return {
        "race_id": race_id,
        "horse": "Dreamasar",
        "velo_prime_prob": vp,
        "market_deception_score": mds,
        "improvement_score": impr,
        "place_prob": place_p,
    }


def _srow(race_id="100", outcome="WIN") -> dict:
    return {
        "race_id": race_id,
        "predicted": "Dreamasar",
        "outcome": outcome,
        "velo_prime_prob": 0.55,
        "assigned_product": "WIN_ONLY",
        "ew_outcome": None,
    }


# ── _rag_label ────────────────────────────────────────────────────────────────

class TestRagLabel:
    def test_strong(self):
        assert _rag_label(VP_STRONG + 0.01, 0.5, 0.4, 0.9) == "STRONG"

    def test_solid(self):
        assert _rag_label(VP_SOLID + 0.01, 0.3, 0.2, 0.6) == "SOLID"

    def test_marginal(self):
        assert _rag_label(VP_SOLID - 0.01, 0.1, 0.1, 0.3) == "MARGINAL"

    def test_boundary_solid(self):
        # Exactly at SOLID threshold goes to MARGINAL (not >)
        assert _rag_label(VP_SOLID, 0.0, 0.0, 0.0) == "MARGINAL"

    def test_boundary_strong(self):
        # Exactly at STRONG threshold goes to SOLID
        assert _rag_label(VP_STRONG, 0.0, 0.0, 0.0) == "SOLID"


# ── load_verdict_index ────────────────────────────────────────────────────────

class TestLoadVerdictIndex:
    def test_basic(self, tmp_path):
        _make_verdict_file(tmp_path, "2026_07_05", [{"top": _top("100")}])
        idx = load_verdict_index(tmp_path / "data")
        assert "100" in idx

    def test_skips_no_top(self, tmp_path):
        _make_verdict_file(tmp_path, "2026_07_05", [{"top": None}])
        idx = load_verdict_index(tmp_path / "data")
        assert len(idx) == 0

    def test_empty_dir(self, tmp_path):
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        assert load_verdict_index(tmp_path / "data") == {}


# ── load_sigma_rows ───────────────────────────────────────────────────────────

class TestLoadSigmaRows:
    def test_date_filtering(self, tmp_path):
        sigma_dir = tmp_path / "data" / "sigma_results"
        _make_sigma_file(tmp_path, "2026_07_01", [_srow("1")])
        _make_sigma_file(tmp_path, "2026_07_20", [_srow("2")])
        rows = load_sigma_rows("2026-07-01", "2026-07-10", sigma_dir)
        assert len(rows) == 1
        assert rows[0]["race_id"] == "1"

    def test_adds_date(self, tmp_path):
        sigma_dir = tmp_path / "data" / "sigma_results"
        _make_sigma_file(tmp_path, "2026_07_05", [_srow("1")])
        rows = load_sigma_rows("2026-07-01", "2026-07-31", sigma_dir)
        assert rows[0]["_date"] == "2026-07-05"


# ── analyse_rag ───────────────────────────────────────────────────────────────

class TestAnalyseRag:
    def _make_rows_and_idx(self, specs):
        """specs: list of (vp, outcome)"""
        rows, idx = [], {}
        for i, (vp, outcome) in enumerate(specs):
            rid = str(i)
            rows.append({**_srow(rid, outcome), "_date": "2026-07-05"})
            idx[rid] = _top(rid, vp=vp)
        return rows, idx

    def test_label_counts(self):
        specs = [(0.65, "WIN"), (0.50, "MISS"), (0.30, "MISS")]
        rows, idx = self._make_rows_and_idx(specs)
        r = analyse_rag(rows, idx)
        strong = next(x for x in r["label_rows"] if x["label"] == "STRONG")
        solid  = next(x for x in r["label_rows"] if x["label"] == "SOLID")
        marginal = next(x for x in r["label_rows"] if x["label"] == "MARGINAL")
        assert strong["n"] == 1
        assert solid["n"] == 1
        assert marginal["n"] == 1

    def test_sr_computed(self):
        specs = [(0.65, "WIN"), (0.65, "WIN"), (0.65, "MISS")]
        rows, idx = self._make_rows_and_idx(specs)
        r = analyse_rag(rows, idx)
        strong = next(x for x in r["label_rows"] if x["label"] == "STRONG")
        assert strong["strike_rate"] == pytest.approx(2/3, abs=0.01)

    def test_no_verdict_counted(self):
        rows = [{**_srow("999", "WIN"), "_date": "2026-07-05"}]
        r = analyse_rag(rows, {})
        assert r["n_no_verdict"] == 1
        assert r["n_enriched"] == 0

    def test_predictive_verdict(self):
        # Many STRONG wins well above baseline
        strong_specs = [(0.65, "WIN")] * 25 + [(0.65, "MISS")] * 5
        marginal_specs = [(0.30, "MISS")] * 30
        all_specs = strong_specs + marginal_specs
        rows, idx = self._make_rows_and_idx(all_specs)
        r = analyse_rag(rows, idx)
        strong = next(x for x in r["label_rows"] if x["label"] == "STRONG")
        assert strong["verdict"] == "RAG_LABEL_PREDICTIVE"
        assert r["rag_signal"] == "RAG_LABEL_DISCRIMINATES"

    def test_insufficient_data_verdict(self):
        specs = [(0.65, "WIN")] * (MIN_LABEL_N - 1)
        rows, idx = self._make_rows_and_idx(specs)
        r = analyse_rag(rows, idx)
        strong = next(x for x in r["label_rows"] if x["label"] == "STRONG")
        assert strong["verdict"] == "INSUFFICIENT_DATA"

    def test_lift_computed(self):
        specs = [(0.65, "WIN")] * 25 + [(0.30, "WIN")] * 5 + [(0.30, "MISS")] * 20
        rows, idx = self._make_rows_and_idx(specs)
        r = analyse_rag(rows, idx)
        strong = next(x for x in r["label_rows"] if x["label"] == "STRONG")
        assert strong["vs_baseline"] is not None
        assert strong["vs_baseline"] > 1.0


# ── analyse_latent_gap / analyse_graph_gap ────────────────────────────────────

class TestGapDiagnostics:
    def test_latent_no_files(self, tmp_path):
        d = tmp_path / "data" / "latent"
        d.mkdir(parents=True, exist_ok=True)
        r = analyse_latent_gap(d)
        assert r["n_output_dates"] == 0
        assert r["verdict"] == "LATENT_GAP_DOCUMENTED"
        assert len(r["root_cause"]) >= 2

    def test_latent_with_files(self, tmp_path):
        _make_latent_file(tmp_path, "2026_06_03")
        _make_latent_file(tmp_path, "2026_06_04")
        r = analyse_latent_gap(tmp_path / "data" / "latent")
        assert r["n_output_dates"] == 2

    def test_graph_no_files(self, tmp_path):
        d = tmp_path / "data" / "graph"
        d.mkdir(parents=True, exist_ok=True)
        r = analyse_graph_gap(d)
        assert r["n_output_dates"] == 0
        assert r["verdict"] == "GRAPH_GAP_DOCUMENTED"

    def test_graph_with_files(self, tmp_path):
        _make_graph_file(tmp_path, "2026_06_03")
        r = analyse_graph_gap(tmp_path / "data" / "graph")
        assert r["n_output_dates"] == 1

    def test_classification_codes_in_summary(self):
        rag = {"n_sigma_rows": 10, "n_enriched": 8, "n_no_verdict": 2,
               "baseline_sr": 0.30, "label_rows": [], "top_label": None,
               "top_label_sr": None, "rag_signal": "RAG_LABEL_WEAK"}
        lat = {"n_output_dates": 0, "output_dates": [], "verdict": "LATENT_GAP_DOCUMENTED",
               "fade_signal_quality": "NOT_OPERATIONAL", "root_cause": ["X"]}
        gr  = {"n_output_dates": 0, "output_dates": [], "verdict": "GRAPH_GAP_DOCUMENTED",
               "fade_signal_quality": "NOT_OPERATIONAL", "root_cause": ["X"]}
        s = build_summary(rag, lat, gr)
        assert "VFU_29_INTELLIGENCE_LAYER_AUDIT_COMPLETE" in s["classification_codes"]
        assert "REPORT_ONLY" in s["classification_codes"]
        assert s["vfu29_validation_version"] == VFU_VERSION


# ── build_brief ────────────────────────────────────────────────────────────────

class TestBuildBrief:
    def _minimal_summary(self):
        rag = {"n_sigma_rows": 100, "n_enriched": 90, "n_no_verdict": 10,
               "baseline_sr": 0.30,
               "label_rows": [{"label": "STRONG", "n": 30, "wins": 12, "placed": 18,
                                "strike_rate": 0.40, "frame_rate": 0.60,
                                "vs_baseline": 1.33, "verdict": "RAG_LABEL_PREDICTIVE"}],
               "top_label": "STRONG", "top_label_sr": 0.40,
               "rag_signal": "RAG_LABEL_DISCRIMINATES"}
        lat = {"n_output_dates": 2, "output_dates": ["2026-06-03", "2026-06-04"],
               "verdict": "LATENT_GAP_DOCUMENTED",
               "fade_signal_quality": "NOT_OPERATIONAL",
               "root_cause": ["PASSPORT_FEED_EPHEMERAL"]}
        gr  = {"n_output_dates": 2, "output_dates": ["2026-06-03", "2026-06-04"],
               "verdict": "GRAPH_GAP_DOCUMENTED",
               "fade_signal_quality": "NOT_OPERATIONAL",
               "root_cause": ["PASSPORT_FEED_EPHEMERAL"]}
        return build_summary(rag, lat, gr)

    def test_has_header(self):
        brief = build_brief(self._minimal_summary())
        assert "VFU-29" in brief

    def test_has_rag_table(self):
        brief = build_brief(self._minimal_summary())
        assert "STRONG" in brief
        assert "RAG_LABEL_PREDICTIVE" in brief

    def test_has_latent_section(self):
        brief = build_brief(self._minimal_summary())
        assert "Latent Tagger Gap" in brief

    def test_has_graph_section(self):
        brief = build_brief(self._minimal_summary())
        assert "Graph Gap" in brief


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:
    def _setup(self, tmp_path: Path) -> None:
        _make_verdict_file(tmp_path, "2026_07_05",
                           [{"top": _top("100", vp=0.65)},
                            {"top": _top("200", vp=0.45)},
                            {"top": _top("300", vp=0.30)}])
        _make_sigma_file(tmp_path, "2026_07_05", [
            _srow("100", "WIN"),
            _srow("200", "MISS"),
            _srow("300", "MISS"),
        ])
        _make_latent_file(tmp_path, "2026_06_03")
        _make_graph_file(tmp_path, "2026_06_03")

    def test_main_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_intelligence_layer_audit as mod
        data_dir   = tmp_path / "data"
        sigma_dir  = data_dir / "sigma_results"
        latent_dir = data_dir / "latent"
        graph_dir  = data_dir / "graph"
        out_json   = data_dir / "reports" / "vfu_29.json"
        out_md     = data_dir / "reports" / "vfu_29.md"
        monkeypatch.setattr(mod, "OUTPUT_JSON", out_json)
        monkeypatch.setattr(mod, "OUTPUT_MD",   out_md)
        (data_dir / "reports").mkdir(parents=True)
        self._setup(tmp_path)

        result = main("2026-07-01", "2026-07-31",
                      data_dir=data_dir, sigma_dir=sigma_dir,
                      latent_dir=latent_dir, graph_dir=graph_dir)

        assert result["vfu29_validation_version"] == VFU_VERSION
        assert "VFU_29_INTELLIGENCE_LAYER_AUDIT_COMPLETE" in result["classification_codes"]
        assert result["rag_verdict_audit"]["n_enriched"] == 3
        assert result["latent_gap"]["n_output_dates"] == 1
        assert result["graph_gap"]["n_output_dates"] == 1
        assert out_json.exists()
        assert out_md.exists()

    def test_empty_data_zero_enriched(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_intelligence_layer_audit as mod
        data_dir  = tmp_path / "data"
        sigma_dir = data_dir / "sigma_results"
        out_json  = data_dir / "reports" / "vfu_29.json"
        out_md    = data_dir / "reports" / "vfu_29.md"
        monkeypatch.setattr(mod, "OUTPUT_JSON", out_json)
        monkeypatch.setattr(mod, "OUTPUT_MD",   out_md)
        (data_dir / "reports").mkdir(parents=True)
        sigma_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "latent").mkdir(parents=True, exist_ok=True)
        (data_dir / "graph").mkdir(parents=True, exist_ok=True)

        result = main("2099-01-01", "2099-12-31",
                      data_dir=data_dir, sigma_dir=sigma_dir,
                      latent_dir=data_dir / "latent",
                      graph_dir=data_dir / "graph")
        assert result["rag_verdict_audit"]["n_enriched"] == 0
