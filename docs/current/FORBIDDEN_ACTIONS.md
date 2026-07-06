# FORBIDDEN_ACTIONS.md — Hard Safety Wall

These are hard boundaries. None may be crossed without an explicit, per-mission
operator instruction naming that specific action. "It seemed obviously correct"
is never sufficient authorization — see the July 06 canonical persistence
precedent in `docs/current/CLAUDE.md` for what explicit authorization looks like
in practice.

| Classification | Meaning |
|---|---|
| `NO_LIVE_SCORING_CHANGE` | No edit to `src/intelligence/velo_prime_ensemble.py` live weights/profile, `models/sqpe_v17/`, or `models/specialist/` without operator gate. |
| `NO_SUPABASE_WRITES` | No insert/upsert/update/delete against any Supabase table without explicit per-mission operator authorization naming the target table(s). |
| `NO_TELEGRAM_SEND` | No message sent via any Telegram bot integration. Scoring alerts are currently DISABLED (`--no-notify`) per `docs/current/ONE_TRUTH.md`. |
| `NO_MODEL_PROMOTION` | No shadow/challenger model (New Build, No-RPR, Champion Intent Shadow, sqpe_v18, etc.) may be promoted to the live scoring path without an operator sign-off recorded in `docs/current/ONE_TRUTH.md`. |
| `NO_PRODUCTION_DEPLOY` | No deploy to Railway or any production host; no change to Railway cron config (currently FAIL_OR_UNPROVEN / manual-only). |
| `NO_CREDENTIAL_EXPOSURE` | No secret, API key, session cookie, or credential file committed, logged, or printed. See `docs/current/SECRET_ROTATION_OPERATOR_CHECKLIST.md`. |
| `NO_AUTONOMOUS_CLOUD_SPEND` | No autonomous provisioning or scaling of paid cloud resources (e.g. Vast.ai per `docs/VASTAI_DEPLOYMENT_GUIDE.md`) without explicit operator approval of cost and scope. |
| `NO_AGENT_SELF_REPLICATION` | No agent spawns a persistent autonomous copy of itself or a new always-on process without explicit operator instruction. |
| `NO_UNAPPROVED_SCHEMA_MUTATION` | No new Supabase migration, table, or column added outside an explicit operator-approved migration mission. Note: existing canonical tables (`canonical_model_scorecards`, `canonical_learning_events`) do not have `promotion_eligible`/`source_type` columns — pack that context into existing `learning_class`/`notes` fields instead of silently adding columns (see `data/reports/july06_canonical_runtime_persistence_report.md` for the precedent). |

## Enforcement mechanism

These are enforced procedurally today via:
- `scripts/ops/side_effect_sentinel.py` (`docs/current/SIDE_EFFECT_SENTINEL.md`) —
  pattern-blocks commands referencing Supabase writes, Telegram sends, model
  promotion, or live scoring.
- `scripts/ops/task_contract_runner.py` (`docs/current/TASK_CONTRACT_RUNNER.md`) —
  blocks out-of-scope paths and forbidden keywords in a mission's git diff.
- `scripts/ops/governed_task_runner.py` (`docs/current/GOVERNED_TASK_RUNNER.md`) —
  chains the above plus worktree safety checks into one mandatory command.

These are procedural gates, not unconditional runtime enforcement everywhere in
the codebase — an agent must not treat "the sentinel didn't block it" as proof an
action was authorized. The operator instruction is the actual authorization; the
sentinel is a backstop.
