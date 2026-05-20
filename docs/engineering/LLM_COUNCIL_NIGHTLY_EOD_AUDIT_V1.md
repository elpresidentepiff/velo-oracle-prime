# LLM Council Nightly EOD Audit Protocol V1

## Objective
Provide high-trust verification of VÉLØ's nightly learning evolution. The Council ensures that the autonomous shadow brain remains isolated from production and free from unsafe data contamination.

## Council Structure & Roles

### Gemini (Lead Auditor)
- **Responsibility**: Quantitative verification.
- **Checks**:
    - Confirms `engine_updates_applied_duplicate_run == 0`.
    - Confirms `live_sentient_state_touched == false`.
    - Confirms `data_error_rate` is within threshold.
    - Validates idempotency keys in the event ledger.

### Claude (Scope Guard)
- **Responsibility**: Architectural integrity.
- **Checks**:
    - Verifies no forbidden files (e.g., `app/main.py`, `velo_prime_service.py`) were modified.
    - Confirms `hfs_features_used == false`.
    - Ensures the shadow adapter's safety wrapper was used.

### GPT (Command Authority)
- **Responsibility**: Final Verdict & Escalation.
- **Actions**:
    - Reviews runner status and Council findings.
    - Signs off on the final `council_verdict` (PASS/FAIL/BLOCKED).
    - Decides on escalation to human authority if structural anomalies are detected.

### Kimi (Observer)
- **Responsibility**: Independent artifact review.
- **Checks**:
    - Forensic review of failure ledgers and event snapshots.

## Audit Artifact
Every run must produce `data/nightly_eod_learning_council_audit_{date}.json` containing the synthesized findings of all members.
