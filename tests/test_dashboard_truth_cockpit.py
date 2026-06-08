"""
Tests for Dashboard Truth Cockpit Phase 1.
Verifies the /api/dashboard/truth-summary endpoint and the dashboard index.html.
"""
import pytest
import os
import pathlib
import json
import ast
from fastapi.testclient import TestClient

# Mock settings if needed, but we can test the live app if we're careful.
# Since we're in the real environment, we'll import the actual app.
from app.main import app

client = TestClient(app)

def test_truth_summary_get_only():
    """Requirement A: Verify the endpoint is GET-only."""
    response = client.get("/api/dashboard/truth-summary")
    assert response.status_code == 200
    
    # POST should be disallowed (or at least not implemented for this path)
    response_post = client.post("/api/dashboard/truth-summary")
    assert response_post.status_code == 405

def test_truth_summary_read_only():
    """Requirement B: Verify the endpoint does not mutate files."""
    # This is a bit hard to prove with a test, but we can check if any new files
    # are created in data/ after a GET request.
    data_dir = pathlib.Path("data")
    initial_files = set(data_dir.glob("*"))
    
    client.get("/api/dashboard/truth-summary")
    
    final_files = set(data_dir.glob("*"))
    assert initial_files == final_files, "New files created during GET request"

def test_no_heavy_imports_in_endpoint():
    """Requirement C: Verify endpoint does not import heavy modules."""
    # We'll check the AST of app/main.py for the dashboard_truth_summary function
    # and ensure it doesn't contain local imports of banned modules.
    main_path = pathlib.Path("app/main.py")
    tree = ast.parse(main_path.read_text(encoding="utf-8"))
    
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "dashboard_truth_summary":
            # Check for local imports in this function
            for subnode in ast.walk(node):
                if isinstance(subnode, (ast.Import, ast.ImportFrom)):
                    # Check what's being imported
                    if isinstance(subnode, ast.Import):
                        names = [alias.name for alias in subnode.names]
                    else:
                        names = [subnode.module]
                    
                    banned = ["app.services.feature_engineering", "app.services.model_manager", "workers.velo_vox", "app.engine.staking"]
                    for name in names:
                        if name in banned:
                            pytest.fail(f"Banned import '{name}' found in dashboard_truth_summary")

def test_missing_artifacts_return_unknown():
    """Requirement D: Verify missing artifacts return UNKNOWN/MISSING."""
    # We'll request a date far in the future
    response = client.get("/api/dashboard/truth-summary?date=2099-01-01")
    assert response.status_code == 200
    data = response.json()
    
    assert data["live_velo_status"] == "UNKNOWN"
    assert data["observability_status"] == "MISSING"
    assert data["sigma_status"] == "MISSING"
    assert data["new_build_status"] == "MISSING"
    assert data["races_scored"] == 0

def test_source_audit_report_exists():
    """Requirement E: Verify dashboard source audit report exists."""
    assert pathlib.Path("data/dashboard/reports/dashboard_truth_source_audit_latest.json").exists()
    assert pathlib.Path("data/dashboard/reports/dashboard_truth_source_audit_latest.md").exists()

def test_dashboard_panel_references_endpoint():
    """Requirement F: Verify dashboard panel references the truth-summary endpoint."""
    index_path = pathlib.Path("app/static/dashboard/index.html")
    content = index_path.read_text(encoding="utf-8")
    assert "/api/dashboard/truth-summary" in content

def test_typo_patch_applied():
    """Requirement G: Verify typo patch applied."""
    doc_path = pathlib.Path("docs/engineering/VELO_PROBABILITY_AND_STATE_ENGINE_V1.md")
    content = doc_path.read_text(encoding="utf-8")
    assert "campaign" in content
    assert "kampaign" not in content

if __name__ == "__main__":
    pytest.main([__file__])
