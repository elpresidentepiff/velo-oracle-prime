# VÉLØ Red Team Agent V1

**Status:** DESIGN ONLY  
**Phase:** 8 — Security and Robustness  
**Classification:** `RED_TEAM_INTERNAL_ONLY` / `NO_EXTERNAL_OFFENSIVE_SECURITY` / `DESIGN_ONLY`

---

## Purpose

Internal defensive agent that attacks VÉLØ's own systems to find governance gaps, leakage risks, and unsafe states before they cause problems in live scoring.

No external offensive security. No third-party target testing. Internal only.

---

## Attack Surface

The Red Team agent probes:

| Target | Attack |
|---|---|
| Feature leakage | Run winner_max_rate dominance test on every feature in every parquet |
| Timestamp provenance | Check all features for within-race correlation to outcome |
| Identity mismatch | Flag races where horse name in parquet doesn't match Supabase |
| Stale Council verdicts | Check if Council evidence packets are older than 7 days |
| Dirty repo state | `git status --short` should be clean before any scoring run |
| Unsafe promotion | Scan for any model promotion without evidence in audit trail |
| Shadow/live contamination | Verify `consumed_live=False` on all shadow learning events |
| Bad international features | Re-run FR timestamp provenance for any new feature |
| Data-source drift | Check if Racing Post coverage has dropped below 90% |
| Stale gitignore | Verify no sensitive files (*.pkl) accidentally exposed |

---

## Red Team Output

After each run, produces a `red_team_report_{date}.json` with:
- Attack surface covered
- Vulnerabilities found (CRITICAL / HIGH / MEDIUM / LOW)
- Evidence for each finding
- Recommended remediation

CRITICAL findings must be addressed before any next promotion discussion.

---

## Scope Constraints

```
INTERNAL_ONLY: Red Team attacks VÉLØ systems only
NO_EXTERNAL_TARGETS: not a penetration testing tool for third parties
NO_OFFENSIVE_SECURITY: discovery and reporting only — no exploitation
NO_LIVE_MUTATION: Red Team cannot make live changes to fix what it finds
FINDINGS_TO_COUNCIL: all CRITICAL/HIGH findings escalate to Council packet
```

```
RED_TEAM_AGENT_V1_STATUS: DEFINED
IMPLEMENTATION: PHASE 8 — after Phase 3 harness
```
