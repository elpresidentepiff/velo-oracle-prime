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
        # Modes check
        modes = data["modes"]
        assert modes["execution_mode"] in ("PAPER", "ARCHIVE", "LIVE")
        assert modes["betfair_mode"] in ("PAPER", "ARCHIVE", "LIVE")

def test_execution_mode_live_blocks_startup(monkeypatch):
    """Verify that startup fails if VELO_EXECUTION_MODE=LIVE is active."""
    from app.main import lifespan
    from fastapi import FastAPI
    import asyncio
    
    app = FastAPI(lifespan=lifespan)
    monkeypatch.setenv("VELO_EXECUTION_MODE", "LIVE")
    
    with pytest.raises(RuntimeError, match="BLOCKED: VELO_EXECUTION_MODE=LIVE"):
        asyncio.run(lifespan(app).__aenter__())

def test_betfair_mode_live_blocks_startup(monkeypatch):
    """Verify that startup fails if BETFAIR_MODE=LIVE is active."""
    from app.main import lifespan
    from fastapi import FastAPI
    import asyncio
    
    app = FastAPI(lifespan=lifespan)
    monkeypatch.setenv("BETFAIR_MODE", "LIVE")
    
    with pytest.raises(RuntimeError, match="BLOCKED: BETFAIR_MODE=LIVE"):
        asyncio.run(lifespan(app).__aenter__())

def test_pipeline_wrappers_resolve():
    """Verify that canonical pipeline wrappers exist and are loadable."""
    wrappers = [
        ("Daily Scoring", ROOT / "app" / "pipelines" / "score_daily_runner.py"),
        ("Sigma Reconciliation", ROOT / "app" / "pipelines" / "sigma_runner.py"),
        ("Results Ingestion", ROOT / "app" / "pipelines" / "results_ingest_runner.py")
    ]
    for name, path in wrappers:
        assert path.exists(), f"Missing canonical wrapper for {name}: {path.name}"

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
