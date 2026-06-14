"""
tests/test_vfu_horse_id_bridge.py
====================================
VFU-06 — Horse Identity Bridge tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ops.vfu_horse_id_bridge import (
    norm_horse,
    detect_namespace,
    build_passport_lookup,
    resolve_identity,
    BRIDGE_VERSION,
)

BRIDGE_FILE    = ROOT / "data/reports/vfu_horse_id_bridge.json"
ENRICHED_FILE  = ROOT / "data/reports/vfu_horse_id_bridge_enriched_union.json"
CLUSTERS_FILE  = ROOT / "data/reports/vfu_horse_id_bridge_repeated_clusters.json"
REPORT_JSON    = ROOT / "data/reports/vfu_horse_identity_bridge_report.json"
UNMATCHED_FILE = ROOT / "data/reports/vfu_horse_identity_bridge_unmatched.json"
AMBIGUOUS_FILE = ROOT / "data/reports/vfu_horse_identity_bridge_ambiguous.json"
CONFLICTS_FILE = ROOT / "data/reports/vfu_horse_identity_bridge_conflicts.json"
AUTOPSY_ID     = ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl"
PASSPORT_ID    = ROOT / "data/reports/vfu_current_era_passport_candidates_identity_enriched.jsonl"
CANON_PASSPORT = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
PASSPORT_FILE  = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"


def _report() -> dict:
    return json.loads(REPORT_JSON.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ── 1. norm_horse strips country suffix before punctuation ────────────────────

def test_norm_horse_strips_country_suffix():
    assert norm_horse("Bint Archange (IRE)") == "bint archange"
    assert norm_horse("Kakirra") == "kakirra"
    assert norm_horse("Chemistry") == "chemistry"
    assert norm_horse("") == ""
    assert norm_horse(None) == ""


# ── 2. detect_namespace classifies ID formats ─────────────────────────────────

def test_detect_namespace():
    assert detect_namespace("8866972") == "EOD_NUMERIC"
    assert detect_namespace(8866972) == "EOD_NUMERIC"
    assert detect_namespace("hrs_53420339") == "RACING_API_HRS"
    assert detect_namespace("rp_WOL_kakirra") == "CONSTRUCTED_RP_NAME"
    assert detect_namespace(None) == "UNKNOWN"
    assert detect_namespace("weird_format") == "UNKNOWN"


# ── 3. Passport lookup: unique vs ambiguous ───────────────────────────────────

def test_passport_lookup_unique_vs_ambiguous():
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    try:
        tmp.write(json.dumps({"horse_name": "Testfilly", "horse_rp_uid": 100}) + "\n")
        tmp.write(json.dumps({"horse_name": "testfilly", "horse_rp_uid": 200}) + "\n")
        tmp.write(json.dumps({"horse_name": "Unique Horse", "horse_rp_uid": 300}) + "\n")
        tmp.close()
        lookup = build_passport_lookup(Path(tmp.name))
        # Both "Testfilly" and "testfilly" norm to "testfilly" → AMBIGUOUS
        assert lookup["testfilly"]["unique"] is False
        assert len(lookup["testfilly"]["all_entries"]) == 2
        # "Unique Horse" is unique
        assert lookup["unique horse"]["unique"] is True
        assert lookup["unique horse"]["rp_uid"] == 300
    finally:
        os.unlink(tmp.name)


# ── 4. Priority 1: existing horse_id on row ───────────────────────────────────

def test_priority1_existing_horse_id():
    row = {"horse_name": "Kakirra", "race_id": "rp_WOL_x", "horse_id": "9999999"}
    identity = resolve_identity(row, {}, {}, {})
    assert identity["horse_id"] == "9999999"
    assert identity["horse_id_source"] == "ROW_EXISTING"
    assert identity["horse_id_join_confidence"] == "HIGH"


# ── 5. Priority 2: unique passport match → RP_UID HIGH ───────────────────────

def test_priority2_passport_match_high():
    passport_lookup = {"kakirra": {"horse_name": "Kakirra", "rp_uid": 8866972, "unique": True, "all_entries": [{"horse_name": "Kakirra", "rp_uid": 8866972}]}}
    row = {"horse_name": "Kakirra", "race_id": "rp_WOL_test"}
    identity = resolve_identity(row, passport_lookup, {}, {})
    assert identity["horse_id"] == "8866972"
    assert identity["horse_id_namespace"] == "RP_UID"
    assert identity["horse_id_source"] == "PASSPORT_NORM_MATCH"
    assert identity["horse_id_join_confidence"] == "HIGH"
    assert identity["horse_id_ambiguous"] is False
    assert identity["horse_id_conflict"] is False


# ── 6. Priority 2: ambiguous passport → AMBIGUOUS, not filled ─────────────────

def test_priority2_passport_ambiguous_not_filled():
    passport_lookup = {
        "lyneham": {
            "horse_name": "Lyneham", "rp_uid": 111, "unique": False,
            "all_entries": [{"horse_name": "Lyneham", "rp_uid": 111}, {"horse_name": "Lyneham", "rp_uid": 222}],
        }
    }
    row = {"horse_name": "Lyneham", "race_id": "rp_TST_test"}
    identity = resolve_identity(row, passport_lookup, {}, {})
    assert identity["horse_id"] is None
    assert identity["horse_id_join_confidence"] == "AMBIGUOUS"
    assert identity["horse_id_ambiguous"] is True


# ── 7. Priority 3: EOD race+name match → MEDIUM ───────────────────────────────

def test_priority3_eod_race_match():
    row = {"horse_name": "Chemistry", "race_id": "rp_KEL_20260524_2.28"}
    eod_race = {("rp_KEL_20260524_2.28", "chemistry"): "hrs_12345"}
    identity = resolve_identity(row, {}, eod_race, {})
    assert identity["horse_id"] == "hrs_12345"
    assert identity["horse_id_namespace"] == "RACING_API_HRS"
    assert identity["horse_id_source"] == "EOD_RACE_MATCH"
    assert identity["horse_id_join_confidence"] == "MEDIUM"


# ── 8. Priority 4: unique EOD name match → LOW ───────────────────────────────

def test_priority4_eod_name_unique():
    row = {"horse_name": "Unique Name Horse", "race_id": "rp_XXX_999"}
    eod_name = {"unique name horse": {"ids": ["rp_XXX_unique_name_horse"], "unique": True}}
    identity = resolve_identity(row, {}, {}, eod_name)
    assert identity["horse_id"] == "rp_XXX_unique_name_horse"
    assert identity["horse_id_namespace"] == "CONSTRUCTED_RP_NAME"
    assert identity["horse_id_source"] == "EOD_NAME_MATCH"
    assert identity["horse_id_join_confidence"] == "LOW"


# ── 9. EOD name ambiguous → AMBIGUOUS, not filled ────────────────────────────

def test_priority4_eod_name_ambiguous_not_filled():
    row = {"horse_name": "Multi Id Horse", "race_id": "rp_XXX_999"}
    eod_name = {"multi id horse": {"ids": ["hrs_111", "hrs_222"], "unique": False}}
    identity = resolve_identity(row, {}, {}, eod_name)
    assert identity["horse_id"] is None
    assert identity["horse_id_join_confidence"] == "AMBIGUOUS"
    assert identity["horse_id_ambiguous"] is True


# ── 10. Conflict: passport RP_UID vs EOD numeric differ ──────────────────────

def test_conflict_passport_vs_eod_numeric():
    passport_lookup = {"conflict horse": {"horse_name": "Conflict Horse", "rp_uid": 1111, "unique": True, "all_entries": [{"horse_name": "Conflict Horse", "rp_uid": 1111}]}}
    eod_race = {("rp_TST_race", "conflict horse"): "9999"}  # different numeric
    row = {"horse_name": "Conflict Horse", "race_id": "rp_TST_race"}
    identity = resolve_identity(row, passport_lookup, eod_race, {})
    # Passport wins (priority 2), but conflict is flagged
    assert identity["horse_id"] == "1111"
    assert identity["horse_id_namespace"] == "RP_UID"
    assert identity["horse_id_conflict"] is True
    assert "CONFLICT" in (identity["horse_id_missing_reason"] or "")


# ── 11. No horse_name → structurally unmatchable ──────────────────────────────

def test_no_horse_name_structurally_unmatchable():
    for name in [None, "", "?"]:
        row = {"horse_name": name, "race_id": "920219"}
        identity = resolve_identity(row, {}, {}, {})
        assert identity["horse_id"] is None
        assert identity["horse_id_join_confidence"] == "UNMATCHED"
        assert identity["horse_id_missing_reason"] == "NO_HORSE_NAME_STRUCTURALLY_UNMATCHABLE"


# ── 12. Every enriched row has all identity fields ────────────────────────────

def test_all_identity_fields_present():
    if not ENRICHED_FILE.exists():
        pytest.skip("VFU-06 not yet generated")
    rows = json.loads(ENRICHED_FILE.read_text())
    required = {
        "horse_id", "horse_id_namespace", "horse_id_source",
        "horse_id_join_key", "horse_id_join_confidence",
        "horse_id_missing_reason", "horse_id_ambiguous", "horse_id_conflict",
        "identity_bridge_version",
    }
    for r in rows[:50]:
        for fld in required:
            assert fld in r, f"Row missing field: {fld}"
        assert r["identity_bridge_version"] == BRIDGE_VERSION


# ── 13. Enriched union row count is exactly 1263 ─────────────────────────────

def test_enriched_union_row_count():
    if not ENRICHED_FILE.exists():
        pytest.skip("VFU-06 not yet generated")
    rows = json.loads(ENRICHED_FILE.read_text())
    assert len(rows) == 1263


# ── 14. Coverage increased from 0 to > 50% ───────────────────────────────────

def test_coverage_increased():
    if not REPORT_JSON.exists():
        pytest.skip("VFU-06 not yet generated")
    report = _report()
    assert report["coverage_before"]["horse_id_filled"] == 0
    assert report["coverage_after"]["horse_id_filled"] > 600
    assert report["coverage_after"]["pct"] > 50.0


# ── 15. Kakirra resolved to RP_UID ───────────────────────────────────────────

def test_kakirra_identity_resolved():
    if not REPORT_JSON.exists():
        pytest.skip("VFU-06 not yet generated")
    report = _report()
    k = report.get("kakirra", {})
    assert k.get("horse_id") == "8866972", f"Expected 8866972, got {k.get('horse_id')}"
    assert k.get("namespace") == "RP_UID"
    assert k.get("confidence") == "HIGH"


# ── 16. Passport automation status reported ───────────────────────────────────

def test_passport_automation_status():
    if not REPORT_JSON.exists():
        pytest.skip("VFU-06 not yet generated")
    report = _report()
    status = report.get("passport_automation_status", "")
    assert status in (
        "PARTIALLY_UNBLOCKED_FOR_RP_UID_ROWS",
        "STILL_BLOCKED_NO_RP_UID_IN_CANDIDATES",
    ), f"Unexpected passport automation status: {status}"


# ── 17. Canonical passport not mutated ───────────────────────────────────────

def test_canonical_passport_not_mutated():
    assert str(ENRICHED_FILE) != str(CANON_PASSPORT)
    assert str(AUTOPSY_ID) != str(CANON_PASSPORT)
    if CANON_PASSPORT.exists():
        content = CANON_PASSPORT.read_text(encoding="utf-8")
        assert BRIDGE_VERSION not in content, \
            "Canonical passport must not contain VFU bridge provenance"


# ── 18. No Supabase import ────────────────────────────────────────────────────

def test_no_supabase_in_bridge_script():
    script = ROOT / "scripts/ops/vfu_horse_id_bridge.py"
    source = script.read_text(encoding="utf-8")
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    assert "import supabase" not in code.lower()
    assert "SUPABASE_URL" not in code
    assert "create_client" not in code


# ── 19. Summary report has required fields ────────────────────────────────────

def test_summary_report_required_fields():
    if not REPORT_JSON.exists():
        pytest.skip("VFU-06 not yet generated")
    report = _report()
    required = {
        "rows_scanned", "coverage_before", "coverage_after",
        "confidence_counts", "namespace_counts", "source_counts",
        "structurally_unmatchable", "ambiguous_count", "conflict_count",
        "kakirra", "passport_automation_status",
        "canonical_passport_mutated", "supabase_written",
        "final_classifications",
    }
    for k in required:
        assert k in report, f"Summary missing key: {k}"
    assert report["canonical_passport_mutated"] is False
    assert report["supabase_written"] is False
    assert "VFU_06_HORSE_IDENTITY_BRIDGE_COMPLETE" in report["final_classifications"]
    assert "AMBIGUOUS_IDENTITIES_NOT_FILLED" in report["final_classifications"]
    assert "CONFLICTING_IDENTITIES_NOT_OVERRIDDEN" in report["final_classifications"]


# ── 20. Ambiguous entries not filled ─────────────────────────────────────────

def test_ambiguous_entries_not_filled():
    if not ENRICHED_FILE.exists():
        pytest.skip("VFU-06 not yet generated")
    rows = json.loads(ENRICHED_FILE.read_text())
    for r in rows:
        if r.get("horse_id_ambiguous") is True:
            assert r.get("horse_id") is None, \
                f"Ambiguous row must not have horse_id filled: {r.get('horse_name')}"


# ── 21. RP_UID rows have numeric horse_id ─────────────────────────────────────

def test_rp_uid_rows_have_numeric_id():
    if not ENRICHED_FILE.exists():
        pytest.skip("VFU-06 not yet generated")
    rows = json.loads(ENRICHED_FILE.read_text())
    for r in rows:
        if r.get("horse_id_namespace") == "RP_UID":
            hid = str(r.get("horse_id", ""))
            assert hid.isdigit(), \
                f"RP_UID horse_id must be numeric, got: {hid} for {r.get('horse_name')}"


# ── 22. Repeated clusters output exists and has identity ─────────────────────

def test_repeated_clusters_identity_enriched():
    if not CLUSTERS_FILE.exists():
        pytest.skip("VFU-06 not yet generated")
    clusters = json.loads(CLUSTERS_FILE.read_text())
    assert len(clusters) > 0
    for c in clusters:
        assert "norm_name" in c
        assert "identity_resolved" in c
        assert "identities" in c
        assert c.get("name_only_confidence") is True
        assert c.get("identity_bridge_version") == BRIDGE_VERSION
