# MASTER STATE — VÉLØ + Analog Sidecar
**Last Updated:** 2026-04-30
**Classification:** OPERATIONAL — TWO-LANE ARCHITECTURE + PAPER EXECUTION LAYER
**Version:** 3.0

---

## Architecture: Two-Lane Model

```
Production Lane (velo-prime-scoring-prod)
├── Scores races, writes velo_verdicts, sends Telegram
├── NEVER imports G/sentient/analog shadow modules
├── Pinned to: deployment 3dfdb43a (March 28 image)
└── Branch: main

Shadow Lane (velo-shadow-lab)
├── Reads production verdicts (velo_verdicts)
├── Evaluates G shadow, rank movement, analog comparison
├── Writes ONLY to shadow tables
├── Branch: shadow-lab
└── Triggered: 09:30 UTC Mon-Sat (30 min after production)

Paper Execution Lane (local operator only)
├── Reads velo_verdicts + racing_api_shadow_forward_ledger.csv
├── Maps verdicts to ExecutionDirectives (SIM/PAPER mode only)
├── Writes ONLY to data/velo_execution_bridge_paper_ledger.csv
├── LIVE mode raises RuntimeError — hard gate, always
└── Triggered: manual daily close via run_execution_bridge_shadow.py
```

---

## Live Systems

| System | Status | Location | Lane |
|--------|--------|----------|------|
| VÉLØ Prime Engine | LIVE | `src/intelligence/velo_prime_ensemble.py` | Production |
| velo_verdicts table | LIVE | Supabase: `ltbsxbvfsxtnharjvqcm` | Production |
| SQPE Phase 3.5 | LIVE | `src/intelligence/sqpe.py` | Production |
| Playbook G (Sentient Loopback) | SHADOW | `app/playbooks/playbook_g_sentient_loopback.py` | Shadow Lab |
| velo-shadow-lab | LIVE | `scripts/shadow_lab.py` | Shadow Lab |
| Racing API Shadow Enrichment | SHADOW | `data/racing_api_shadow_forward_ledger.csv` | Shadow Lab |
| VeloExecutionBridge | PAPER_ONLY | `src/velo/execution_bridge.py` | Paper Execution |
| Execution Bridge Paper Ledger | ACTIVE | `data/velo_execution_bridge_paper_ledger.csv` | Paper Execution |

---

## Railway Services

| Service | Branch | Status | Deploy ID | Commit |
|---------|--------|--------|-----------|--------|
| velo-prime-scoring | main | ROLLED BACK | `3dfdb43a` | Mar 28 |
| velo-prime-scoring-prod | main | ACTIVE (rollback) | `3dfdb43a` | Mar 28 |
| velo-shadow-lab | shadow-lab | ACTIVE | `440cc7e8` | `77b8a52` |

### Rollback Note
`velo-prime-scoring` was rolled back to March 28 image (`3dfdb43a`) after experimental G instrumentation broke the runtime. Production scoring is restored and confirmed working (rows at `2026-04-09T06:25:51`).

---

## Shadow Lab

### Service
- Railway: `velo-shadow-lab` (ID: `b772d439-be21-4a02-9d46-4c79c7bf2ede`)
- Branch: `shadow-lab`
- Cron: `30 9 * * 1-6` (09:30 UTC Mon-Sat)
- Entrypoint: `python scripts/shadow_lab.py`

### Shadow Tables
| Table | Purpose |
|-------|---------|
| `public.shadow_watermarks` | Idempotency — tracks processed batches |
| `public.shadow_audit_log` | Per-row processing log |
| `public.velo_shadow_results` | G shadow evaluation per verdict |
| `public.velo_shadow_rank_movement` | Top-3 rank movement analysis |

### Watermark Strategy
- Uses `generated_at` as batch completeness signal
- First run: gates to last 48 hours (96 rows max)
- Subsequent runs: only rows newer than last watermark
- Idempotent: re-running same batch is a no-op

### Current G State
- G is underpopulated (`G_TOO_FEW_RACES`) — needs evolved state from Supabase learned_patterns
- Shadow lab correctly returns neutral multiplier (1.0) when G is underpopulated
- Real G signals will emerge as shadow accumulates real scoring runs

---

## Supabase

| Item | Value |
|------|-------|
| URL | `https://ltbsxbvfsxtnharjvqcm.supabase.co` |
| Service role key | Rotated — stored in Railway project vars |
| Shadow key | `SHADOW_SUPABASE_KEY` (same rotated key, separate service var) |

### API Keys
- **DO NOT** use the service role key in chat
- All Supabase keys were rotated 2026-04-09 after exposure

---

## Branch Strategy

| Branch | Purpose | Auto-deploy |
|--------|---------|-------------|
| `main` | Production — stable only | Yes |
| `shadow-lab` | Shadow lab — fast-moving | Yes (to velo-shadow-lab) |

**Rule:** No G/sentient/analog imports ever merge into `main`. Shadow evolves on `shadow-lab`.

---

## Last Known Good

| Item | Value |
|------|-------|
| Production deploy | `3dfdb43a` (Mar 28 image, rolled back) |
| Last scoring run | `2026-04-09T06:25:51` (35 races) |
| Telegram | Confirmed working |
| velo_verdicts persist | Confirmed working |
| Shadow lab | Working — 96 rows processed first run |
| Shadow watermark | `2026-04-09T06:25:51` |
| Phase 5 commit | `bfe983a` — Racing API shadow enrichment (374,639 rows, leakage risk flagged) |
| Phase 6 commit | `c1353ff` — VeloExecutionBridge built, paper ledger live |
| Phase 6A commit | `3f65b1c` — --audit-results flag, first paper close |
| Paper ledger state | POWER_ANCHOR n=3, 2/2 closed wins (Hickory Lad SP=1.36, Infraad SP=1.80), P&L=+1.16 |
| Next paper review gate | n≥20 (currently n=3) |

---

## What Was Removed from Production

After the Apr 9 failure, these were removed from production scoring:
- `velo_prime_service.py` G shadow instrumentation blocks
- `src/intelligence/velo_prime_ensemble.py` G shadow `compute()` calls
- All G/sentient state loading from production scoring path

These now live exclusively in `scripts/shadow_lab.py` on `shadow-lab`.

---

## Critical Rules

1. **Production never imports G/sentient/analog modules**
2. **Shadow lab never writes to production tables**
3. **No intuition-only promotion to production**
4. **Shadow lab failure is isolated from production**
5. **Credentials never pasted in chat — rotate immediately if exposed**
6. **VeloExecutionBridge VELO_EXECUTION_MODE=LIVE is permanently blocked — RuntimeError enforced in code**
7. **Paper ledger is append-only — never overwrite historical directive records**
8. **POWER_ANCHOR paper ledger: no review before n≥20, no live discussion before n≥100, no automatic promotion**
9. **Racing API enrichment weight changes blocked until RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK is resolved**

---

## Paper Execution Layer — Promotion Gates

| Gate | Threshold | Current State |
|------|-----------|---------------|
| First review allowed | POWER_ANCHOR n≥20 | n=3 — INSUFFICIENT_SAMPLE |
| Paper candidate discussion | POWER_ANCHOR n≥60 | blocked |
| Live discussion | POWER_ANCHOR n≥100 | blocked |
| Auto-promotion | Never | hard rule |

---

*Updated: 2026-04-30 — Phase 3 complete (paper execution layer live). Shadow lab operational.*
