"""
Tests for VFU-24: SQPE v18 Formal Decision — scripts/ops/vfu_sqpe_v18_decision.py

Coverage:
  - load_metadata: returns empty dict for missing file, correct for real file
  - build_decision: correct delta calculations, NO_PROMOTION verdict
  - build_decision: cross_holdout_note present
  - build_decision: all classification codes present
  - build_brief: produces markdown with expected sections
  - main(): writes output files, returns correct decision
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_sqpe_v18_decision import (
    load_metadata,
    build_decision,
    build_brief,
    main,
    VFU_VERSION,
)


def _v17() -> dict:
    return {
        "version": "v17.1",
        "auc": 0.9296,
        "top1_accuracy": 0.7197,
        "mrr": 0.8344,
        "train_rows": 1535890,
        "test_rows": 79742,
        "promoted_at": "2026-06-19T07:59:16",
    }


def _v18() -> dict:
    return {
        "version": "v18.0",
        "trained_at": "2026-04-05T16:55:56",
        "train_rows": 1374559,
        "test_rows": 241073,
        "auc_v18": 0.9372,
        "auc_v17_baseline": 0.9375,
        "log_loss_v18": 0.1834,
        "top1_v18": 0.7367,
        "top1_v17_baseline": 0.7379,
        "mrr_v18": 0.8486,
        "mrr_v17_baseline": 0.8493,
        "v18_new_features": ["days_since_run", "class_delta"],
        "new_feature_importances": {
            "class_delta": 0.0005,
            "days_since_run": 0.0005,
        },
        "verdict": "NO LIFT",
    }


class TestLoadMetadata:
    def test_missing_file_returns_empty(self, tmp_path):
        result = load_metadata(tmp_path / "nonexistent.json")
        assert result == {}

    def test_valid_file_returns_content(self, tmp_path):
        f = tmp_path / "meta.json"
        f.write_text(json.dumps({"version": "v18.0", "auc_v18": 0.9372}), encoding="utf-8")
        result = load_metadata(f)
        assert result["version"] == "v18.0"
        assert result["auc_v18"] == 0.9372


class TestBuildDecision:
    def test_decision_is_no_promotion(self):
        d = build_decision(_v17(), _v18())
        assert d["decision"] == "NO_PROMOTION"

    def test_auc_delta_is_negative(self):
        d = build_decision(_v17(), _v18())
        delta = d["v18"]["v18_own_auc_delta"]
        assert delta < 0

    def test_top1_delta_is_negative(self):
        d = build_decision(_v17(), _v18())
        delta = d["v18"]["v18_own_top1_delta"]
        assert delta < 0

    def test_new_feature_importances_near_zero(self):
        d = build_decision(_v17(), _v18())
        fi = d["v18"]["new_feature_importances"]
        assert fi["class_delta"] < 0.001
        assert fi["days_since_run"] < 0.001

    def test_cross_holdout_note_present(self):
        d = build_decision(_v17(), _v18())
        assert "cross_holdout" in d["cross_holdout_note"].lower() or len(d["cross_holdout_note"]) > 20

    def test_classification_codes_present(self):
        d = build_decision(_v17(), _v18())
        codes = d["classification_codes"]
        assert "SQPE_V18_NO_PROMOTION" in codes
        assert "SQPE_V17_1_REMAINS_LIVE" in codes
        assert "NO_LIVE_SCORING_CHANGE" in codes
        assert "NO_SUPABASE_WRITES" in codes
        assert "REPORT_ONLY" in codes

    def test_vfu_version_present(self):
        d = build_decision(_v17(), _v18())
        assert d["vfu24_validation_version"] == VFU_VERSION

    def test_promotion_blocked_reasons_non_empty(self):
        d = build_decision(_v17(), _v18())
        assert len(d["promotion_blocked_reasons"]) >= 3

    def test_empty_metadata_handled(self):
        d = build_decision({}, {})
        assert d["decision"] == "NO_PROMOTION"
        assert d["v17_1"]["auc"] is None

    def test_delta_precision(self):
        d = build_decision(_v17(), _v18())
        # 0.9372 - 0.9375 = -0.0003
        assert d["v18"]["v18_own_auc_delta"] == pytest.approx(-0.0003, abs=0.0001)


class TestBuildBrief:
    def test_has_header(self):
        d = build_decision(_v17(), _v18())
        brief = build_brief(d)
        assert "VFU-24" in brief

    def test_has_no_promotion_verdict(self):
        d = build_decision(_v17(), _v18())
        brief = build_brief(d)
        assert "NO_PROMOTION" in brief

    def test_has_feature_importance_table(self):
        d = build_decision(_v17(), _v18())
        brief = build_brief(d)
        assert "class_delta" in brief
        assert "days_since_run" in brief

    def test_has_comparison_table(self):
        d = build_decision(_v17(), _v18())
        brief = build_brief(d)
        assert "v17" in brief.lower() and "v18" in brief.lower()


class TestMain:
    def test_main_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_sqpe_v18_decision as module
        v17_path = tmp_path / "models" / "sqpe_v17" / "metadata.json"
        v18_path = tmp_path / "models" / "sqpe_v18" / "metadata.json"
        v17_path.parent.mkdir(parents=True)
        v18_path.parent.mkdir(parents=True)
        v17_path.write_text(json.dumps(_v17()), encoding="utf-8")
        v18_path.write_text(json.dumps(_v18()), encoding="utf-8")

        out_record = tmp_path / "data" / "reports" / "vfu_24_decision.json"
        out_brief  = tmp_path / "data" / "reports" / "vfu_24_decision.md"
        (tmp_path / "data" / "reports").mkdir(parents=True)

        monkeypatch.setattr(module, "V17_METADATA",  v17_path)
        monkeypatch.setattr(module, "V18_METADATA",  v18_path)
        monkeypatch.setattr(module, "OUTPUT_RECORD", out_record)
        monkeypatch.setattr(module, "OUTPUT_BRIEF",  out_brief)

        decision = main()

        assert decision["decision"] == "NO_PROMOTION"
        assert out_record.exists()
        assert out_brief.exists()
        loaded = json.loads(out_record.read_text())
        assert loaded["decision"] == "NO_PROMOTION"
        assert "SQPE_V18_NO_PROMOTION" in loaded["classification_codes"]
