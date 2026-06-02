# NEW ENGINEER BOOTSTRAP

Quick-start guide for onboarding onto the VÉLØ Oracle Prime system.

## 1. What is this?
VÉLØ Oracle Prime is an ensemble-based probability engine for horse racing. It governs decision tiers (A/B/C/X) based on a consensus of deterministic agents and ML models.

## 2. System Status (Mental Model)
*   **LIVE**: Primary scoring path (`sqpe_v17`).
*   **SHADOW**: Active evaluation loops (Playbook G, Challenger V1).
*   **PAPER**: Research-only sidecars (Sire Sidecar, Intent V1).

## 3. Local Setup
```powershell
# 1. Clone and enter
git clone <repo_url>
cd velo-oracle-prime

# 2. Virtual Env
python -m venv venv
./venv/Scripts/activate

# 3. Dependencies
pip install -r requirements_production.txt
```

## 4. Operational Integrity (Smoke Test)
Before touching any code, ensure the current baseline is healthy:
```powershell
$env:PYTHONPATH='.'
python tests/smoke_test.py
```

## 5. First Principles
1.  **Strict Temporal Safety**: Never use data from the future to score a race in the past.
2.  **No Live Betting**: Live execution is blocked by code assertions.
3.  **Truth First**: Prefer `UNRESOLVED` over a false match in reconciliation.
4.  **Auditability**: Every change must be traceable via `docs/stabilization/CHANGELOG.md`.

## 6. Where to look?
*   Scoring logic: `src/intelligence/velo_prime_ensemble.py`
*   Reconciliation: `scripts/ops/run_results_sigma.py`
*   Safety Guards: `app/core/safety_guards.py`
*   Repo Map: `docs/runtime/REPO_MAP.md`
