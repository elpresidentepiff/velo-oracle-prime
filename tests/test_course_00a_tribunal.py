"""
Tests for COURSE-00A — Source Provenance Tribunal and Stale Fact Correction.
Verifies: stale facts caught, unsourced claims downgraded, no false proven claims,
Southwell corrected, hard constraints held.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "ops"))
import build_course_00a_tribunal as _course_00a_mod  # type: ignore[import]
from build_course_00a_tribunal import (  # type: ignore[import]
    _BHA_RP_SOURCE_MAP,
    _COURSE_00_CLAIMS,
    _FINAL_CLASSIFICATIONS,
    _HARD_CONSTRAINTS,
    _VERIFIED_REGISTRY,
    _s1_extract_claims,
    _s2_surface_audit,
    _s3_draw_audit,
    _s4_pace_audit,
    _s5_bha_rp_reality,
    _s6_corrections,
    _s7_verified_registry,
)

# ── T-01: No banned imports / calls ───────────────────────────────────────────


def test_no_supabase_import() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00a_tribunal.py").read_text()
    for banned in ["import supabase", "from supabase"]:
        assert banned not in src


def test_no_telegram_import() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00a_tribunal.py").read_text()
    for banned in ["import telegram", "from telegram"]:
        assert banned not in src


def test_no_model_mutation_calls() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00a_tribunal.py").read_text()
    for banned in ["promote_model(", "place_order(", "score_race("]:
        assert banned not in src


def test_no_external_url_requests() -> None:
    src = (Path(__file__).parent.parent / "scripts" / "ops" / "build_course_00a_tribunal.py").read_text()
    for banned in ["requests.get(", "urllib.request.urlopen("]:
        assert banned not in src


# ── T-02: Hard constraints and classifications ─────────────────────────────────


def test_hard_constraints_present() -> None:
    required = {
        "REPORT_ONLY",
        "NO_SUPABASE_WRITES",
        "NO_TELEGRAM_SEND",
        "COURSE_FACTS_REQUIRE_PROVENANCE",
        "UNSOURCED_COURSE_FACTS_DOWNGRADED_TO_UNKNOWN",
        "STALE_COURSE_FACTS_CORRECTED_OR_QUARANTINED",
        "SOURCE_SECTION_EXISTS_IS_NOT_PROOF",
        "HYPOTHESES_ARE_NOT_FACTS",
    }
    assert required.issubset(set(_HARD_CONSTRAINTS))


def test_final_classifications_complete() -> None:
    required = {
        "COURSE_00A_SOURCE_PROVENANCE_TRIBUNAL_COMPLETE",
        "SOUTHWELL_SURFACE_STALE_FACT_REVIEWED",
        "STALE_FACTS_CORRECTED_OR_QUARANTINED",
        "UNSOURCED_CLAIMS_DOWNGRADED",
        "HYPOTHESES_NOT_PROMOTED_TO_FACTS",
        "SOURCE_SECTION_EXISTS_NOT_TREATED_AS_PROOF",
        "COURSE_01_REQUIRES_PROVENANCE_FIELDS",
        "REPORT_ONLY",
    }
    assert required.issubset(set(_FINAL_CLASSIFICATIONS))


# ── T-03: Every claim has required provenance fields ──────────────────────────


def test_every_claim_has_evidence_status() -> None:
    claims = _s1_extract_claims()
    assert len(claims) >= 10
    for c in claims:
        assert "evidence_status" in c, f"Claim missing evidence_status: {c.get('course')} {c.get('claim_type')}"
        assert c["evidence_status"], "evidence_status cannot be empty"


def test_every_claim_has_action() -> None:
    claims = _s1_extract_claims()
    valid_actions = {"KEEP", "CORRECT", "DOWNGRADE_TO_UNKNOWN", "DOWNGRADE_TO_HYPOTHESIS", "QUARANTINE"}
    for c in claims:
        assert "action" in c, f"Claim missing action: {c.get('course')}"
        assert c["action"] in valid_actions, f"Invalid action: {c['action']}"


def test_every_claim_has_course_and_type() -> None:
    claims = _s1_extract_claims()
    for c in claims:
        assert c.get("course"), "Claim missing course"
        assert c.get("claim_type"), "Claim missing claim_type"


# ── T-04: Southwell surface stale fact ────────────────────────────────────────


def test_southwell_fibresand_flagged_stale() -> None:
    claims = _s1_extract_claims()
    southwell_surface = [c for c in claims if c["course"] == "Southwell (AW)" and c["claim_type"] == "surface"]
    assert len(southwell_surface) >= 1, "No Southwell surface claim found"
    stale_claims = [c for c in southwell_surface if c["evidence_status"] == "STALE"]
    assert len(stale_claims) >= 1, "Southwell Fibresand not flagged as STALE"


def test_southwell_corrected_to_tapeta() -> None:
    claims = _s1_extract_claims()
    southwell_surface = [
        c
        for c in claims
        if c["course"] == "Southwell (AW)" and c["claim_type"] == "surface" and c["evidence_status"] == "STALE"
    ]
    assert len(southwell_surface) >= 1
    claim = southwell_surface[0]
    assert "Tapeta" in str(claim.get("corrected_value", "")), (
        f"Southwell not corrected to Tapeta, got: {claim.get('corrected_value')}"
    )
    assert claim["action"] == "CORRECT"


def test_s2_southwell_stale_detected() -> None:
    claims = _s1_extract_claims()
    s2 = _s2_surface_audit(claims)
    assert s2["southwell_stale"] is True
    assert "Tapeta" in s2["southwell_corrected_to"]
    assert s2["stale_count"] >= 1
    assert s2["corrected_count"] >= 1


# ── T-05: Draw claims all downgraded to hypothesis ────────────────────────────


def test_draw_claims_mostly_hypothesis() -> None:
    claims = _s1_extract_claims()
    s3 = _s3_draw_audit(claims)
    assert s3["total_draw_claims"] >= 5
    # Majority must be downgraded (not verified local)
    assert s3["verified_count"] == 0, f"Draw claims should have 0 VERIFIED_LOCAL, got {s3['verified_count']}"
    assert s3["hypothesis_count"] >= s3["total_draw_claims"] - 2, "Most draw claims must be downgraded to hypothesis"


def test_no_draw_claim_verified_local() -> None:
    claims = _s1_extract_claims()
    draw_claims = [c for c in claims if c["claim_type"] == "draw_bias_direction"]
    verified_local = [c for c in draw_claims if c["evidence_status"] == "VERIFIED_LOCAL"]
    assert len(verified_local) == 0, (
        f"No draw claim can be VERIFIED_LOCAL — no local draw data in pipeline. Got: {[c['course'] for c in verified_local]}"
    )


# ── T-06: Pace claims all downgraded to hypothesis ────────────────────────────


def test_pace_claims_all_hypothesis() -> None:
    claims = _s1_extract_claims()
    s4 = _s4_pace_audit(claims)
    assert s4["total_pace_claims"] >= 3
    assert s4["local_running_style_data"] is False
    assert s4["hypothesis_count"] == s4["total_pace_claims"], (
        f"ALL pace claims must be HYPOTHESIS. Got {s4['hypothesis_count']}/{s4['total_pace_claims']}"
    )


def test_pace_verdict_hypothesis_only() -> None:
    claims = _s1_extract_claims()
    s4 = _s4_pace_audit(claims)
    assert "HYPOTHESIS" in s4["verdict"]


# ── T-07: BHA/RP source map — no false proven ────────────────────────────────


def test_bha_rp_map_no_false_proven() -> None:
    s5 = _s5_bha_rp_reality()
    assert len(s5) >= 8
    for entry in s5:
        bha = entry.get("bha_status", "")
        local = entry.get("local_status", "")
        # If not local present, cannot claim PROVEN_ACCESSIBLE_NOW from BHA/RP
        # unless it's a truly public field like course name
        if bha == "PROVEN_ACCESSIBLE_NOW" and local != "LOCAL_PRESENT":
            field = entry.get("field", "")
            # Allow publicly accessible BHA fields (course name, OR ratings database)
            publicly_accessible = {"course", "OR"}
            assert field in publicly_accessible, (
                f"Field '{field}' claims BHA PROVEN but is not LOCAL_PRESENT and not a known public BHA field"
            )


def test_surface_not_proven_locally() -> None:
    s5 = _s5_bha_rp_reality()
    surface_entries = [e for e in s5 if e.get("field") == "surface"]
    if surface_entries:
        assert surface_entries[0].get("local_status") in ("LOCAL_ABSENT", "LOCAL_MISSING"), (
            "Surface should be LOCAL_ABSENT — not captured in local pipeline"
        )


# ── T-08: Corrections summary ─────────────────────────────────────────────────


def test_corrections_tally_consistent() -> None:
    claims = _s1_extract_claims()
    s6 = _s6_corrections(claims)
    total = s6["keep"] + s6["correct"] + s6["downgrade"] + s6["quarantine"]
    assert total == s6["total_claims"], f"Tally mismatch: {total} vs {s6['total_claims']}"


def test_at_least_one_correction() -> None:
    claims = _s1_extract_claims()
    s6 = _s6_corrections(claims)
    assert s6["correct"] >= 1, "Must have at least 1 stale fact corrected (Southwell)"


def test_at_least_five_downgrades() -> None:
    claims = _s1_extract_claims()
    s6 = _s6_corrections(claims)
    assert s6["downgrade"] >= 5, f"Expected 5+ downgrades (draw+pace claims), got {s6['downgrade']}"


# ── T-09: Verified registry — provenance fields on every entry ────────────────


def test_verified_registry_has_entries() -> None:
    s7 = _s7_verified_registry()
    assert len(s7) >= 5


def test_verified_registry_provenance_fields() -> None:
    s7 = _s7_verified_registry()
    required = {
        "course",
        "surface_current",
        "surface_source_status",
        "draw_bias_direction",
        "draw_bias_source_status",
        "confidence",
        "tribunal_verdict",
    }
    for entry in s7:
        missing = required - set(entry.keys())
        assert not missing, f"Registry entry {entry.get('course')} missing: {missing}"


def test_verified_registry_no_hypothesis_as_verified() -> None:
    s7 = _s7_verified_registry()
    for entry in s7:
        draw_status = entry.get("draw_bias_source_status", "")
        pace_status = entry.get("pace_source_status", "")
        # Draw and pace must never be VERIFIED_LOCAL in registry
        assert draw_status != "VERIFIED_LOCAL", (
            f"{entry.get('course')} draw status claims VERIFIED_LOCAL — impossible without local draw data"
        )
        assert pace_status != "VERIFIED_LOCAL", (
            f"{entry.get('course')} pace status claims VERIFIED_LOCAL — impossible without running-style data"
        )


def test_southwell_in_verified_registry() -> None:
    s7 = _s7_verified_registry()
    southwell = [e for e in s7 if e.get("course") == "Southwell (AW)"]
    assert len(southwell) >= 1, "Southwell (AW) must be in verified registry"
    entry = southwell[0]
    assert entry.get("surface_current") == "Tapeta", (
        f"Southwell surface should be Tapeta in registry, got: {entry.get('surface_current')}"
    )
    assert "STALE" in str(entry.get("tribunal_verdict", "")), (
        "Southwell registry entry should note stale fact in tribunal_verdict"
    )


# ── T-10: Output files ────────────────────────────────────────────────────────


def test_output_files_written(tmp_path, monkeypatch) -> None:
    """
    Self-contained: runs main() against a monkeypatched REPO_ROOT so this
    test never depends on checked-in data/reports outputs.
    """
    monkeypatch.setattr(_course_00a_mod, "REPO_ROOT", str(tmp_path))
    _course_00a_mod.main()

    required = [
        "data/reports/course_00a_source_provenance_tribunal.md",
        "data/reports/course_00a_source_provenance_tribunal.json",
        "data/reports/course_00a_course_fact_provenance_table.csv",
        "data/reports/course_00a_stale_fact_corrections.csv",
        "data/reports/course_00a_unsourced_claims_quarantine.csv",
        "data/reports/course_00a_verified_course_registry.csv",
        "data/reports/course_00a_operator_brief.md",
    ]
    for f in required:
        path = tmp_path / f
        assert path.exists(), f"Missing: {f}"
        assert path.stat().st_size > 0, f"Empty: {f}"


def test_stale_corrections_csv_has_southwell() -> None:
    path = Path(__file__).parent.parent / "data/reports/course_00a_stale_fact_corrections.csv"
    if path.exists():
        content = path.read_text()
        assert "Southwell" in content, "Southwell stale fact must appear in corrections CSV"
        assert "Tapeta" in content, "Corrected value Tapeta must appear in corrections CSV"


def test_quarantine_csv_has_draw_claims() -> None:
    path = Path(__file__).parent.parent / "data/reports/course_00a_unsourced_claims_quarantine.csv"
    if path.exists():
        content = path.read_text()
        assert "draw_bias" in content or "front_runner" in content, (
            "Quarantine CSV must contain draw/pace downgraded claims"
        )


def test_json_has_final_classifications() -> None:
    path = Path(__file__).parent.parent / "data/reports/course_00a_source_provenance_tribunal.json"
    if path.exists():
        data = json.loads(path.read_text())
        meta = data.get("meta", {})
        fc = meta.get("final_classifications", [])
        assert "COURSE_00A_SOURCE_PROVENANCE_TRIBUNAL_COMPLETE" in fc
        assert "SOUTHWELL_SURFACE_STALE_FACT_REVIEWED" in fc
        assert "REPORT_ONLY" in fc
