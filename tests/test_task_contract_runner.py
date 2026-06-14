import pytest
import json
import subprocess
import os
from pathlib import Path
from scripts.ops.task_contract_runner import (
    TASK_CONTRACT_OK, TASK_CONTRACT_MISSING, TASK_CONTRACT_INVALID_JSON,
    TASK_CONTRACT_FORBIDDEN_PATH_TOUCHED, TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED,
    TASK_CONTRACT_FORBIDDEN_KEYWORD_FOUND, TASK_CONTRACT_CLASSIFICATION_MISSING
)

@pytest.fixture
def temp_git_repo(tmp_path):
    """Creates a temporary git repository for testing."""
    repo_dir = tmp_path / "test_task_repo"
    repo_dir.mkdir()
    
    def run_git(args):
        return subprocess.check_output(["git"] + args, cwd=repo_dir, text=True).strip()
    
    run_git(["init", "-b", "main"])
    run_git(["config", "user.email", "test@example.com"])
    run_git(["config", "user.name", "Test User"])
    
    (repo_dir / "README.md").write_text("initial")
    run_git(["add", "README.md"])
    run_git(["commit", "-m", "initial"])
    
    return repo_dir

@pytest.fixture
def base_contract():
    return {
        "task_id": "TEST-TASK",
        "allowed_paths": ["allowed.py", "docs/", "contract.json", "cls.txt"],
        "forbidden_paths": ["src/secret/"],
        "forbidden_keywords": ["SECRET_KEY", "INTERNAL_API"],
        "classification_required": ["NO_LEAK", "SAFETY_OK"]
    }

def test_valid_contract_success(temp_git_repo, base_contract, tmp_path):
    """1. Valid contract with only allowed files returns TASK_CONTRACT_OK and PASS."""
    contract_path = temp_git_repo / "contract.json"
    contract_path.write_text(json.dumps(base_contract))
    
    # Make allowed change
    (temp_git_repo / "allowed.py").write_text("print('hello')")
    
    # Classification file
    cls_path = temp_git_repo / "cls.txt"
    cls_path.write_text("NO_LEAK SAFETY_OK")
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--classification-file", "cls.txt"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "PASS"
    assert data["state"] == TASK_CONTRACT_OK

def test_missing_contract(temp_git_repo):
    """2. Missing contract returns TASK_CONTRACT_MISSING and FAIL."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "non_existent.json"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["state"] == TASK_CONTRACT_MISSING

def test_invalid_json_contract(temp_git_repo):
    """3. Invalid JSON returns TASK_CONTRACT_INVALID_JSON and FAIL."""
    contract_path = temp_git_repo / "bad.json"
    contract_path.write_text("{ broken }")
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "bad.json"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["state"] == TASK_CONTRACT_INVALID_JSON

def test_forbidden_path_touched(temp_git_repo, base_contract):
    """4. Forbidden path touched returns TASK_CONTRACT_FORBIDDEN_PATH_TOUCHED and non-PASS."""
    contract_path = temp_git_repo / "contract.json"
    contract_path.write_text(json.dumps(base_contract))
    
    (temp_git_repo / "src").mkdir()
    (temp_git_repo / "src" / "secret").mkdir()
    (temp_git_repo / "src" / "secret" / "key.txt").write_text("leak")
    
    # Classification file to pass that check
    cls_path = temp_git_repo / "cls.txt"
    cls_path.write_text("NO_LEAK SAFETY_OK")
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--classification-file", "cls.txt"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["state"] == TASK_CONTRACT_FORBIDDEN_PATH_TOUCHED
    assert "src/secret/key.txt" in data["forbidden_path_hits"]

def test_out_of_scope_path_touched(temp_git_repo, base_contract):
    """5. Out-of-scope path touched returns TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED and non-PASS."""
    contract_path = temp_git_repo / "contract.json"
    contract_path.write_text(json.dumps(base_contract))
    
    (temp_git_repo / "random.txt").write_text("not allowed")
    
    # Classification file to pass that check
    cls_path = temp_git_repo / "cls.txt"
    cls_path.write_text("NO_LEAK SAFETY_OK")
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--classification-file", "cls.txt"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["state"] == TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED
    assert "random.txt" in data["out_of_scope_hits"]

def test_forbidden_keyword_found(temp_git_repo, base_contract):
    """6. Forbidden keyword in diff returns TASK_CONTRACT_FORBIDDEN_KEYWORD_FOUND and non-PASS."""
    contract_path = temp_git_repo / "contract.json"
    contract_path.write_text(json.dumps(base_contract))
    
    (temp_git_repo / "allowed.py").write_text("SECRET_KEY = '123'")
    
    # Classification file to pass that check
    cls_path = temp_git_repo / "cls.txt"
    cls_path.write_text("NO_LEAK SAFETY_OK")
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--classification-file", "cls.txt"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["state"] == TASK_CONTRACT_FORBIDDEN_KEYWORD_FOUND
    assert "SECRET_KEY" in data["forbidden_keyword_hits"]

def test_missing_classification(temp_git_repo, base_contract):
    """7. Missing required classification returns TASK_CONTRACT_CLASSIFICATION_MISSING and non-PASS."""
    contract_path = temp_git_repo / "contract.json"
    contract_path.write_text(json.dumps(base_contract))
    
    (temp_git_repo / "allowed.py").write_text("ok")
    cls_path = temp_git_repo / "cls.txt"
    cls_path.write_text("NO_LEAK") # missing SAFETY_OK
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--classification-file", "cls.txt"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = json.loads(res.stdout)
    assert data["state"] == TASK_CONTRACT_CLASSIFICATION_MISSING
    assert "SAFETY_OK" in data["classification_missing"]

def test_artifact_written(temp_git_repo, base_contract, tmp_path):
    """9. JSON artifact is written."""
    contract_path = temp_git_repo / "contract.json"
    contract_path.write_text(json.dumps(base_contract))
    output_json = tmp_path / "task_latest.json"
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--output", str(output_json),
        "--mode", "preflight"
    ], cwd=temp_git_repo, env=env)
    
    assert output_json.exists()
    data = json.loads(output_json.read_text())
    assert data["task_id"] == "TEST-TASK"

def test_json_schema_completeness(temp_git_repo, base_contract, tmp_path):
    """10. JSON output schema completeness."""
    contract_path = temp_git_repo / "contract.json"
    contract_path.write_text(json.dumps(base_contract))
    output_json = tmp_path / "schema_task.json"
    
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "task_contract_runner.py"
    env = os.environ.copy()
    env["VELO_TASK_ROOT"] = str(temp_git_repo)
    
    subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--output", str(output_json),
        "--mode", "preflight"
    ], cwd=temp_git_repo, env=env)
    
    with open(output_json) as f:
        data = json.load(f)
    
    keys = [
        "status", "state", "task_id", "contract_path", "base_ref", 
        "changed_files", "forbidden_path_hits", "out_of_scope_hits", 
        "forbidden_keyword_hits", "classification_required", 
        "classification_missing", "errors", "created_at"
    ]
    for key in keys:
        assert key in data, f"Missing key in JSON: {key}"

