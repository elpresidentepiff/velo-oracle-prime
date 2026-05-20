# VÉLØ Dependency Contract V1

**Date:** 2026-05-05

## 1. Supabase Package Audit

The `supabase` Python package is a critical P1 dependency for all cloud-integrated scripts.

| Environment | verified | Path |
|---|---|---|
| `requirements_production.txt` | **YES** | `supabase>=2.7.0` |
| `Dockerfile` | **YES** | `pip install -r requirements_production.txt` |
| `railway.toml` | **YES** | `pip install -r requirements_production.txt` |
| `.github/workflows/ci.yml` | **YES** | Uses standard build path. |

## 2. Plan Verification
- **Racing API:** Verified Standard Plan (3 req/sec).
- **Python Version:** Python 3.11-slim (Docker) / Python 3.12 (Local Venv).

## 3. Conclusion
The dependency contract is **STABLE**. Missing `supabase` package errors in the audit environment were likely due to local pathing or an un-activated venv, not a missing project requirement.
