# Execution / Betting Modules

This folder contains execution-oriented and betting-oriented modules that are
**not** the current canonical audit-first VÉLØ runtime.

Affected files:

- [betting_agents.py](C:\Users\puror\velo-oracle-prime\app\agents\betting_agents.py)
- [betfair_execution_agent.py](C:\Users\puror\velo-oracle-prime\app\agents\betfair_execution_agent.py)
- [betfair_trading_agents.py](C:\Users\puror\velo-oracle-prime\app\agents\betfair_trading_agents.py)
- [odds_movement_predictor.py](C:\Users\puror\velo-oracle-prime\app\agents\odds_movement_predictor.py)

These modules should remain segregated from the current operator-visibility
and evidence-first race-day path unless explicitly revived under governance.

Canonical live path is:

1. [C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py](C:\Users\puror\velo-oracle-prime\scripts\run_prime_today.py)
2. [C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py](C:\Users\puror\velo-oracle-prime\app\services\velo_prime_service.py)
3. [C:\Users\puror\velo-oracle-prime\src\intelligence\velo_prime_ensemble.py](C:\Users\puror\velo-oracle-prime\src\intelligence\velo_prime_ensemble.py)
4. [C:\Users\puror\velo-oracle-prime\scripts\run_results_sigma.py](C:\Users\puror\velo-oracle-prime\scripts\run_results_sigma.py)
5. [C:\Users\puror\velo-oracle-prime\src\preflight.py](C:\Users\puror\velo-oracle-prime\src\preflight.py)
