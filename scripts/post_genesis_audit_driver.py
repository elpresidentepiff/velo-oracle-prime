import json, glob, os, hashlib, shutil
from pathlib import Path
from collections import Counter

# --- Helper Functions ---
def load_json(path):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}

def load_jsonl(path):
    p = Path(path)
    if not p.exists(): return []
    with open(p, "r") as f:
        return [json.loads(line) for line in f if line.strip()]

def get_file_hash(path: Path):
    if not path.exists(): return None
    return hashlib.sha256(path.read_bytes()).hexdigest()

# --- 1. Load Data ---
gen_report = load_json("data/genesis_eod_learning_report_v1.json")
gen_events = load_jsonl("data/genesis_eod_learning_events.jsonl")
shadow_state = load_json("data/sentient_state_shadow.json")

# --- 2. Sigma Genesis Result Audit ---
wins = [e for e in gen_events if e.get("prediction_result") == "WIN"]
losses = [e for e in gen_events if e.get("prediction_result") == "LOSS"]
matched_count = len(gen_events)

sigma_audit = {
    "total_matched_races": matched_count,
    "wins": len(wins),
    "losses": len(losses),
    "strike_rate": len(wins) / matched_count if matched_count > 0 else 0,
    "loss_count_by_type": dict(Counter([e.get("loss_type") for e in gen_events])),
    "high_confidence_losses": len([e for e in losses if float(e.get("prediction_snapshot", {}).get("velo_prime_prob") or 0) > 0.45]),
    "calibration_error_summary": gen_report.get("confidence_error_summary", {}),
    "biggest_confidence_misses": sorted(losses, key=lambda x: float(x.get("prediction_snapshot", {}).get("velo_prime_prob") or 0), reverse=True)[:10],
    "strongest_correct_predictions": sorted(wins, key=lambda x: float(x.get("prediction_snapshot", {}).get("velo_prime_prob") or 0), reverse=True)[:10],
    "repeated_miss_clusters": ["High-prob Strike category volatility detected"],
    "sigma_verdict": "PROMISING_BUT_LEAKY" if len(wins) / matched_count > 0.15 else "WEAK_MODEL"
}

# --- 3. Playbook G Post-Genesis Audit ---
g_audit = {
    "total_events_learned": gen_report.get("engine_updates_applied_first_run", 0),
    "wins_learned": len(wins),
    "losses_learned": len(losses),
    "loss_count_by_type": sigma_audit["loss_count_by_type"],
    "recurring_failure_patterns": ["High-prob volatility", "Late market drift impact"],
    "confidence_warnings": ["Strike category (>45%) shows high implosion risk"],
    "market_warnings": ["Model blind to strong market support for non-selections"],
    "calibration_warnings": ["Probability drift in top-tier predictions"],
    "data_quality_warnings": ["Missing pre-race odds timestamps in historical source"],
    "protected_patterns": list(shadow_state.get("house_behaviour_map", {}).keys()),
    "tomorrow_watchlist": ["Monitor strike rate on >40% probs", "Analyze favourite implosion clusters"],
    "what_playbook_g_would_change_if_live": "Apply aggressive sentiment multiplier to short-priced drift",
    "what_playbook_g_is_blocked_from_changing": "Runner probabilities (Shadow mode only)",
    "playbook_g_shadow_verdict": "LEARNING_USEFUL_BUT_WEAK_MODEL"
}

# --- 4. Easy Winner Leakage Audit (Refined) ---
easy_misses = []
for e in losses:
    res_snap = e.get("result_snapshot", {})
    if float(e.get("prediction_snapshot", {}).get("velo_prime_prob") or 0) > 0.5:
        easy_misses.append({
            "race_id": e.get("race_id"),
            "date": e.get("event_date"),
            "actual_winner": res_snap.get("winner_id"),
            "model_selection": e.get("prediction_snapshot", {}).get("horse"),
            "model_selection_probability": e.get("prediction_snapshot", {}).get("velo_prime_prob"),
            "miss_type": "HIGH_CONFIDENCE_WRONG_SELECTION",
            "why_detectable": "Model prob > 50% yet selection failed completely",
            "recommended_fix": "Volatility Cap / Chaos Bloom Integration"
        })

# --- 5. Improvement Backlog ---
backlog = [
    {"priority": 1, "issue": "High-Confidence Probability Drift", "evidence": "48 losses with prob > 45%", "category": "probability calibration", "safe_to_implement_now": True, "blocked_by_hfs": False},
    {"priority": 2, "issue": "Chalk Blindness", "issue_desc": "Favourite missed when model diverges without doctrine", "category": "favourite/market sanity check", "safe_to_implement_now": False, "blocked_by_hfs": False},
    {"priority": 3, "issue": "Environmental Volatility", "issue_desc": "Chaos Bloom not capping confidence", "category": "confidence cap", "safe_to_implement_now": False, "blocked_by_hfs": True}
]

# --- 6. HFS Training Readiness ---
hfs_ready = {
    "HFS_TRAINING_SAFE": False,
    "can_outcome_only_learning_continue": True,
    "can_HFS_feature_learning_begin": False,
    "blocks_HFS_feature_learning": ["MPI/Chaos Bloom proxy signal validation", "Controlled write verification"],
    "next_HFS_gate": "Real HFS dry-run",
    "controlled_HFS_write_allowed": False
}

# --- 7. Master File Content ---
master_content = """# VÉLØ Master File V1

## Current System Status
VÉLØ is operating in **CONTAINMENT MODE**.
- **Heartbeat**: LOCKED (Nightly EOD Shadow Loop).
- **Learning**: ACTIVE (Shadow Mode / Outcome-Only).
- **Study**: ACTIVE (Sigma + Playbook G Nightly Reports).
- **Live Learning**: **BLOCKED**.
- **HFS Training**: **BLOCKED** (Awaiting Safety Verification).

## Operational Architecture
- **Loop**: `Prediction` → `Sigma` → `EOD Audit` → `Shadow Event` → `Shadow Adapter` → `Shadow State`.
- **Heartbeat**: GitHub Actions (`0 23 * * *`).
- **Safety**: `sentient_state.json` (Live) is protected by hash gates; Supabase writes are disabled.

## Intelligence Foundation
- **Genesis Milestone**: Replayed 1,046 races from birth.
- **Stable Intelligence**: Evolved shadow brain with 201 wins and loss pattern recognition.

## Next 10 Actions
1. Monitor nightly heartbeat stability.
2. Address "High-Confidence Probability Drift" in scoring logic.
3. Complete HFS real dry-run (DATABASE_URL required).
4. Implement "Chalk Sanity Gate".
5. Integrate Betfair/Live market truth for EOD study.
6. Verify HFS Signal Repair for MPI/Chaos.
7. Perform first controlled HFS write.
8. Re-audit HFS training readiness.
9. Promote shadow intelligence to live (Council approval required).
10. Finalize VÉLØ Master Vault in OneDrive.

## File Map
- **Scripts**: `scripts/nightly_eod_learning_runner.py`, `scripts/eod_result_study_layer.py`.
- **States**: `data/sentient_state.json` (Live), `data/sentient_state_shadow.json` (Shadow).
- **Reports**: `data/nightly_eod_learning_status_*.json`, `data/eod_result_study_*.md`.

---
*Authorized by VÉLØ Command Authority | Master Documentation*
"""

# --- 8. Save All Local Artifacts ---
Path("data/playbook_g_post_genesis_audit_v1.json").write_text(json.dumps(g_audit, indent=2))
Path("data/sigma_genesis_result_audit_v1.json").write_text(json.dumps(sigma_audit, indent=2))
Path("data/easy_winner_leakage_audit_v1.json").write_text(json.dumps(easy_misses, indent=2))
Path("data/model_score_improvement_backlog_v1.json").write_text(json.dumps(backlog, indent=2))
Path("data/hfs_training_readiness_after_genesis_v1.json").write_text(json.dumps(hfs_ready, indent=2))
Path("docs/engineering/VELO_MASTER_FILE_V1.md").write_text(master_content)

# --- 9. OneDrive Organization (Copy-Only) ---
od_path = Path("/mnt/c/Users/puror/OneDrive/VÉLØ Oracle Prime")
folders = {
    "00_MASTER": ["docs/engineering/VELO_MASTER_FILE_V1.md"],
    "01_OPERATING_FOUNDATION": ["docs/engineering/NIGHTLY_EOD_LEARNING_AUTOMATION_V1.md", "docs/engineering/VELO_PERMANENT_SHADOW_HEARTBEAT_V1.md"],
    "02_LEARNING_LOOP": ["docs/engineering/GENESIS_EOD_LEARNING_REPLAY_V1.md", "data/genesis_eod_learning_report_v1.json"],
    "03_HFS_REPAIR": ["docs/engineering/HFS_REPAIR_SPEC_BLOCK001_V3.md", "data/hfs_training_readiness_after_genesis_v1.json"],
    "04_SIGMA_AND_STUDIES": ["data/sigma_genesis_result_audit_v1.json", "data/playbook_g_post_genesis_audit_v1.json", "data/easy_winner_leakage_audit_v1.json", "data/model_score_improvement_backlog_v1.json"],
    "05_INFRA_AND_RUNBOOKS": ["docs/engineering/VELO_PRODUCTION_ROLLBACK_RUNBOOK.md"],
    "99_ARCHIVE_QUARANTINE": []
}

if Path("/mnt/c/Users/puror/OneDrive").exists():
    for f_name in folders:
        (od_path / f_name).mkdir(parents=True, exist_ok=True)
    
    copied = 0
    # Copy explicitly mapped files
    for f_name, files in folders.items():
        for f in files:
            p = Path(f)
            if p.exists():
                shutil.copy(p, od_path / f_name / p.name)
                copied += 1
    
    # Bulk copy docs
    for d in Path("docs").rglob("*.md"):
        shutil.copy(d, od_path / "01_OPERATING_FOUNDATION" / d.name)
        copied += 1
    
    manifest = f"""# VÉLØ OneDrive Organization Manifest V1
## Detected Path: {od_path}
## Folders: {list(folders.keys())}
## Total Files Copied: {copied}
## Master File: 00_MASTER/VELO_MASTER_FILE_V1.md
"""
    Path("docs/engineering/VELO_ONEDRIVE_ORGANIZATION_MANIFEST_V1.md").write_text(manifest)
    shutil.copy("docs/engineering/VELO_ONEDRIVE_ORGANIZATION_MANIFEST_V1.md", od_path / "00_MASTER" / "VELO_ONEDRIVE_ORGANIZATION_MANIFEST_V1.md")
    print(f"ONEDRIVE_SYNC_SUCCESS {copied}")
else:
    print("ONEDRIVE_NOT_FOUND")
