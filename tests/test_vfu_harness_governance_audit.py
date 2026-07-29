"""
Tests for VFU-30: Harness + Governance Audit
scripts/ops/vfu_harness_governance_audit.py

Coverage:
  - audit_harness: returns dir exists, task tier counts, verdict
  - audit_council: reads run files, verdict counts, EVIDENCE_INCOMPLETE pct
  - audit_learning_gate: reads status files, gate_blocks count
  - build_summary: classification codes, overall score
  - build_brief: sections present
  - main(): outputs, correct structure
"""
import json
import pytest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_harness_governance_audit import (
    audit_harness,
    audit_council,
    audit_learning_gate,
    build_summary,
    build_brief,
    main,
    VFU_VERSION,
    KNOWN_TASKS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_council_run(tmp_path: Path, run_date: str, verdict: str,
                      status: str = "READY") -> None:
    d = tmp_path / "data" / "council_runs"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"council_run_{run_date}.json").write_text(
        json.dumps({"council_verdict": verdict, "council_status": status}),
        encoding="utf-8",
    )


def _make_learning_status(tmp_path: Path, date_tag: str, verdict: str,
                           events: int = 30, mode: str = "OUTCOME_ONLY_EOD_REPLAY") -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / f"nightly_eod_learning_status_{date_tag}.json").write_text(
        json.dumps({
            "date": date_tag.replace("_", "-"),
            "verdict": verdict,
            "learning_mode": mode,
            "events_created": events,
            "wins": 5,
            "losses": 25,
        }),
        encoding="utf-8",
    )


# ── audit_harness ─────────────────────────────────────────────────────────────

class TestAuditHarness:
    def test_no_returns_dir(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir(parents=True, exist_ok=True)
        r = audit_harness(d)
        assert r["harness_returns_exist"] is False
        assert r["executor_invoked"] is False
        assert r["n_harness_returns"] == 0

    def test_empty_returns_dir(self, tmp_path):
        (tmp_path / "data" / "harness_returns").mkdir(parents=True)
        r = audit_harness(tmp_path / "data")
        assert r["harness_returns_exist"] is True
        assert r["executor_invoked"] is False

    def test_returns_with_files(self, tmp_path):
        d = tmp_path / "data" / "harness_returns"
        d.mkdir(parents=True)
        (d / "run_1.json").write_text("{}", encoding="utf-8")
        (d / "run_2.json").write_text("{}", encoding="utf-8")
        r = audit_harness(tmp_path / "data")
        assert r["n_harness_returns"] == 2
        assert r["executor_invoked"] is True

    def test_all_shadow_verdict(self, tmp_path):
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        r = audit_harness(tmp_path / "data")
        assert r["n_shadow_tasks"] == len(KNOWN_TASKS)
        assert r["n_enforced_tasks"] == 0
        assert r["verdict"] == "HARNESS_SHADOW_ONLY"

    def test_task_tiers_present(self, tmp_path):
        (tmp_path / "data").mkdir(parents=True, exist_ok=True)
        r = audit_harness(tmp_path / "data")
        assert "SIGMA_CLOSE" in r["task_tiers"]
        assert "DAILY_LEARNING_AUDIT" in r["task_tiers"]


# ── audit_council ─────────────────────────────────────────────────────────────

class TestAuditCouncil:
    def test_no_files(self, tmp_path):
        d = tmp_path / "data" / "council_runs"
        d.mkdir(parents=True, exist_ok=True)
        r = audit_council(d)
        assert r["verdict"] == "NO_COUNCIL_RUNS"

    def test_verdict_counts(self, tmp_path):
        d = tmp_path / "data" / "council_runs"
        _make_council_run(tmp_path, "2026-07-20", "PASS_TO_LEARNING")
        _make_council_run(tmp_path, "2026-07-21", "PASS_TO_LEARNING")
        _make_council_run(tmp_path, "2026-07-22", "WATCH_ONLY")
        r = audit_council(d)
        assert r["verdict_distribution"]["PASS_TO_LEARNING"] == 2
        assert r["verdict_distribution"]["WATCH_ONLY"] == 1
        assert r["watch_only_blocks"] == 1

    def test_evidence_incomplete_pct(self, tmp_path):
        d = tmp_path / "data" / "council_runs"
        _make_council_run(tmp_path, "2026-07-20", "PASS_TO_LEARNING", "EVIDENCE_INCOMPLETE")
        _make_council_run(tmp_path, "2026-07-21", "PASS_TO_LEARNING", "READY")
        r = audit_council(d)
        assert r["evidence_incomplete_pct"] == pytest.approx(0.5)

    def test_n_runs(self, tmp_path):
        d = tmp_path / "data" / "council_runs"
        for i in range(5):
            _make_council_run(tmp_path, f"2026-07-{20+i:02d}", "PASS_TO_LEARNING")
        r = audit_council(d)
        assert r["n_runs"] == 5

    def test_recent_verdicts_limited(self, tmp_path):
        d = tmp_path / "data" / "council_runs"
        for i in range(8):
            _make_council_run(tmp_path, f"2026-07-{20+i:02d}", "PASS_TO_LEARNING")
        r = audit_council(d)
        assert len(r["recent_verdicts"]) == 5


# ── audit_learning_gate ───────────────────────────────────────────────────────

class TestAuditLearningGate:
    def test_no_files(self, tmp_path):
        d = tmp_path / "data"
        d.mkdir(parents=True, exist_ok=True)
        r = audit_learning_gate(d)
        assert r["verdict"] == "NO_LEARNING_STATUS_FILES"

    def test_gate_blocks_counted(self, tmp_path):
        _make_learning_status(tmp_path, "2026_07_25", "FAIL_GATE_BLOCKED")
        _make_learning_status(tmp_path, "2026_07_26", "FAIL_GATE_BLOCKED")
        _make_learning_status(tmp_path, "2026_07_27", "SUCCESS")
        r = audit_learning_gate(tmp_path / "data")
        assert r["gate_blocks_n"] == 2
        assert r["gate_enforcement"] == "ACTIVE"
        assert r["verdict"] == "GATE_ENFORCEMENT_CONFIRMED"

    def test_no_recent_blocks(self, tmp_path):
        _make_learning_status(tmp_path, "2026_07_27", "SUCCESS")
        r = audit_learning_gate(tmp_path / "data")
        assert r["gate_enforcement"] == "NO_RECENT_BLOCKS"
        assert r["verdict"] == "GATE_WIRED_NOT_RECENTLY_TRIGGERED"

    def test_recent_runs_populated(self, tmp_path):
        _make_learning_status(tmp_path, "2026_07_25", "SUCCESS", events=30)
        r = audit_learning_gate(tmp_path / "data")
        assert len(r["recent_runs"]) == 1
        assert r["recent_runs"][0]["events"] == 30


# ── build_summary ─────────────────────────────────────────────────────────────

class TestBuildSummary:
    def _harness(self, invoked=False):
        return {"n_registered_tasks": 5, "n_shadow_tasks": 5, "n_enforced_tasks": 0,
                "harness_returns_exist": invoked, "n_harness_returns": 1 if invoked else 0,
                "executor_invoked": invoked, "task_tiers": KNOWN_TASKS,
                "verdict": "HARNESS_SHADOW_ONLY", "gap": "not invoked"}

    def _council(self):
        return {"n_runs": 10, "verdict_distribution": {"PASS_TO_LEARNING": 7, "WATCH_ONLY": 3},
                "status_distribution": {"READY": 5, "EVIDENCE_INCOMPLETE": 5},
                "recent_verdicts": [], "watch_only_blocks": 3, "evidence_incomplete_n": 5,
                "evidence_incomplete_pct": 0.5, "verdict": "COUNCIL_ACTIVE_GATE"}

    def _gate(self, blocks=0):
        return {"n_files": 5, "recent_runs": [], "verdict_counts": {"SUCCESS": 5},
                "gate_blocks_n": blocks,
                "gate_enforcement": "ACTIVE" if blocks > 0 else "NO_RECENT_BLOCKS",
                "verdict": "GATE_ENFORCEMENT_CONFIRMED" if blocks > 0 else "GATE_WIRED_NOT_RECENTLY_TRIGGERED"}

    def test_classification_codes(self):
        s = build_summary(self._harness(), self._council(), self._gate())
        assert "VFU_30_HARNESS_GOVERNANCE_AUDIT_COMPLETE" in s["classification_codes"]
        assert "REPORT_ONLY" in s["classification_codes"]

    def test_vfu_version(self):
        s = build_summary(self._harness(), self._council(), self._gate())
        assert s["vfu30_validation_version"] == VFU_VERSION

    def test_score_skeleton_no_executor(self):
        s = build_summary(self._harness(False), self._council(), self._gate(0))
        assert s["overall_governance_score"] == "PARTIAL"

    def test_score_full(self):
        s = build_summary(self._harness(True), self._council(), self._gate(2))
        assert s["overall_governance_score"] == "FULL"


# ── build_brief ────────────────────────────────────────────────────────────────

class TestBuildBrief:
    def _summary(self):
        from scripts.ops.vfu_harness_governance_audit import build_summary
        h = {"n_registered_tasks": 5, "n_shadow_tasks": 5, "n_enforced_tasks": 0,
             "harness_returns_exist": False, "n_harness_returns": 0,
             "executor_invoked": False, "task_tiers": KNOWN_TASKS,
             "verdict": "HARNESS_SHADOW_ONLY", "gap": "never invoked"}
        c = {"n_runs": 3, "verdict_distribution": {"PASS_TO_LEARNING": 2, "WATCH_ONLY": 1},
             "status_distribution": {"READY": 2, "EVIDENCE_INCOMPLETE": 1},
             "recent_verdicts": [{"date": "2026-07-27", "verdict": "WATCH_ONLY", "status": "READY"}],
             "watch_only_blocks": 1, "evidence_incomplete_n": 1,
             "evidence_incomplete_pct": 0.33, "verdict": "COUNCIL_ACTIVE_GATE"}
        g = {"n_files": 2, "recent_runs": [{"date": "2026-07-27", "learning_mode": "x",
             "verdict": "SUCCESS", "events": 30, "wins": 5, "losses": 25}],
             "verdict_counts": {"SUCCESS": 2}, "gate_blocks_n": 0,
             "gate_enforcement": "NO_RECENT_BLOCKS",
             "verdict": "GATE_WIRED_NOT_RECENTLY_TRIGGERED"}
        return build_summary(h, c, g)

    def test_has_header(self):
        brief = build_brief(self._summary())
        assert "VFU-30" in brief

    def test_has_harness_section(self):
        brief = build_brief(self._summary())
        assert "HARNESS_SHADOW_ONLY" in brief

    def test_has_council_table(self):
        brief = build_brief(self._summary())
        assert "2026-07-27" in brief
        assert "WATCH_ONLY" in brief

    def test_has_gate_section(self):
        brief = build_brief(self._summary())
        assert "Learning Gate" in brief


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:
    def test_main_produces_outputs(self, tmp_path, monkeypatch):
        import scripts.ops.vfu_harness_governance_audit as mod
        data_dir    = tmp_path / "data"
        council_dir = data_dir / "council_runs"
        out_json    = data_dir / "reports" / "vfu_30.json"
        out_md      = data_dir / "reports" / "vfu_30.md"
        monkeypatch.setattr(mod, "OUTPUT_JSON", out_json)
        monkeypatch.setattr(mod, "OUTPUT_MD",   out_md)
        (data_dir / "reports").mkdir(parents=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        _make_council_run(tmp_path, "2026-07-25", "WATCH_ONLY")
        _make_council_run(tmp_path, "2026-07-26", "PASS_TO_LEARNING")
        _make_learning_status(tmp_path, "2026_07_25", "FAIL_GATE_BLOCKED")

        result = main(data_dir=data_dir, council_dir=council_dir)

        assert result["vfu30_validation_version"] == VFU_VERSION
        assert "VFU_30_HARNESS_GOVERNANCE_AUDIT_COMPLETE" in result["classification_codes"]
        assert result["harness_audit"]["executor_invoked"] is False
        assert result["council_audit"]["n_runs"] == 2
        assert result["learning_gate_audit"]["gate_blocks_n"] == 1
        assert out_json.exists()
        assert out_md.exists()
