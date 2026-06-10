# RAILWAY CLEAN ORCHESTRATOR — SPEC (build only if/when needed)

**One service. One repo. One start command.** Name: `velo-orchestrator`.

- **Runs:** `scripts/ops/run_race_day.py` stages (per ONE_RACE_DAY_COMMAND_SPEC) + `/healthz`.
- **Allowed:** preflight · dry-run · proofs · evening closeout. **Live scoring only behind an operator approval flag** (Telegram button or dashboard toggle writing an approval artifact the orchestrator checks).
- **Env (names only):** SUPABASE_URL, SUPABASE_SERVICE_KEY(rotated), TELEGRAM_BOT_TOKEN(rotated)+CHAT_ID, VELO_ENSEMBLE_PROFILE, TRIGGER secret. **No RACING_API_*. No service-role for anything but its own writes.**
- **Health checks at boot, refuse to serve if any fail:** Supabase read OK · `docs/current/ONE_TRUTH.md` present in image · loop registry loads · git SHA exposed at `/healthz` · Racing API import scan clean · Telegram disabled unless approval artifact exists.
- **Every stage writes its proof artifact** (source_truth, feature_health, attach preflight, rpdc_integrity, persistence_proof, mission_control, sigma_status, learning_admission) — proof fails ⇒ stage stops ⇒ status endpoint shows the exact failed loop.
- **Forbidden, enforced in code:** unapproved scoring · learning execution · Telegram pick sends · dashboard publish · historical repair apply · any Betfair execution import (existing AST guard reused).
