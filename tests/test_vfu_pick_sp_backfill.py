"""
Tests for VFU-21: pick_sp Backfill — scripts/ops/vfu_pick_sp_backfill.py

Coverage:
  - normalize_name edge cases
  - _build_sp_index: standard dict schema, list+full_runners schema, no file, all-zero SP
  - _needs_backfill: null, 0.0, 10.0 trigger; real values do not
  - process_row: RECOVERED / NO_FILE / NO_SP / HORSE_NOT_FOUND / ORIGINAL_PRESENT
  - Evidence tier upgrade: TIER_B_GOOD_NO_PICK_SP → TIER_B_GOOD / TIER_A_FULL
  - Does NOT overwrite existing real pick_sp
  - build_summary counts and coverage
  - main() integration: writes correct output files
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_pick_sp_backfill import (
    normalize_name,
    _build_sp_index,
    _needs_backfill,
    process_row,
    build_summary,
    main,
    RECOVERY_DONE,
    NO_FILE,
    NO_SP_IN_FILE,
    HORSE_NOT_FOUND,
    ORIGINAL_PRESENT,
    VFU_VERSION,
)


# ------------------------------------------------------------------
# normalize_name
# ------------------------------------------------------------------

class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("Gris Majeur") == "gris majeur"

    def test_apostrophe_removed(self):
        assert normalize_name("Rider's Dream") == "riders dream"

    def test_hyphen_to_space(self):
        assert normalize_name("Well-Known") == "well known"

    def test_double_space_collapsed(self):
        assert normalize_name("Big  Horse") == "big horse"

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_none(self):
        assert normalize_name(None) == ""


# ------------------------------------------------------------------
# _build_sp_index
# ------------------------------------------------------------------

class TestBuildSpIndex:
    def _write_results(self, tmp_path: Path, date_tag: str, data) -> None:
        results_dir = tmp_path / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / f"rp_results_{date_tag}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_standard_dict_schema(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_pick_sp_backfill as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        self._write_results(tmp_path, "2026_06_08", {
            "results": [
                {"runners": [
                    {"horse": "Dreamasar",   "sp_dec": 9.0},
                    {"horse": "Lucky Star",  "sp_dec": 4.5},
                    {"horse": "Zero Horse",  "sp_dec": 0.0},
                ]},
            ]
        })
        idx, status = _build_sp_index("2026_06_08")
        assert status == "ok"
        assert idx["dreamasar"] == 9.0
        assert idx["lucky star"] == 4.5
        assert "zero horse" not in idx

    def test_list_schema_full_runners_no_sp(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_pick_sp_backfill as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        self._write_results(tmp_path, "2026_05_29", [
            {"race_id": "123", "full_runners": [
                {"horse": "Echo Of Stars", "position": "1"},
            ]},
        ])
        idx, status = _build_sp_index("2026_05_29")
        assert status == "no_sp_in_file"
        assert idx == {}

    def test_no_file(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_pick_sp_backfill as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        (tmp_path / "data" / "results").mkdir(parents=True, exist_ok=True)
        idx, status = _build_sp_index("2099_01_01")
        assert status == "no_file"
        assert idx == {}

    def test_all_zero_sp(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_pick_sp_backfill as module
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        self._write_results(tmp_path, "2026_06_05", {
            "results": [
                {"runners": [
                    {"horse": "Horse A", "sp_dec": 0.0},
                    {"horse": "Horse B", "sp_dec": 0.0},
                ]},
            ]
        })
        idx, status = _build_sp_index("2026_06_05")
        assert status == "no_sp_in_file"
        assert idx == {}


# ------------------------------------------------------------------
# _needs_backfill
# ------------------------------------------------------------------

class TestNeedsBackfill:
    def test_null(self):
        assert _needs_backfill({"pick_sp": None}) is True

    def test_zero(self):
        assert _needs_backfill({"pick_sp": 0.0}) is True

    def test_ten(self):
        assert _needs_backfill({"pick_sp": 10.0}) is True

    def test_real_value(self):
        assert _needs_backfill({"pick_sp": 4.5}) is False

    def test_missing_key(self):
        assert _needs_backfill({}) is True


# ------------------------------------------------------------------
# process_row
# ------------------------------------------------------------------

def _make_row(**kw) -> dict:
    base = {
        "ledger_id": "VFU19-00000",
        "race_id": "rac_123",
        "race_date": "2026-06-08",
        "horse_name": "Dreamasar",
        "horse_id": None,
        "pick_sp": None,
        "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP",
    }
    base.update(kw)
    return base


class TestProcessRow:
    def _indexes(self, status="ok", sp=9.0):
        idx = {"dreamasar": sp} if status == "ok" else {}
        return {"2026_06_08": (idx, status)}

    def test_recovered(self):
        row = _make_row()
        out = process_row(row, self._indexes())
        assert out["pick_sp"] == 9.0
        assert out["pick_sp_recovery_method"] == RECOVERY_DONE
        assert out["pick_sp_confidence"] == "HIGH"
        assert out["pick_sp_pre_backfill"] is None
        assert out["vfu21_validation_version"] == VFU_VERSION

    def test_no_file(self):
        row = _make_row()
        out = process_row(row, {"2026_06_08": ({}, "no_file")})
        assert out["pick_sp_recovery_method"] == NO_FILE
        assert out["pick_sp"] is None
        assert out["pick_sp_confidence"] == "NONE"

    def test_no_sp_in_file(self):
        row = _make_row()
        out = process_row(row, {"2026_06_08": ({}, "no_sp_in_file")})
        assert out["pick_sp_recovery_method"] == NO_SP_IN_FILE
        assert out["pick_sp"] is None

    def test_horse_not_found(self):
        row = _make_row(horse_name="Unknown Horse")
        out = process_row(row, self._indexes())
        assert out["pick_sp_recovery_method"] == HORSE_NOT_FOUND
        assert out["pick_sp"] is None

    def test_original_present_not_overwritten(self):
        row = _make_row(pick_sp=4.5)
        out = process_row(row, self._indexes())
        assert out["pick_sp"] == 4.5
        assert out["pick_sp_recovery_method"] == ORIGINAL_PRESENT
        assert out["pick_sp_pre_backfill"] == 4.5

    def test_tier_upgrade_no_horse_id(self):
        row = _make_row(horse_id=None)
        out = process_row(row, self._indexes())
        assert out["evidence_quality_tier"] == "TIER_B_GOOD"

    def test_tier_upgrade_with_horse_id(self):
        row = _make_row(horse_id="rp_CHE_dreamasar")
        out = process_row(row, self._indexes())
        assert out["evidence_quality_tier"] == "TIER_A_FULL"

    def test_other_tier_not_changed(self):
        row = _make_row(evidence_quality_tier="TIER_C_LIMITED_IDENTITY")
        out = process_row(row, self._indexes())
        assert out["evidence_quality_tier"] == "TIER_C_LIMITED_IDENTITY"

    def test_pre_backfill_preserves_zero(self):
        row = _make_row(pick_sp=0.0)
        out = process_row(row, self._indexes())
        assert out["pick_sp_pre_backfill"] == 0.0
        assert out["pick_sp"] == 9.0

    def test_pre_backfill_preserves_ten(self):
        row = _make_row(pick_sp=10.0)
        out = process_row(row, self._indexes())
        assert out["pick_sp_pre_backfill"] == 10.0
        assert out["pick_sp"] == 9.0


# ------------------------------------------------------------------
# build_summary
# ------------------------------------------------------------------

class TestBuildSummary:
    def _row(self, pick_sp, method, tier_in="TIER_B_GOOD_NO_PICK_SP", tier_out=None, horse_id=None):
        base = {
            "pick_sp": pick_sp,
            "pick_sp_recovery_method": method,
            "evidence_quality_tier": tier_out or tier_in,
        }
        return base

    def test_counts(self):
        rows_in = [
            {"pick_sp": None,  "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
            {"pick_sp": 4.5,   "evidence_quality_tier": "TIER_A_FULL"},
            {"pick_sp": 0.0,   "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
        ]
        rows_out = [
            {"pick_sp": 9.0,   "pick_sp_recovery_method": RECOVERY_DONE,    "evidence_quality_tier": "TIER_B_GOOD"},
            {"pick_sp": 4.5,   "pick_sp_recovery_method": ORIGINAL_PRESENT,  "evidence_quality_tier": "TIER_A_FULL"},
            {"pick_sp": None,  "pick_sp_recovery_method": NO_FILE,            "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
        ]
        s = build_summary(rows_in, rows_out)
        assert s["total_rows"] == 3
        assert s["backfill_candidates"] == 2
        assert s["recovered"] == 1
        assert s["unrecoverable"] == 1
        assert s["recovery_rate"] == pytest.approx(0.5)
        assert s["real_sp_coverage_after"] == 2  # 9.0 + 4.5
        assert s["method_breakdown"][RECOVERY_DONE] == 1
        assert s["method_breakdown"][NO_FILE] == 1

    def test_classification_codes_present(self):
        rows_in = [{"pick_sp": 4.5, "evidence_quality_tier": None}]
        rows_out = [{"pick_sp": 4.5, "pick_sp_recovery_method": ORIGINAL_PRESENT, "evidence_quality_tier": None}]
        s = build_summary(rows_in, rows_out)
        assert "VFU_21_PICK_SP_BACKFILL_COMPLETE" in s["classification_codes"]
        assert "NO_SUPABASE_WRITES" in s["classification_codes"]
        assert "NO_LIVE_SCORING_CHANGE" in s["classification_codes"]


# ------------------------------------------------------------------
# main() integration
# ------------------------------------------------------------------

class TestMain:
    def _write_results(self, tmp_path: Path, date_tag: str, data) -> None:
        results_dir = tmp_path / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / f"rp_results_{date_tag}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_main_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_pick_sp_backfill as module

        # Point all paths to tmp
        monkeypatch.setattr(module, "DATA", tmp_path / "data")
        monkeypatch.setattr(module, "OUTPUT_LEDGER",  tmp_path / "data" / "reports" / "vfu_21_ledger.jsonl")
        monkeypatch.setattr(module, "OUTPUT_SUMMARY", tmp_path / "data" / "reports" / "vfu_21_summary.json")
        monkeypatch.setattr(module, "OUTPUT_BRIEF",   tmp_path / "data" / "reports" / "vfu_21_brief.md")
        (tmp_path / "data" / "reports").mkdir(parents=True, exist_ok=True)

        # Write a tiny 3-row input ledger
        ledger_path = tmp_path / "data" / "reports" / "input.jsonl"
        rows = [
            {"ledger_id": "0", "race_date": "2026-06-08", "horse_name": "Dreamasar",
             "horse_id": None, "pick_sp": None, "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
            {"ledger_id": "1", "race_date": "2026-06-08", "horse_name": "Lucky Star",
             "horse_id": "rp_CHE_lstar", "pick_sp": 0.0, "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
            {"ledger_id": "2", "race_date": "2099-01-01", "horse_name": "Ghost Horse",
             "horse_id": None, "pick_sp": None, "evidence_quality_tier": "TIER_B_GOOD_NO_PICK_SP"},
        ]
        ledger_path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

        # Provide results for 2026-06-08
        self._write_results(tmp_path, "2026_06_08", {
            "results": [{"runners": [
                {"horse": "Dreamasar",  "sp_dec": 9.0},
                {"horse": "Lucky Star", "sp_dec": 3.5},
            ]}]
        })

        summary = main(ledger_path)

        assert summary["total_rows"] == 3
        assert summary["backfill_candidates"] == 3
        assert summary["recovered"] == 2
        assert summary["unrecoverable"] == 1
        assert summary["method_breakdown"][NO_FILE] == 1

        # Output ledger written
        out_rows = [json.loads(l) for l in
                    (tmp_path / "data" / "reports" / "vfu_21_ledger.jsonl")
                    .read_text().splitlines() if l.strip()]
        assert len(out_rows) == 3
        assert out_rows[0]["pick_sp"] == 9.0
        assert out_rows[0]["evidence_quality_tier"] == "TIER_B_GOOD"   # no horse_id
        assert out_rows[1]["pick_sp"] == 3.5
        assert out_rows[1]["evidence_quality_tier"] == "TIER_A_FULL"   # has horse_id
        assert out_rows[2]["pick_sp_recovery_method"] == NO_FILE
