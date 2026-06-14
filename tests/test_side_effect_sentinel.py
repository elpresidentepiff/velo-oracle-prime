import pytest
import json
import subprocess
import os
from pathlib import Path
from scripts.ops.side_effect_sentinel import (
    SIDE_EFFECT_SAFE, SIDE_EFFECT_SUPABASE_WRITE_RISK, SIDE_EFFECT_TELEGRAM_SEND_RISK,
    SIDE_EFFECT_MODEL_PROMOTION_RISK, SIDE_EFFECT_LIVE_SCORING_RISK,
    SIDE_EFFECT_FORBIDDEN_ENV, SIDE_EFFECT_COMMAND_OK, SIDE_EFFECT_COMMAND_FAILED,
    SIDE_EFFECT_COMMAND_BLOCKED
)

@pytest.fixture
def sentinel_script():
    return Path(__file__).resolve().parents[1] / "scripts" / "ops" / "side_effect_sentinel.py"

def _load_json_from_stdout(stdout: str) -> dict:
    # Find the last { ... } block in stdout
    import re
    matches = list(re.finditer(r'\{.*\}', stdout, re.DOTALL))
    if not matches:
        raise ValueError(f"No JSON found in: {stdout}")
    return json.loads(matches[-1].group(0))

def test_safe_audit_command(sentinel_script, tmp_path):
    """Safe audit command returns SIDE_EFFECT_SAFE and PASS."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--", "echo", "safe"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode == 0
    data = _load_json_from_stdout(res.stdout)
    assert data["status"] == "PASS"
    assert data["state"] == SIDE_EFFECT_SAFE

def test_safe_run_command(sentinel_script, tmp_path):
    """Safe run command executes and returns SIDE_EFFECT_COMMAND_OK."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "run",
        "--", "echo", "hello"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode == 0
    data = _load_json_from_stdout(res.stdout)
    assert data["status"] == "PASS"
    assert data["state"] == SIDE_EFFECT_COMMAND_OK
    assert data["command_executed"] is True

def test_supabase_risk(sentinel_script, tmp_path):
    """Supabase write-risk command returns SIDE_EFFECT_SUPABASE_WRITE_RISK and non-PASS."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--", "supabase", "insert", "verdict"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == SIDE_EFFECT_SUPABASE_WRITE_RISK
    assert any("SUPABASE" in hit for hit in data["risk_hits"])

def test_telegram_risk(sentinel_script, tmp_path):
    """Telegram send-risk command returns SIDE_EFFECT_TELEGRAM_SEND_RISK and non-PASS."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--", "python", "send_telegram.py"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == SIDE_EFFECT_TELEGRAM_SEND_RISK

def test_model_risk(sentinel_script, tmp_path):
    """Model promotion-risk command returns SIDE_EFFECT_MODEL_PROMOTION_RISK and non-PASS."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--", "registry", "promote", "v2"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == SIDE_EFFECT_MODEL_PROMOTION_RISK

def test_scoring_risk(sentinel_script, tmp_path):
    """Live scoring-risk command returns SIDE_EFFECT_LIVE_SCORING_RISK and non-PASS."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--", "score_race", "123"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == SIDE_EFFECT_LIVE_SCORING_RISK

def test_dangerous_env_flag(sentinel_script, tmp_path):
    """Dangerous env flag returns SIDE_EFFECT_FORBIDDEN_ENV and non-PASS."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    env["VELO_ALLOW_SUPABASE_WRITES"] = "true"
    
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--", "echo", "risky-env"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == SIDE_EFFECT_FORBIDDEN_ENV

def test_unsafe_run_blocked(sentinel_script, tmp_path):
    """Unsafe run command is blocked and not executed."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "run",
        "--", "supabase", "upsert", "data"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == SIDE_EFFECT_COMMAND_BLOCKED
    assert data["command_executed"] is False

def test_failing_safe_command(sentinel_script, tmp_path):
    """Failing safe command returns SIDE_EFFECT_COMMAND_FAILED."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "run",
        "--", "false"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert data["state"] == SIDE_EFFECT_COMMAND_FAILED
    assert data["command_executed"] is True

def test_classification_check(sentinel_script, tmp_path):
    """Missing classification returns non-PASS. Valid classification file returns PASS."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    cls_file = tmp_path / "cls.txt"
    
    # 1. Missing
    cls_file.write_text("PARTIAL CLASSIFICATION")
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--classification-file", str(cls_file),
        "--", "echo", "test"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode != 0
    data = _load_json_from_stdout(res.stdout)
    assert len(data["classification_missing"]) > 0
    
    # 2. Valid
    cls_file.write_text("NO_LIVE_SCORING_CHANGE NO_SUPABASE_WRITES NO_MODEL_PROMOTION NO_TELEGRAM_SEND")
    res = subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--classification-file", str(cls_file),
        "--", "echo", "test"
    ], capture_output=True, text=True, env=env)
    
    assert res.returncode == 0
    data = _load_json_from_stdout(res.stdout)
    assert data["status"] == "PASS"

def test_artifact_written(sentinel_script, tmp_path):
    """JSON artifact is written."""
    env = os.environ.copy()
    env["VELO_SENTINEL_ROOT"] = str(tmp_path)
    out_json = tmp_path / "sentinel.json"
    subprocess.run([
        "python3", str(sentinel_script),
        "--mode", "audit",
        "--output", str(out_json),
        "--", "echo", "artifact-test"
    ], env=env)
    
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert "status" in data
    assert "created_at" in data
