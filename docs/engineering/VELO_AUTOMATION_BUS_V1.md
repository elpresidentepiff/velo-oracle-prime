# VÉLØ Automation Bus V1

**Status:** DESIGN ONLY  
**Phase:** 9 — Ops Automation  
**Classification:** `AUTOMATION_BUS_OPS_ONLY` / `NO_LIVE_MUTATION` / `DESIGN_ONLY`

---

## Purpose

n8n-style workflow automation for operations and reporting. The automation bus handles routine ops tasks so the prediction brain doesn't need to be manually orchestrated for every delivery.

The automation bus is strictly ops/reporting only. It cannot touch the prediction core.

---

## Allowed Workflows

| Workflow | Description | Trigger |
|---|---|---|
| Daily report routing | Copy sigma report to dashboard + Telegram mirror | Sigma close |
| Dashboard refresh | Rebuild `data/mission_control/latest.json` after scoring | Score complete |
| Artifact copying | Move timestamped reports to archive folder | Daily close |
| Issue creation | Create GitHub issue if Red Team finds CRITICAL finding | Red Team complete |
| Calendar reminder | Remind operator of gate review dates | Scheduled |
| Email notification | Operator daily summary email | Daily close |
| Telegram mirror check | Verify Telegram delivery completed | Post-sigma |

## Hard Boundary

The Automation Bus CANNOT:
- Trigger live scoring
- Modify `weight_policy_registry.py`
- Call `run_prime_today.py` outside the approved Railway cron
- Consume learning
- Promote models
- Mutate Telegram format
- Mutate router/staking/Playbook G

---

```
AUTOMATION_BUS_V1_STATUS: DEFINED
ENFORCEMENT: DESIGN — ops automation only, never prediction-adjacent
```
