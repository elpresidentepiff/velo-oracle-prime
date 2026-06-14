# BETTING_LEDGER PROVENANCE AUDIT

**Date:** 2026-06-11 (00:0x UTC) · Table: Supabase `betting_ledger`, 1,050 rows · Read-only.

## Classification: **BETTING_LEDGER_CONFIRMED_SIM**

Evidence (sample row id=1, 2026-03-19 Ludlow):
- `bankroll_before: 1000.0` — synthetic round-number starting bankroll
- `placed_at == settled_at` to the microsecond — bets "placed" and "settled" in the same instant = backfilled simulation, not live wagering
- `market_id: null` — no exchange/bookmaker market reference anywhere
- `race_id: rac_11874681` — Racing-API-era ID format (decommissioned source)
- `reasoning: "velo_prime_v1 | tier=C | pos=2 | sp=3.0"` — generated from verdict+result, i.e. retrospective
- Writer: `app/agents/betting_agents.py` (`supabase.table("betting_ledger").insert`) — classified LEGACY_AGENT in the runtime map since April

Fields: stake ✓ (flat £5 sim), odds ✓ (SP), result/P&L ✓, live/sim marker ✗ (absent — hence the quarantine until now).

## Rules going forward
- **Safe for ROI: NO.** Sim-era, legacy framework, stakes/odds retrospective. Stays excluded from every PERFORMANCE_CLAIM_POLICY layer.
- Do not delete (historical record of the March experiment). Do not extend (writer is legacy).
- Repair packet note: label the table LEGACY_SIM in the schema archive review; future real ledger (if ever) must be a new table with a live/sim marker by design.
