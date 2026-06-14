# VÉLØ Test Suite

## Run
```bash
venv/bin/python -m pytest                 # full suite (947 collected)
venv/bin/python -m pytest tests/test_mission_control_source_truth.py \
                          tests/test_rpdc_persist_boundary.py        # truth-boundary core
```
Pinned environment (requirements_production.txt): `pytest==7.4.4`,
`pytest-asyncio==0.23.3`, `pytest-cov==4.1.0`. If collection crashes with
`ModuleNotFoundError: _pytest.scope`, the venv has drifted — reinstall the pins.

## Quarantine policy (Loop 9: every fix becomes a test)
- A test that fails because **the live path changed** is quarantined with a
  `STALE_LIVE_PATH` skip marker stating what was removed and where the live-path
  coverage now lives. It is never silently deleted; if the symbol returns, the
  `skipif` re-arms the test automatically.
- A test that asserts a **point-in-time incident state** (e.g. "repo has a
  10-day data gap") must be rewritten to assert the detector contract, not the
  incident.
- Current quarantines: Racing-API-era loader tests (`fetch_api_racecards`,
  `_sanitize_api_rpr`) and the two HFS-training-era modules
  (`test_hfs_feature_builder_v1.py`, `test_hfs_backfill_dry_run_v1.py`).
- Do not run unknown network-touching tests against production Supabase from a
  dev box; that belongs to CI (no secrets ⇒ network tests fail loud or skip).
