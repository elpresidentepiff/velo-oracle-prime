# VÉLØ Workflow Lock
> Created 2026-03-17. Read before starting any race-day or deploy operation.

---

## Workflow Mutex Rules

**Only ONE workflow may be active at a time.** The workflows are:

| Workflow | Trigger | Lock |
|---|---|---|
| **10am Race** | 9:55am pre-race | Exclusive — no deploy surgery while active |
| **Results Reconciliation** | After all races complete | Exclusive — no deploy surgery while active |
| **Deploy Surgery** | Infrastructure fix needed | Exclusive — never during race day |

---

## 10am Race Workflow — Locked Sequence

```
PRE-FLIGHT   python scripts/preflight_10am_check.py  ← MUST PASS before proceeding
SMOKE TEST   python scripts/run_todays_races.py --smoke  ← single race
INSPECT      review smoke output manually
FULL RUN     python scripts/run_todays_races.py  ← only if smoke clean
TELEGRAM     send via Telegram bot
STOP         do NOT continue to results reconciliation
```

**Hard rules:**
- If preflight fails: FIX THE PROBLEM. Do not run predictions against a broken endpoint.
- If smoke test fails: STOP. Do not send to Telegram.
- Do not mix deploy changes with 10am operations under any circumstances.

---

## Results Reconciliation Workflow — Locked Sequence

```
WAIT         until all races on card are complete
RESULTS      fetch via Racing API results endpoint
RECONCILE    compare predictions vs actuals (scripts/sigma_loop_closer.py)
SIGMA        update sigma loop
LEARN        update learned_patterns in Supabase if pattern confirmed
```

**Hard rules:**
- Never triggered automatically.
- Never run during 10am window.
- Never run before all races on the day's card are finished.

---

## Deploy Surgery Rules

- Never during race day (9:00–18:00 UK time) unless endpoint is completely dead.
- Always run `scripts/deploy_proof_check.py` after every deploy.
- Always use rollback anchor (`a340bf86`) if new deploy fails proof check.
- Read `docs/VELO_CANONICAL_STATE.md` before touching Railway.

---

## Emergency Protocol

If the endpoint goes down during a race day:
1. Run `scripts/deploy_proof_check.py` — confirm dead.
2. Rollback immediately: `deploymentRedeploy(id: "a340bf86-2df0-42d2-b16f-8ed0ef76346f")`
3. Run proof check again — confirm live.
4. Resume race-day workflow.
5. Log the incident in `docs/VELO_INCIDENT_LOG.md`.

---

*Created: 2026-03-17. Do not edit without updating VELO_CANONICAL_STATE.md.*
