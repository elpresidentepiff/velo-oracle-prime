import pytest
import json
import subprocess
import os
from pathlib import Path

@pytest.fixture
def test_env(tmp_path):
    """Sets up a mock environment with safety runners available."""
    # We need real runners because the governor calls them via sys.executable
    # But we want to isolate the ROOT for the tests
    root = tmp_path / "governor_test_root"
    root.mkdir()
    
    # Create necessary dirs
    (root / "scripts" / "ops").mkdir(parents=True)
    (root / "data" / "current").mkdir(parents=True)
    (root / "ops" / "task_contracts").mkdir(parents=True)
    
    # Copy real runners to mock root
    src_root = Path(__file__).resolve().parents[1]
    for script in ["worktree_safety_runner.py", "task_contract_runner.py", "side_effect_sentinel.py", "governed_task_runner.py"]:
        script_src = src_root / "scripts" / "ops" / script
        if script_src.exists():
            content = script_src.read_text()
            (root / "scripts" / "ops" / script).write_text(content)
            (root / "scripts" / "ops" / script).chmod(0o755)

    # Initialize mock git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=root)
    subprocess.run(["git", "config", "user.email", "test@governor.com"], cwd=root)
    subprocess.run(["git", "config", "user.name", "Governor Test"], cwd=root)
    
    # Commit everything
    subprocess.run(["git", "add", "."], cwd=root)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root)
    
    return root

def test_governor_success_chain(test_env):
    """Governed task runner succeeds when all gates pass."""
    contract_data = {
        "task_id": "TEST-CHAIN",
        "allowed_paths": ["README.md", "task.txt", "contract.json", "cls.txt", "data/current/"],
        "forbidden_paths": ["src/secret/"],
        "forbidden_keywords": ["FAIL_ME"],
        "classification_required": ["GOVERNED_OK"]
    }
    (test_env / "contract.json").write_text(json.dumps(contract_data))
    (test_env / "cls.txt").write_text("GOVERNED_OK NO_LIVE_SCORING_CHANGE NO_SUPABASE_WRITES NO_MODEL_PROMOTION NO_TELEGRAM_SEND")
    
    # Commit these to keep worktree clean
    subprocess.run(["git", "add", "contract.json", "cls.txt"], cwd=test_env)
    subprocess.run(["git", "commit", "-m", "add test assets"], cwd=test_env)
    
    script_path = test_env / "scripts" / "ops" / "governed_task_runner.py"
    
    # Set env vars for the sub-runners
    env = os.environ.copy()
    env["VELO_SAFETY_ROOT"] = str(test_env)
    env["VELO_TASK_ROOT"] = str(test_env)
    env["VELO_SENTINEL_ROOT"] = str(test_env)
    env["VELO_GOVERNOR_ROOT"] = str(test_env)
    env["VELO_HARDENING_ROOT"] = str(test_env)
    env["VELO_TEST_GIT"] = "1"
    
    res = subprocess.run([
        "python3", str(script_path),
        "--expected-branch", "main",
        "--contract", "contract.json",
        "--classification-file", "cls.txt",
        "--", "echo", "governed-success"
    ], cwd=test_env, capture_output=True, text=True, env=env)
    
    assert res.returncode == 0
    assert "SUCCESS: Task governed and verified" in res.stdout
    
    # Verify artifact
    artifact_path = test_env / "data" / "current" / "governed_task_latest.json"
    assert artifact_path.exists()
    data = json.loads(artifact_path.read_text())
    assert data["status"] == "PASS"

def test_governor_blocks_dirty_worktree(test_env):
    """Governor blocks execution if worktree is dirty."""
    contract_data = {
        "task_id": "TEST-BLOCK",
        "allowed_paths": ["README.md", "data/current/"],
        "forbidden_paths": [],
        "forbidden_keywords": [],
        "classification_required": []
    }
    (test_env / "contract.json").write_text(json.dumps(contract_data))
    subprocess.run(["git", "add", "contract.json"], cwd=test_env)
    subprocess.run(["git", "commit", "-m", "add contract"], cwd=test_env)
    
    # Make dirty
    (test_env / "dirty.txt").write_text("dirty")
    
    script_path = test_env / "scripts" / "ops" / "governed_task_runner.py"
    env = os.environ.copy()
    env["VELO_SAFETY_ROOT"] = str(test_env)
    env["VELO_TASK_ROOT"] = str(test_env)
    env["VELO_SENTINEL_ROOT"] = str(test_env)
    env["VELO_GOVERNOR_ROOT"] = str(test_env)
    env["VELO_TEST_GIT"] = "1"

    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--", "echo", "should-not-run"
    ], cwd=test_env, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    assert "ABORTED: WORKTREE_SAFETY_FAILED" in res.stdout

def test_governor_fails_on_post_audit_violation(test_env):
    """Governor fails if the task violates the contract during execution."""
    contract_data = {
        "task_id": "TEST-VIOLATE",
        "allowed_paths": ["README.md", "contract.json", "cls.txt", "data/current/"], # out_of_scope.txt NOT allowed
        "forbidden_paths": [],
        "forbidden_keywords": [],
        "classification_required": []
    }
    (test_env / "contract.json").write_text(json.dumps(contract_data))
    (test_env / "cls.txt").write_text("NO_LIVE_SCORING_CHANGE NO_SUPABASE_WRITES NO_MODEL_PROMOTION NO_TELEGRAM_SEND")
    subprocess.run(["git", "add", "contract.json", "cls.txt"], cwd=test_env)
    subprocess.run(["git", "commit", "-m", "add assets"], cwd=test_env)
    
    script_path = test_env / "scripts" / "ops" / "governed_task_runner.py"
    env = os.environ.copy()
    env["VELO_SAFETY_ROOT"] = str(test_env)
    env["VELO_TASK_ROOT"] = str(test_env)
    env["VELO_SENTINEL_ROOT"] = str(test_env)
    env["VELO_GOVERNOR_ROOT"] = str(test_env)
    env["VELO_TEST_GIT"] = "1"

    # Command will create an out-of-scope file
    res = subprocess.run([
        "python3", str(script_path),
        "--contract", "contract.json",
        "--classification-file", "cls.txt",
        "--", "touch", "out_of_scope.txt"
    ], cwd=test_env, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    assert "FAILURE: Task final audit failed" in res.stdout
    
    artifact_path = test_env / "data" / "current" / "governed_task_latest.json"
    data = json.loads(artifact_path.read_text())
    assert data["status"] == "FAIL"
    assert data["results"]["contract_audit"]["state"] == "TASK_CONTRACT_OUT_OF_SCOPE_PATH_TOUCHED"
