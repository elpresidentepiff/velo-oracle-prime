"""Mission Control source truth must come from the observability packet.

Contract (operator-mandated, 2026-06-10):
  - clean packet      -> RP_MERGED_CLEAN
  - degraded packet   -> RP_MERGED_DEGRADED (and learning gate BLOCKED)
  - missing packet    -> UNKNOWN (and learning gate BLOCKED)
  - malformed packet  -> UNKNOWN
  - NEVER defaults to RP_MERGED_CLEAN
  - read-only: no Supabase writes, no scoring imports
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.mission_control_config import MC_CONFIG  # noqa: E402
from scripts.ops.update_mission_control import (  # noqa: E402
    _detect_source_truth,
    _gate_status,
    _read_observability_source_truth,
)


def _write_packet(data_dir: Path, date_und: str, run_id: str, label: str, ts: str) -> None:
    packet = {"source_truth": label, "timestamp": ts, "run_id": run_id}
    (data_dir / f"velo_run_observability_{date_und}_{run_id}.json").write_text(json.dumps(packet))


def test_clean_packet_returns_clean(tmp_path):
    _write_packet(tmp_path, "2026_06_09", "aaaa1111", "RP_MERGED_CLEAN", "2026-06-09T05:00:00+00:00")
    assert _detect_source_truth([], "2026-06-09", data_dir=tmp_path) == "RP_MERGED_CLEAN"


def test_degraded_packet_returns_degraded(tmp_path):
    _write_packet(tmp_path, "2026_06_10", "bbbb2222", "RP_MERGED_DEGRADED", "2026-06-10T04:26:00+00:00")
    assert _detect_source_truth([], "2026-06-10", data_dir=tmp_path) == "RP_MERGED_DEGRADED"


def test_missing_packet_returns_unknown(tmp_path):
    assert _detect_source_truth([], "2026-06-11", data_dir=tmp_path) == "UNKNOWN"


def test_malformed_packet_returns_unknown(tmp_path):
    (tmp_path / "velo_run_observability_2026_06_10_cccc3333.json").write_text("{not valid json")
    assert _detect_source_truth([], "2026-06-10", data_dir=tmp_path) == "UNKNOWN"


def test_unrecognised_label_returns_unknown(tmp_path):
    _write_packet(tmp_path, "2026_06_10", "dddd4444", "TOTALLY_FINE_TRUST_ME", "2026-06-10T04:26:00+00:00")
    assert _detect_source_truth([], "2026-06-10", data_dir=tmp_path) == "UNKNOWN"


def test_latest_packet_wins_on_retry_days(tmp_path):
    # June 9 pattern: a failed early run then a clean final run — final run wins.
    _write_packet(tmp_path, "2026_06_09", "eeee5555", "SOURCE_UNKNOWN_BLOCK", "2026-06-09T04:29:00+00:00")
    _write_packet(tmp_path, "2026_06_09", "ffff6666", "RP_MERGED_CLEAN", "2026-06-09T05:16:00+00:00")
    assert _read_observability_source_truth("2026-06-09", data_dir=tmp_path) == "RP_MERGED_CLEAN"


def test_contamination_takes_precedence(tmp_path):
    _write_packet(tmp_path, "2026_06_10", "abcd9999", "RP_MERGED_CLEAN", "2026-06-10T04:26:00+00:00")
    contaminated_sha = next(iter(MC_CONFIG.CONTAMINATED_RUN_IDS))
    rows = [{"run_id": f"2026_06_10_{contaminated_sha}_1"}]
    assert _detect_source_truth(rows, "2026-06-10", data_dir=tmp_path) == "RP_MERGED_CONTAMINATED"


def test_degraded_blocks_learning_gate():
    learning, promotion, reasons = _gate_status(0, 0, "RP_MERGED_DEGRADED")
    assert learning == MC_CONFIG.LEARNING_GATE_BLOCKED
    assert promotion == MC_CONFIG.PROMOTION_GATE_BLOCKED
    assert "GATE_SOURCE_DEGRADED" in reasons


def test_unknown_blocks_learning_gate():
    learning, promotion, reasons = _gate_status(0, 0, "UNKNOWN")
    assert learning == MC_CONFIG.LEARNING_GATE_BLOCKED
    assert "GATE_SOURCE_UNKNOWN" in reasons


def test_clean_day_keeps_gates_open():
    learning, promotion, reasons = _gate_status(0, 0, "RP_MERGED_CLEAN")
    assert learning == MC_CONFIG.LEARNING_GATE_OPEN
    assert promotion == MC_CONFIG.PROMOTION_GATE_OPEN
    assert reasons == []


def test_no_scoring_imports_in_mission_control():
    src = (ROOT / "scripts" / "ops" / "update_mission_control.py").read_text()
    for forbidden in ("velo_prime_service", "velo_prime_ensemble", "score_race"):
        assert forbidden not in src
