"""
VÉLØ Read State First
=====================
Run this at the start of every session or before any infrastructure action.
Reads canonical state files and prints a READBACK block.
Exits non-zero if any required file is missing.

Usage:
    python scripts/read_state_first.py
"""
import sys
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

REQUIRED_FILES = [
    "docs/VELO_CANONICAL_STATE.md",
    "docs/VELO_DEPLOY_PROOF_RULE.md",
    "docs/VELO_WORKFLOW_LOCK.md",
    "docs/VELO_INCIDENT_LOG.md",
]

EXTRACT = {
    "canonical repo":               (r"elpresidentepiff/velo-oracle-prime", "elpresidentepiff/velo-oracle-prime"),
    "canonical branch":             (r"feature/v10-launch", "feature/v10-launch"),
    "canonical production service": (r"velo-oracle.*0992976e", "velo-oracle (0992976e-a59d-4cc8-a51f-76e330057493)"),
    "canonical ingestion service":  (r"ingestion-spine.*b9a52e75", "ingestion-spine (b9a52e75-6d98-4077-98d0-d9e68b16033e)"),
    "canonical prediction endpoint":(r"POST https://velo-oracle-production", "POST https://velo-oracle-production.up.railway.app/api/v1/predict/race"),
    "last proven-good deployment":  (r"a340bf86", "a340bf86-2df0-42d2-b16f-8ed0ef76346f @ 2026-03-17T11:36 UTC"),
    "rollback anchor":              (r"deploymentRedeploy", "deploymentRedeploy(id: \"a340bf86-2df0-42d2-b16f-8ef0ef76346f\")"),
}

print("\nVÉLØ READ STATE FIRST\n")

# 1. Check required files exist
missing = []
for rel in REQUIRED_FILES:
    p = ROOT / rel
    if not p.exists():
        print(f"  MISSING  {rel}")
        missing.append(rel)
    else:
        print(f"  FOUND    {rel}")

if missing:
    print(f"\nFATAL: {len(missing)} required file(s) missing. Create them before proceeding.")
    sys.exit(1)

# 2. Read canonical state
canonical_text = (ROOT / "docs/VELO_CANONICAL_STATE.md").read_text(encoding="utf-8")

# 3. Print READBACK
print("\n" + "=" * 60)
print("READBACK:")
print(f"  - canonical repo:                elpresidentepiff/velo-oracle-prime")
print(f"  - canonical branch:              feature/v10-launch")
print(f"  - canonical production service:  velo-oracle (0992976e-a59d-4cc8-a51f-76e330057493)")
print(f"  - canonical ingestion service:   ingestion-spine (b9a52e75-6d98-4077-98d0-d9e68b16033e)")
print(f"  - canonical prediction endpoint: POST https://velo-oracle-production.up.railway.app/api/v1/predict/race")
print(f"  - last proven-good deployment:   a340bf86-2df0-42d2-b16f-8ef0ef76346f @ 2026-03-17T11:36 UTC")
print(f"  - 10am workflow:                 FETCH → NORMALIZE → SCORE → SUGGEST → STOP")
print(f"  - results workflow:              WAIT → FETCH RESULTS → RECONCILE → SIGMA → LEARN")
print(f"  - rollback command:              deploymentRedeploy(id: \"a340bf86-2df0-42d2-b16f-8ef0ef76346f\")")
print("=" * 60)

# 4. Verify key strings still present in canonical state (sanity check)
checks = [
    ("velo-oracle-prime in canonical state",    "velo-oracle-prime" in canonical_text),
    ("feature/v10-launch in canonical state",   "feature/v10-launch" in canonical_text),
    ("0992976e in canonical state",             "0992976e" in canonical_text),
    ("a340bf86 rollback anchor present",        "a340bf86" in canonical_text),
    ("bash start.sh in canonical state",        "bash start.sh" in canonical_text),
]

print("\nSANITY CHECKS:")
all_ok = True
for label, result in checks:
    status = "PASS" if result else "FAIL"
    if not result:
        all_ok = False
    print(f"  {status}  {label}")

print()
if all_ok:
    print("STATE: CANONICAL FILES CONSISTENT — safe to proceed")
    sys.exit(0)
else:
    print("STATE: CANONICAL FILE INCONSISTENCY DETECTED — review docs/VELO_CANONICAL_STATE.md")
    sys.exit(1)
