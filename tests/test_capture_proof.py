import pytest
import json
import os
from pathlib import Path
from scripts.ops.capture_proof import CaptureProof, CAPTURE_UNKNOWN_ERROR, CAPTURE_DOWNLOAD_MISSING, audit_manifest

def test_capture_proof_schema():
    """1. JSON schema/required fields."""
    proof = CaptureProof(date_str="2026-06-11", source="rp")
    data = proof.save()
    
    required_fields = [
        "date", "source", "status", "started_at", "finished_at",
        "browser_engine", "url_count", "pages_reached",
        "screenshots_written", "dom_snapshots_written",
        "downloads_expected", "downloads_found",
        "session_detected", "login_detected",
        "redaction_applied", "errors", "artifacts"
    ]
    for field in required_fields:
        assert field in data

def test_failure_never_becomes_pass():
    """2. Unknown/failure never becomes PASS."""
    proof = CaptureProof(date_str="2026-06-11")
    proof.add_error(CAPTURE_UNKNOWN_ERROR, "Test Error")
    data = proof.save()
    assert data["status"] != "PASS"
    assert data["status"] == "FAIL"

def test_redaction_flag():
    """3. Redaction flag exists and works."""
    proof = CaptureProof(date_str="2026-06-11")
    text = "Contact us at test@example.com"
    redacted = proof.apply_redaction(text)
    assert "[REDACTED_EMAIL]" in redacted
    assert proof.redaction_applied is True
    data = proof.save()
    assert data["redaction_applied"] is True

def test_artifact_paths_safe():
    """4. Artifact paths are relative and safe."""
    # Note: ROOT is set in the script, we might need to be careful here if testing from different path
    # but the script uses .relative_to(ROOT)
    from scripts.ops.capture_proof import ROOT
    proof = CaptureProof(date_str="2026-06-11")
    test_path = ROOT / "data" / "test_artifact.png"
    # Create dummy file
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.touch()
    
    proof.add_artifact(test_path, "screenshot")
    data = proof.save()
    
    assert data["artifacts"][0]["path"] == "data/test_artifact.png"
    assert data["screenshots_written"] == 1
    
    # Cleanup
    test_path.unlink()

def test_no_supabase_dependency():
    """5. No Supabase writes/imports required."""
    # This is a static check - we verify no 'supabase' string in the file
    path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "capture_proof.py"
    content = path.read_text()
    assert "supabase" not in content.lower()

def test_import_without_browser():
    """6. Script can be imported without launching browser."""
    # If it imported in this test file, it passed.
    assert CaptureProof is not None

def test_missing_download_detection(tmp_path):
    """1. missing expected download/file produces CAPTURE_DOWNLOAD_MISSING
       2. missing expected download/file does not produce CAPTURE_OK"""
    manifest_data = {
        "url_count": 1,
        "captures": [
            {
                "source_url": "https://example.com",
                "status": "PASS",
                "html_path": str(tmp_path / "non_existent.html")
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data))
    
    result = audit_manifest("2026-06-11", manifest_path)
    
    assert result["status"] in ["FAIL", "PARTIAL"]
    assert result["status"] != "PASS"
    assert any(err["code"] == CAPTURE_DOWNLOAD_MISSING for err in result["errors"])

def test_empty_expected_downloads_valid(tmp_path):
    """3. no expected downloads remains valid if manifest declares zero expected downloads"""
    manifest_data = {
        "url_count": 1,
        "captures": [
            {
                "source_url": "https://example.com",
                "status": "PASS"
                # No html_path or screenshot_path
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data))
    
    result = audit_manifest("2026-06-11", manifest_path)
    
    assert result["status"] == "PASS"
    assert result["errors"] == []

