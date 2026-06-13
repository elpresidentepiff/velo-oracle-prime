import pytest
import json
import os
import subprocess
from pathlib import Path

@pytest.fixture
def mock_root(tmp_path):
    root = tmp_path / "mock_hardening"
    root.mkdir()
    (root / "docs" / "current").mkdir(parents=True)
    (root / "data" / "current").mkdir(parents=True)
    
    # Create the script in mock root
    src_root = Path(__file__).resolve().parents[1]
    content = (src_root / "scripts" / "ops" / "verify_hardening_state.py").read_text()
    (root / "verify.py").write_text(content)
    
    return root

def _load_json_from_stdout(stdout: str) -> dict:
    import re
    matches = list(re.finditer(r'\{.*\}', stdout, re.DOTALL))
    if not matches:
        raise ValueError(f"No JSON found in: {stdout}")
    return json.loads(matches[-1].group(0))

def test_verifier_passes_when_valid(mock_root):
    log_path = mock_root / "docs/current/VELO_HARDENING_STATE.md"
    log_path.write_text("""
# Log
- CAPTURE-PROOF (0737443)
- WORKTREE-SAFETY-RUNNER (95e698d)
- TASK-CONTRACT-RUNNER (1f109df)
- SIDE-EFFECT-SENTINEL (ac8760b)
- GOVERNED-TASK-RUNNER (ed8d09d)
- Baseline (5dfd9a5)
""")
    
    env = os.environ.copy()
    env["VELO_HARDENING_ROOT"] = str(mock_root)
    res = subprocess.run(["python3", "verify.py"], cwd=mock_root, capture_output=True, text=True, env=env)
    assert res.returncode == 0
    data = _load_json_from_stdout(res.stdout)
    assert data["status"] == "PASS"
    assert data["state"] == "HARDENING_VERIFIED"

def test_verifier_fails_when_missing_layer(mock_root):
    log_path = mock_root / "docs/current/VELO_HARDENING_STATE.md"
    log_path.write_text("Missing everything")
    
    env = os.environ.copy()
    env["VELO_HARDENING_ROOT"] = str(mock_root)
    res = subprocess.run(["python3", "verify.py"], cwd=mock_root, capture_output=True, text=True, env=env)
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["status"] == "FAIL"
    assert "CAPTURE_PROOF" in data["missing_layers"]

def test_verifier_fails_when_file_missing(mock_root):
    env = os.environ.copy()
    env["VELO_HARDENING_ROOT"] = str(mock_root)
    res = subprocess.run(["python3", "verify.py"], cwd=mock_root, capture_output=True, text=True, env=env)
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == "LOG_MISSING"

def test_artifact_written(mock_root):
    log_path = mock_root / "docs/current/VELO_HARDENING_STATE.md"
    log_path.write_text("dummy")
    env = os.environ.copy()
    env["VELO_HARDENING_ROOT"] = str(mock_root)
    subprocess.run(["python3", "verify.py"], cwd=mock_root, env=env)
    
    assert (mock_root / "data/current/hardening_state_check_latest.json").exists()

def test_p1_2_contract_valid():
    contract_path = Path(__file__).resolve().parents[1] / "ops" / "task_contracts" / "P1-2.json"
    assert contract_path.exists()
    data = json.loads(contract_path.read_text())
    assert data["task_id"] == "P1-2"
    for cls in ["NO_LIVE_SCORING_CHANGE", "NO_SUPABASE_WRITES", "NO_MODEL_PROMOTION", "NO_TELEGRAM_SEND"]:
        assert cls in data["classification_required"]
