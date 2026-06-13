import pytest
import json
import os
import subprocess
from pathlib import Path

@pytest.fixture
def mock_root(tmp_path):
    root = tmp_path / "mock_branch"
    root.mkdir()
    (root / "docs" / "current").mkdir(parents=True)
    (root / "data" / "current").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    
    # Create the script in mock root
    src_root = Path(__file__).resolve().parents[1]
    content = (src_root / "scripts" / "ops" / "verify_branch_protection_readiness.py").read_text()
    (root / "verify_branch.py").write_text(content)
    
    return root

def _load_json_from_stdout(stdout: str) -> dict:
    import re
    matches = list(re.finditer(r'\{.*\}', stdout, re.DOTALL))
    if not matches:
        raise ValueError(f"No JSON found in: {stdout}")
    return json.loads(matches[-1].group(0))

def test_branch_verifier_passes_when_valid(mock_root):
    # Setup mock files
    (mock_root / ".github/workflows/governed-safety.yml").touch()
    (mock_root / "docs/current/VELO_HARDENING_STATE.md").touch()
    (mock_root / "docs/current/BRANCH_PROTECTION_POLICY.md").write_text("""
# Policy
- governed-safety
- NO_LIVE_SCORING_CHANGE
- NO_SUPABASE_WRITES
- NO_MODEL_PROMOTION
- NO_TELEGRAM_SEND
""")
    
    env = os.environ.copy()
    env["VELO_BRANCH_ROOT"] = str(mock_root)
    res = subprocess.run(["python3", "verify_branch.py"], cwd=mock_root, capture_output=True, text=True, env=env)
    assert res.returncode == 0
    data = _load_json_from_stdout(res.stdout)
    assert data["status"] == "PASS"
    assert data["state"] == "READY"

def test_branch_verifier_fails_when_policy_missing(mock_root):
    (mock_root / ".github/workflows/governed-safety.yml").touch()
    (mock_root / "docs/current/VELO_HARDENING_STATE.md").touch()
    
    env = os.environ.copy()
    env["VELO_BRANCH_ROOT"] = str(mock_root)
    res = subprocess.run(["python3", "verify_branch.py"], cwd=mock_root, capture_output=True, text=True, env=env)
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["status"] == "FAIL"
    assert "Policy doc missing" in data["errors"][0]

def test_branch_verifier_fails_when_incomplete_policy(mock_root):
    (mock_root / ".github/workflows/governed-safety.yml").touch()
    (mock_root / "docs/current/VELO_HARDENING_STATE.md").touch()
    (mock_root / "docs/current/BRANCH_PROTECTION_POLICY.md").write_text("Incomplete")
    
    env = os.environ.copy()
    env["VELO_BRANCH_ROOT"] = str(mock_root)
    res = subprocess.run(["python3", "verify_branch.py"], cwd=mock_root, capture_output=True, text=True, env=env)
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == "INCOMPLETE_POLICY"
    assert "governed-safety" in data["errors"][0]

def test_artifact_written(mock_root):
    (mock_root / ".github/workflows/governed-safety.yml").touch()
    (mock_root / "docs/current/VELO_HARDENING_STATE.md").touch()
    (mock_root / "docs/current/BRANCH_PROTECTION_POLICY.md").write_text("governed-safety NO_LIVE_SCORING_CHANGE NO_SUPABASE_WRITES NO_MODEL_PROMOTION NO_TELEGRAM_SEND")
    
    env = os.environ.copy()
    env["VELO_BRANCH_ROOT"] = str(mock_root)
    subprocess.run(["python3", "verify_branch.py"], cwd=mock_root, env=env)
    
    assert (mock_root / "data/current/branch_protection_readiness_latest.json").exists()
