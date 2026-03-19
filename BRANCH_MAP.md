# VÉLØ BRANCH MAP
**Generated:** 2026-03-18 | **Canonical spine:** `main` @ `012608e`

---

## LIVE BRANCHES (tracked, merge-eligible)

| Branch | Last Commit | Hash | Status | Notes |
|---|---|---|---|---|
| `main` | 2026-03-18 | `012608e` | **CANON — Railway deploys from here** | Fast-forward from `feature/v10-launch` |
| `feature/v10-launch` | 2026-03-18 | `012608e` | **ACTIVE dev branch** | Identical to main post-merge. All new work goes here. |
| `feature/cheltenham-20260312` | 2026-03-11 | `c48817a` | EVIDENCE — read-only | Cheltenham Day 3 multi-model consensus report. Benchmark data. |
| `feature/sentient-feedback-loop` | 2026-03-10 | `1191e15` | MERGED (PR #52) | Kingmaker, fuzzy matching, Supabase persistence — already in main |
| `feature/spotlight-layer` | 2026-03-14 | `1cf8f7a` | MERGED (PR #53) | Spotlight NLP parser, ingestion worker — already in main |
| `feature/phase-3a-governance` | 2026-01-18 | `605a179` | DORMANT — recoverable | Proposal persistence + review gate. Not merged. |
| `feature/prefect-automation` | 2026-01-08 | `903b867` | DORMANT — orphaned | Prefect pipeline. No Prefect in prod. Low-value. |
| `feature/ops-phase1-checkpoint` | 2026-01-04 | `f5197a3` | ARCHIVED | nixpacks isolation. Already superseded. |

---

## COPILOT BRANCHES (GitHub Copilot generated, unreviewed)

| Branch | Hash | Status | Verdict |
|---|---|---|---|
| `copilot/replace-placeholder-agents` | `fb97e66` | MERGED (PR merged) | 5-agent system — already in main |
| `copilot/add-langgraph-agent-orchestration` | `47e3cff` | HELD BACK | Needs langgraph>=0.2.0. Not ready. Do not merge. |
| `copilot/harden-production-security` | `4d3dbd8` | MERGED | Security hardening — in main |
| `copilot/implement-production-smoke-tests` | `bab0e6d` | MERGED | /debug/routes protection — in main |
| `copilot/fix-supabase-httpx-compatibility` | `e2a777d` | MERGED | httpx 0.27.2 — in main |
| `copilot/fix-relative-import-errors` | `69e6c7d` | MERGED | PYTHONPATH handling — in main |
| `copilot/fix-railway-deployment` | `8c7dd39` | MERGED | nixpacks + healthcheck — in main |
| `copilot/fix-trpc-404-errors` | `d41ffad` | MERGED | /trpc/health dynamic — in main |
| `copilot/fix-prefect-logging` | `7bee030` | LOW VALUE | Prefect not in prod. Skip. |
| `copilot/fix-db-insertion-for-racecards` | `8d9020a` | LOW VALUE | Timestamp fix only. Skip. |
| `copilot/add-data-quality-tracking` | `7e463fa` | REVIEW NEEDED | Conflicts resolved. May have value. |
| `copilot/add-parse-quality-tracking` | `d0cf56b` | LOW VALUE | Redundant with spotlight. Skip. |
| `copilot/add-racing-post-pdf-parser` | `5025025` | SUPERSEDED | ingestion-spine already live. |
| `copilot/add-trainer-performance-stats` | `53bb8f6` | RECOVERABLE | Trainer stats module. Inspect before deciding. |
| `copilot/add-trpc-compatibility-layer` | `649e10d` | DEAD | tRPC not used in this stack. Archive. |
| `copilot/build-regression-protection-system` | `39fd786` | REVIEW NEEDED | Regression guard could be useful. |
| `copilot/set-up-great-expectations` | `cdaf294` | LOW VALUE | Great Expectations not adopted. |

---

## DEPENDABOT BRANCHES (automated dependency bumps)

All open. None merged. Current state:

| Branch | Target | Action |
|---|---|---|
| `dependabot/pip/workers/ingestion_spine/fastapi-0.135.1` | fastapi 0.135.1 | **MERGE** — ingestion-spine needs latest |
| `dependabot/pip/workers/ingestion_spine/pytest-9.0.2` | pytest dev | Merge with next dev cycle |
| `dependabot/pip/workers/ingestion_spine/ruff-0.15.6` | ruff dev | Merge with next dev cycle |
| `dependabot/pip/workers/ingestion_spine/pytest-asyncio-1.3.0` | pytest-asyncio | Merge with next dev cycle |
| `dependabot/pip/workers/ingestion_spine/ipython-9.11.0` | ipython dev | Merge with next dev cycle |
| `dependabot/pip/workers/ingestion_spine/pydantic-2.12.5` | pydantic | Test first — pydantic breaking changes |
| `dependabot/pip/workers/ingestion_spine/supabase-2.27.2` | supabase | **MERGE** — keep supabase current |
| `dependabot/pip/workers/ingestion_spine/pdfplumber-0.11.9` | pdfplumber | Merge with ingestion update |
| `dependabot/github_actions/actions/download-artifact-8.0.1` | GHA | Merge — security |
| `dependabot/github_actions/actions/checkout-6` | GHA | Merge — security |

---

## DEAD / ARCHIVED BRANCHES

| Branch | Reason |
|---|---|
| `master` | Legacy — pre-takeover. `864df4f` "VÉLØ TAKEOVER PACKAGE". Read-only reference only. |
| `worktree-agent-*` | Temporary worktree branches. Repo-cleanup commit `121392f`. Auto-generated. Delete. |
| `hotfix/quality-defaults-to-none` | `fc42213` — merged. Close. |

---

## BRANCH RULES

1. **`main`** — deploy target. Never commit directly. Merge only via fast-forward from `feature/v10-launch`.
2. **`feature/v10-launch`** — active development. All new work goes here.
3. **Copilot branches** — review before merging. Never auto-merge.
4. **`master`** — do not delete. Historical reference only.
5. **`feature/cheltenham-20260312`** — preserve. First real benchmark evidence.
