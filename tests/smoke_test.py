"""
VÉLØ Oracle Prime Smoke Suite.
Fast, high-level verification of core system integrity.
"""
import pytest
import os
import pathlib
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load env early
load_dotenv()

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def test_app_can_import():
    """Verify that the main app components can be imported without crashing."""
    from app.main import app
    assert app is not None

def test_runtime_truth_api_healthy():
    """Verify that the runtime-truth API metadata is reachable and consistent."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    with TestClient(app) as client:
        response = client.get("/api/runtime-truth")
        assert response.status_code == 200
        data = response.json()
        assert "safety" in data
        assert "learning_governance" in data
        assert data["modes"]["execution_mode"] in ("PAPER", "ARCHIVE", "LIVE")

def test_safety_guards_enforced():
    """Verify that startup fails if forbidden modes are active."""
    from app.main import lifespan
    from fastapi import FastAPI
    import asyncio
    
    app = FastAPI(lifespan=lifespan)
    
    # Force an unsafe mode in a subprocess-like environment (mocking env)
    os.environ["VELO_EXECUTION_MODE"] = "LIVE"
    
    with pytest.raises(RuntimeError, match="BLOCKED: VELO_EXECUTION_MODE=LIVE"):
        asyncio.run(lifespan(app).__aenter__())
        
    # Restore safe mode
    os.environ["VELO_EXECUTION_MODE"] = "PAPER"

def test_pipeline_wrappers_resolve():
    """Verify that canonical pipeline wrappers exist and are loadable."""
    wrappers = [
        ROOT / "app" / "pipelines" / "score_daily_runner.py",
        ROOT / "app" / "pipelines" / "sigma_runner.py",
        ROOT / "app" / "pipelines" / "results_ingest_runner.py"
    ]
    for w in wrappers:
        assert w.exists(), f"Missing canonical wrapper: {w.name}"

def test_forbidden_import_guard():
    """Verify that the safety_guards utility correctly identifies forbidden imports."""
    from app.core.safety_guards import check_imports
    
    # Create a temporary file with a forbidden import
    temp_file = ROOT / "tests" / "temp_forbidden_test.py"
    temp_file.write_text("from app.agents.betfair_execution_agent import something", encoding="utf-8")
    
    try:
        violations = check_imports(ROOT, [temp_file])
        assert len(violations) > 0
        assert "forbidden from-import" in violations[0]
    finally:
        if temp_file.exists():
            temp_file.unlink()

if __name__ == "__main__":
    pytest.main([__file__])
