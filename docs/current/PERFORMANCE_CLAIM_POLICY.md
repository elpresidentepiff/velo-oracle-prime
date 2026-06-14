# PERFORMANCE CLAIM POLICY — LOOP 12

**Effective:** 2026-06-10 · No public performance claim without evidence at the claimed level. Evidence base: `PERFORMANCE_AND_MONEY_REALITY_AUDIT.md` (2026-06-10).

## Claim levels

| Level | Requirement | What VÉLØ holds today |
|---|---|---|
| `INTERNAL_ONLY` | Any computed number, clearly labelled | Everything |
| `SHADOW_ONLY` | Paper/flat-stake evidence, no staking; sample stated | Router lanes: V2 n=41 ROI +40.7%, V1 n=51 ROI +28.8%, V6 n=17 ROI +48.5% |
| `VERIFIED_INTERNAL` | Sigma-verified, artifact-backed, recomputable | 19-day SR 26.1% (155/595, 2026-05-21→06-09) |
| `PUBLIC_SAFE` | VERIFIED_INTERNAL + clean-day-only series + degraded/contaminated days excluded and disclosed + 90+ consecutive days | **Not yet** — no clean-day-only series exists; window is 19 days |
| `PUBLIC_BENCHMARKED` | PUBLIC_SAFE + same-dates comparison against a named public competitor (e.g. RP Postdata/newspaper naps via `build_industry_comparison.py`) + independent recomputation | **Not yet** |

## Hard rules
1. **No "top 10 UK" / "top-tier UK" claim until `PUBLIC_BENCHMARKED`.**
2. Every published number carries: sample size, date range, exclusions, and claim level.
3. Numbers from the execution-bridge paper ledger are **`EVIDENCE_INTEGRITY_SUSPECT`** and unusable at any public level until the ID chain is repaired (synthetic `rp_` IDs prevent result closure; POWER_ANCHOR closed sample is 0/8 with most rows unable to close).
4. Degraded days (June 7, 8, 10, …) and contaminated days (May 20) must be excluded from clean series and the exclusion disclosed — never silently dropped, never silently included.
5. Shadow numbers are always labelled shadow. A shadow ROI presented as live ROI is a firing offence for the doc that does it.
6. Claims downgrade automatically: if any input loop (L3 RPDC, L4 persistence, L7 sigma) is failing for the period claimed, the claim level caps at `INTERNAL_ONLY` for that period.

## Path to PUBLIC_BENCHMARKED
1. Repair ledger ID chain (operator-approved fix).
2. Build clean-day-only sigma series with exclusions disclosed.
3. Run 90+ consecutive days with pre-race timestamped picks.
4. Same-dates benchmark vs named public tipsters/naps tables.
5. Independent recomputation from stored artifacts.
