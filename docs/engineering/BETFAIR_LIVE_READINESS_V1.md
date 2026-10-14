# Betfair live-betting readiness — V1 (2026-10-14)

**Verdict: not ready for live money. Nothing here should change the standing rules** (no live staking, execution bridge SIM/PAPER only, live weights frozen). This is the gate list for when that changes.

## What exists today
- `src/velo/execution_bridge.py`: simulation/paper only. Raises on `VELO_EXECUTION_MODE=LIVE` or `BETFAIR_MODE=LIVE`; stake and liability always null.
- `app/integrations/betfair_client.py`: SIM / DELAYED / LIVE. `place_order()` calls `place_orders` when `BETFAIR_MODE=LIVE`. **That env var is the only thing between this repo and a real bet.**
- `src/velo/execution_guard.py`: lane classifier (FORTRESS / FRAME / VISION / KILL). Classifies, does not size or cap.
- `betting_ledger` (Supabase): written by `run_results_sigma.py` *after* results, one row per race (upsert on `race_id`). A retrospective ledger, not an order record.

## Evidence on edge (as of 2026-10-14)
| Measure | Value |
|---|---|
| `betting_ledger`, 2026-03-19 → 10-13 | 2,210 bets, £17,585 staked, **−£3,252.60 (−18.5%)**, 20% strike, bankroll low −£1,474 (no floor) |
| FormFav global shadow, 10-13 | top pick won 27 of 110 usable races (24.5%); US 7/51 (14%) |
| Price history stored | **0 rows** in `market_snapshots`, `odds_snapshots`, `formfav_market_snapshots`, `betfair_markets` |

No price history means closing-line value (CLV) cannot be measured, so "is VELO beating the market" is currently unanswerable.

## Closed 2026-10-14 (no behaviour change to scoring; live betting still blocked)
- **Blocker 4/5 (single switch, shallow scan):** `BetfairClient.place_order` in LIVE mode now calls a risk gate first and **denies by default** (`NO_RISK_GATE_CONFIGURED`). Real orders need `BETFAIR_MODE=LIVE` *and* an explicitly wired gate. `tests/test_no_live_order_path.py` (CI) fails if any code other than the Betfair client calls `place_order(s)` or any deploy config enables a LIVE mode.
- **Blocker 3 (risk layer) — rules built, not wired:** `src/velo/execution_risk.py` is a pure, fail-closed gate: kill switch, per-market operator approval, market open and pre-play, customer order ref + duplicate refs, stake cap, price band and Betfair ladder, per-race and daily liability caps, daily loss stop, bankroll floor. 12 rules, each tested. **Still to build (needs operator approval):** the durable state provider (kill-switch row, approval records, exposure, seen refs), and passing `customer_order_ref` to Betfair as its own idempotency key.
- **FormFav call volume:** results for races stuck `pending`/`interim` were re-fetched every 60 s for 3 hours; now every 2 / 10 min. The daily settle sweep upgrades stragglers. Prices are Premium-only (trial = 403), so price capture (G1) waits on a paid tier or the Betfair delayed key.

## Blockers still open
1. **Secrets hygiene.** A TheRacingAPI username/password is committed in `docs/VELO_DEVELOPER_BLUEPRINT.md` in a **public** repo (and git history). Rotate it, remove it, then decide whether the repo stays public. Betfair credentials/certs go in Railway sealed variables only, never in the repo.
2. **No demonstrated edge.** Need pre-off price capture, then CLV and calibration by segment (`formfav_sigma_edges`) over a sample large enough to trust (≥30 final races per segment as a floor, far more for a go decision).
3. **Execution risk layer wired to real state.** Rules exist (above); still missing: per-bet stake cap, per-race and daily liability caps, daily-loss stop and bankroll floor, persistent kill switch, market-status check (suspended / in-play), price sanity vs expectation, idempotent customer order refs, order-state reconciliation (partial matches, lapses, cancels), commission-aware P&L.
4. **Single-point switch.** One env var enables real orders. Needs a second independent control (signed operator approval record in the DB, checked per order) and a hard daily cap enforced server-side.
5. **Safety scan is shallow.** `app/core/safety_guards.py` scans three files for two module names that no longer exist. Replace with a real test that fails CI if any non-execution module can reach `place_order`.
6. **Monitoring.** The FormFav worker sat in a silent 429 loop for hours and was found by hand. A betting system needs alerts on stale feeds, failed deploys, rate limits, and missed daily runs, not log reading.
7. **Always-on scoring.** Scoring depends on a local Racing Post browser session; the Railway scoring cron is documented as dead. A missed laptop day means no picks.
8. **Betfair onboarding.** Live app key (activation fee), certificate login, session keep-alive, streaming API for prices, Premium Charge exposure, and account/commercial terms for operating as a company. Owner decisions.

## Staged gates
| Gate | Exit criterion |
|---|---|
| G0 Hygiene | Secrets rotated and removed; monitoring/alerts live; scoring on an always-on path |
| G1 Evidence | Price capture running; ≥ N final races of CLV and calibration, positive in a named segment |
| G2 Build | Execution risk layer (blocker 3–5) built and tested; still cannot place orders |
| G3 Paper on real prices | ≥ 4 weeks of paper orders against live Betfair prices with fills/commission modelled; matches G1 expectations |
| G4 Live minimum | Minimum stake, tight caps, one segment, operator approval per day |
| G5 Scale | Only on G4 results, stepwise |

## Daily monitoring (in place)
The worker settles and reconciles every race day (`formfav_global_eod.py`). Query:
- `formfav_sigma_daily` — by date, country and result basis.
- `formfav_sigma_edges` — by country × confidence × top-pick probability band, with `avg_predicted_win_pct` against actual strike (calibration) and `enough_sample`.
