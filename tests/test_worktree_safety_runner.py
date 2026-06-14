import pytest
import json
import subprocess
import os
from pathlib import Path
from scripts.ops.worktree_safety_runner import run_safety_check, WORKTREE_SAFE, WORKTREE_DIRTY, WORKTREE_WRONG_BRANCH, WORKTREE_HEAD_MISMATCH

@pytest.fixture
def temp_git_repo(tmp_path):
    """Creates a temporary git repository for testing."""
    repo_dir = tmp_path / "test_repo"
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

def test_clean_repo_returns_worktree_safe(temp_git_repo):
    """1. Clean repo returns WORKTREE_SAFE."""
    status, state, details = run_safety_check(cwd=temp_git_repo)
    assert status == "PASS"
    assert state == WORKTREE_SAFE
    assert details["is_dirty"] is False

def test_wrong_branch_returns_wrong_branch(temp_git_repo):
    """2. Wrong branch returns WORKTREE_WRONG_BRANCH."""
    status, state, details = run_safety_check(expected_branch="feature/not-main", cwd=temp_git_repo)
    assert status == "FAIL"
    assert state == WORKTREE_WRONG_BRANCH

def test_dirty_staged_file_returns_dirty(temp_git_repo):
    """3. Dirty staged file returns non-PASS."""
    (temp_git_repo / "dirty.txt").write_text("dirty")
    subprocess.run(["git", "add", "dirty.txt"], cwd=temp_git_repo)
    
    status, state, details = run_safety_check(cwd=temp_git_repo)
    assert status == "FAIL"
    assert state == WORKTREE_DIRTY
    assert "dirty.txt" in details["staged_files"]

def test_dirty_unstaged_file_returns_dirty(temp_git_repo):
    """4. Dirty unstaged file returns non-PASS."""
    (temp_git_repo / "README.md").write_text("modified")
    
    status, state, details = run_safety_check(cwd=temp_git_repo)
    assert status == "FAIL"
    assert state == WORKTREE_DIRTY
    assert "README.md" in details["unstaged_files"]

def test_untracked_file_returns_dirty(temp_git_repo):
    """5. Untracked file returns non-PASS unless allowed."""
    (temp_git_repo / "untracked.txt").write_text("new")
    
    # Not allowed
    status, state, details = run_safety_check(cwd=temp_git_repo, allow_untracked=False)
    assert status == "FAIL"
    assert state == WORKTREE_DIRTY
    
    # Allowed
    status, state, details = run_safety_check(cwd=temp_git_repo, allow_untracked=True)
    assert status == "PASS"
    assert state == WORKTREE_SAFE

def test_head_mismatch_returns_mismatch(temp_git_repo):
    """6. HEAD mismatch returns WORKTREE_HEAD_MISMATCH."""
    # Current HEAD
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_git_repo, text=True).strip()
    
    # Check with wrong head
    status, state, details = run_safety_check(expected_head="abcdef1", cwd=temp_git_repo)
    assert status == "FAIL"
    assert state == WORKTREE_HEAD_MISMATCH
    
    # Check with correct head (short)
    short_head = current_head[:7]
    status, state, details = run_safety_check(expected_head=short_head, cwd=temp_git_repo)
    assert status == "PASS"
    assert state == WORKTREE_SAFE

def test_run_mode_execution(temp_git_repo, tmp_path):
    """7. In run mode, unsafe repo blocks command execution.
       8. In run mode, safe repo executes command and records exit code."""
    output_json = tmp_path / "safety.json"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "worktree_safety_runner.py"
    
    # 1. Safe execution
    env = os.environ.copy()
    env["VELO_SAFETY_ROOT"] = str(temp_git_repo)
    env["VELO_TEST_GIT"] = "1"
    
    res = subprocess.run([
        "python3", str(script_path), 
        "--mode", "run", 
        "--output", str(output_json),
        "--", "echo", "hello"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode == 0
    with open(output_json) as f:
        data = json.load(f)
    assert data["status"] == "PASS"
    assert data["command_executed"] is True
    assert data["command_exit_code"] == 0

    # 2. Unsafe execution (dirty)
    (temp_git_repo / "dirty.txt").write_text("dirty")
    res = subprocess.run([
        "python3", str(script_path), 
        "--mode", "run", 
        "--output", str(output_json),
        "--", "echo", "should-not-run"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    with open(output_json) as f:
        data = json.load(f)
    assert data["status"] == "FAIL"
    assert data["command_executed"] is False
    assert "Command BLOCKED" in res.stdout

def test_failing_command_returns_failed(temp_git_repo, tmp_path):
    """9. Failing command returns WORKTREE_COMMAND_FAILED."""
    output_json = tmp_path / "safety.json"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "worktree_safety_runner.py"
    
    env = os.environ.copy()
    env["VELO_SAFETY_ROOT"] = str(temp_git_repo)
    env["VELO_TEST_GIT"] = "1"
    
    res = subprocess.run([
        "python3", str(script_path), 
        "--mode", "run", 
        "--output", str(output_json),
        "--", "false"
    ], cwd=temp_git_repo, capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    with open(output_json) as f:
        data = json.load(f)
    assert data["status"] == "FAIL"
    assert data["state"] == "WORKTREE_COMMAND_FAILED"
    assert data["command_executed"] is True
    assert data["command_exit_code"] != 0

def test_json_artifact_written(temp_git_repo, tmp_path):
    """10. JSON artifact is written."""
    output_json = tmp_path / "test_artifact.json"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "worktree_safety_runner.py"
    
    env = os.environ.copy()
    env["VELO_SAFETY_ROOT"] = str(temp_git_repo)
    env["VELO_TEST_GIT"] = "1"

    subprocess.run([
        "python3", str(script_path), 
        "--mode", "audit", 
        "--output", str(output_json)
    ], cwd=temp_git_repo, env=env)
    
    assert output_json.exists()
    with open(output_json) as f:
        data = json.load(f)
    assert "status" in data
    assert "created_at" in data

def test_json_schema_completeness(temp_git_repo, tmp_path):
    output_json = tmp_path / "schema.json"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "worktree_safety_runner.py"
    
    env = os.environ.copy()
    env["VELO_SAFETY_ROOT"] = str(temp_git_repo)
    env["VELO_TEST_GIT"] = "1"

    subprocess.run([
        "python3", str(script_path), 
        "--mode", "audit", 
        "--output", str(output_json)
    ], cwd=temp_git_repo, env=env)
    
    with open(output_json) as f:
        data = json.load(f)
    
    keys = [
        "status", "state", "branch", "head", "expected_branch", 
        "expected_head", "is_dirty", "staged_files", "unstaged_files", 
        "untracked_files", "command_requested", "command_executed", 
        "command_exit_code", "errors", "created_at"
    ]
    for key in keys:
        assert key in data, f"Missing key in JSON: {key}"

