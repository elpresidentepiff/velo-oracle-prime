#!/usr/bin/env python3
"""
Tests for VFU-25: Identity Resolution Sprint.
Run with: source venv/bin/activate && python -m pytest tests/test_vfu_25_identity_resolution.py -v
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_25_identity_resolution_sprint import (
    _norm,
    _load_jsonl,
    build_combined_lookup,
    resolve_ledger_rows,
    build_stats,
    VFU25_VERSION,
)
import scripts.ops.vfu_25_identity_resolution_sprint as _mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _ledger_row(
    horse_name="Test Horse",
    horse_id=None,
    race_date="2026-05-25",
    race_id="rac_test_001",
    course="Ascot",
    era="CURRENT_ERA_VALIDATED",
    pick_sp=None,
    outcome="MISS",
) -> dict:
    return {
        "ledger_id":     f"L_{race_id}",
        "horse_name":    horse_name,
        "horse_id":      horse_id,
        "race_date":     race_date,
        "race_id":       race_id,
        "course":        course,
        "era_bucket":    era,
        "pick_sp":       pick_sp,
        "outcome":       outcome,
    }


def _lookup_with(name="test horse", date="2026-05-25", horse_id="rp_ASC_test_horse",
                 sp=4.0, source="runner_snapshot", confidence="HIGH") -> dict:
    return {(_norm(name), date): (horse_id, sp, source, confidence)}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_01_name_only_row_is_resolved():
    """A NAME_ONLY row matching the lookup must appear in resolved list."""
    row = _ledger_row(horse_name="Test Horse", horse_id=None)
    lookup = _lookup_with(name="Test Horse", date="2026-05-25")
    resolved, unresolved = resolve_ledger_rows([row], lookup)
    assert len(resolved) == 1
    assert resolved[0]["resolved_horse_id"] == "rp_ASC_test_horse"


def test_02_row_with_existing_horse_id_skipped():
    """Rows that already have horse_id must not be overwritten."""
    row = _ledger_row(horse_name="Known Horse", horse_id="existing_id_999")
    lookup = _lookup_with(name="Known Horse", date="2026-05-25", horse_id="new_id_000")
    resolved, unresolved = resolve_ledger_rows([row], lookup)
    assert len(resolved) == 0  # existing id row is skipped


def test_03_unresolved_row_in_unresolved_list():
    """Row with no lookup match must appear in unresolved list."""
    row = _ledger_row(horse_name="Unknown Horse")
    resolved, unresolved = resolve_ledger_rows([row], {})
    assert len(unresolved) == 1
    assert unresolved[0]["reason"] == "NO_SOURCE_COVERAGE"


def test_04_resolved_row_has_blocked_from_live_use():
    """Every resolved entry must have blocked_from_live_use=True."""
    row = _ledger_row()
    lookup = _lookup_with()
    resolved, _ = resolve_ledger_rows([row], lookup)
    assert all(r["blocked_from_live_use"] is True for r in resolved)


def test_05_resolved_row_has_human_review_required():
    """Every resolved entry must have human_review_required=True."""
    row = _ledger_row()
    lookup = _lookup_with()
    resolved, _ = resolve_ledger_rows([row], lookup)
    assert all(r["human_review_required"] is True for r in resolved)


def test_06_sp_repair_fills_null_only():
    """SP repair must populate pick_sp_repaired only when pick_sp was null."""
    row_null_sp = _ledger_row(pick_sp=None)
    row_has_sp  = _ledger_row(horse_name="Has SP", race_id="rac_002", pick_sp=3.5)
    lookup = {
        (_norm("Test Horse"), "2026-05-25"): ("id_1", 4.0, "runner_snapshot", "HIGH"),
        (_norm("Has SP"),     "2026-05-25"): ("id_2", 5.0, "runner_snapshot", "HIGH"),
    }
    resolved, _ = resolve_ledger_rows([row_null_sp, row_has_sp], lookup)
    assert len(resolved) == 2
    null_entry = next(r for r in resolved if r["horse_name"] == "Test Horse")
    has_entry  = next(r for r in resolved if r["horse_name"] == "Has SP")
    assert null_entry["pick_sp_repaired"] == 4.0   # filled from lookup
    assert has_entry["pick_sp_repaired"] is None    # not overwritten


def test_07_name_normalisation_case_insensitive():
    """Name matching must be case-insensitive."""
    row = _ledger_row(horse_name="ALLCAPS HORSE")
    lookup = {(_norm("allcaps horse"), "2026-05-25"): ("id_norm", 3.0, "snapshot", "HIGH")}
    resolved, _ = resolve_ledger_rows([row], lookup)
    assert len(resolved) == 1


def test_08_stats_total_resolves_correctly():
    """Stats must count resolved + unresolved consistently."""
    rows = [_ledger_row(race_id=f"r{i}") for i in range(4)]
    lookup = _lookup_with()  # only matches race_id rac_test_001
    resolved, unresolved = resolve_ledger_rows(rows, lookup)
    stats = build_stats(rows, resolved, unresolved)
    assert stats["total_name_only"] == 4
    assert stats["total_resolved"] + stats["total_unresolved"] == 4


def test_09_stats_sp_repair_count_correct():
    """SP repair count must match number of entries where pick_sp_repaired is not None."""
    rows = [
        _ledger_row(pick_sp=None),
        _ledger_row(horse_name="Has SP", race_id="rac_002", pick_sp=5.0),
    ]
    lookup = {
        (_norm("Test Horse"), "2026-05-25"): ("id_1", 4.0, "s", "HIGH"),
        (_norm("Has SP"),     "2026-05-25"): ("id_2", 3.0, "s", "HIGH"),
    }
    resolved, unresolved = resolve_ledger_rows(rows, lookup)
    stats = build_stats(rows, resolved, unresolved)
    assert stats["sp_repairs"] == 1


def test_10_vfu11_ledger_not_mutated():
    """VFU-25 module must not write to the VFU-11 master ledger."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    # Must not open the ledger file for writing
    assert 'open(LEDGER_PATH, "w"' not in src
    assert "open(LEDGER_PATH, 'w'" not in src
    assert "LEDGER_PATH.write_text" not in src


def test_11_no_supabase_in_module():
    """VFU-25 module must not import or call Supabase."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "create_client" not in src
    assert "from supabase" not in src
    assert "import supabase" not in src


def test_12_no_telegram_in_module():
    """VFU-25 module must not contain Telegram send logic."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "bot.send" not in src
    assert "telegram.Bot" not in src
    assert "sendMessage" not in src


def test_13_no_live_scoring_in_module():
    """VFU-25 must not invoke the live scoring pipeline."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "run_prime_today" not in src
    assert "SQPEEngine" not in src
    assert "VeloPrimeEnsemble" not in src


def test_14_resolution_source_recorded():
    """Each resolved entry must record which source provided the horse_id."""
    row = _ledger_row()
    lookup = _lookup_with(source="runner_snapshot")
    resolved, _ = resolve_ledger_rows([row], lookup)
    assert resolved[0]["resolution_source"] == "runner_snapshot"


def test_15_confidence_level_recorded():
    """Each resolved entry must record the confidence level."""
    row = _ledger_row()
    lookup = _lookup_with(confidence="CONFIRMED")
    resolved, _ = resolve_ledger_rows([row], lookup)
    assert resolved[0]["resolution_confidence"] == "CONFIRMED"


def test_16_resolution_version_stamped():
    """Each resolved entry must carry the VFU25_VERSION stamp."""
    row = _ledger_row()
    lookup = _lookup_with()
    resolved, _ = resolve_ledger_rows([row], lookup)
    assert resolved[0]["resolution_version"] == VFU25_VERSION


def test_17_era_bucket_preserved():
    """Resolved entry must preserve the original era_bucket."""
    row = _ledger_row(era="PRE_SURGERY_ARCHIVE_QUARANTINE")
    lookup = _lookup_with()
    resolved, _ = resolve_ledger_rows([row], lookup)
    assert resolved[0]["era_bucket"] == "PRE_SURGERY_ARCHIVE_QUARANTINE"


def test_18_horse_passport_not_mutated_flag():
    """Summary must include horse_passport_mutated=False."""
    src = pathlib.Path(_mod.__file__).read_text(encoding="utf-8")
    assert "horse_passport_mutated" in src
    assert '"horse_passport_mutated": False' in src or "'horse_passport_mutated': False" in src


def test_19_real_ledger_resolution_rate_over_40_pct():
    """Against real VFU-11 ledger, resolution rate must exceed 40%."""
    if not _mod.LEDGER_PATH.exists():
        return  # skip if no ledger
    lookup = build_combined_lookup(_mod.DATA, _mod.VFU21_PATH)
    ledger = _load_jsonl(_mod.LEDGER_PATH)
    resolved, unresolved = resolve_ledger_rows(ledger, lookup)
    stats = build_stats(ledger, resolved, unresolved)
    assert stats["resolution_rate_pct"] >= 40.0, (
        f"Resolution rate {stats['resolution_rate_pct']}% below 40% floor"
    )


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = sorted(
        [(k, v) for k, v in globals().items() if k.startswith("test_")],
        key=lambda x: x[0],
    )
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
    print(f"\n{passed + failed} tests  |  {passed} passed  |  {failed} failed")
    sys.exit(1 if failed else 0)
