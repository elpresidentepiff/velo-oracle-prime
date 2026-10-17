# VÉLØ PRIME — Claude Code Context

> **SINGLE SOURCE OF TRUTH: `docs/current/ONE_TRUTH.md`**
> That file wins any conflict with this file or any other doc.

## Quick orientation

- **Operational law:** `docs/current/ONE_TRUTH.md`
- **Step-by-step daily commands (Steps 1–20):** `THE_ONE_TRUTH.md` (root)
- **Race day lifecycle:** `docs/current/RACE_DAY_RUNBOOK.md`
- **Learning gate:** `docs/current/LEARNING_ADMISSION_GATE.md`
- **VFU state:** `docs/current/VELO_VFU_TIMELINE_APPENDIX.md`
- **VCP (coherence protocol):** see VCP State section in ONE_TRUTH.md

## Hard laws (never override without operator approval)

1. Racing API is PERMANENTLY DECOMMISSIONED for live use. RP HTML is the only live source.
2. No live staking. Execution bridge is SIM/PAPER only with hard runtime guards.
3. Live model weights are FROZEN — no promotion without operator gate.
4. RPDC is horse-career memory. PDF intelligence must never overwrite RPDC fields.
5. Mission Control derives source truth from the observability packet — never by default. Missing = UNKNOWN.
6. Sigma Telegram format is LOCKED — never change it. Always use `run_results_sigma.py`.
7. No new numbered truth files. ONE_TRUTH.md is the only living truth.

## Learning Loop Status (audited 2026-07-28)

Full audit findings in ONE_TRUTH.md "LEARNING LOOP AUDIT" section. Summary for session context:

- **Playbook G IS learning** — 3,466 races, live state authorized 2026-07-26. Doctrine strengths have evolved (most near 0.0, LAY_THE_STORY=0.08, ENGINE_SUPREMACY=1.0 frozen).
- **G multiplier is NOT applied to VP** — gated by `VELO_G_SHADOW_MODE=shadow` (default). Every verdict has `g_shadow_multiplier` and `g_shadow_flags` logged. Backtest before flipping live.
- **VCP-03 now wired** — Step 20B in `run_full_raceday_eod.py` (fixed 2026-07-28). Count restarts at 0/10.
- **Gate enforcement: zero** — 12 gate conditions are procedural only. Runner hardcodes `learning_allowed=True`.
- **Council verdict faked** — runner copies its own verdict into `council_audit` file; never reads Step 16b output.
- **Calibration threshold too low** — VP > 0.35 = CALIBRATION_ERROR catches 57–85% of losses. Fix: raise to 0.55.

Fix order and status (2026-07-28):
- Fix 1 VCP-03 wire-in: **DONE** (`1f39fcf`) — Step 20B in `run_full_raceday_eod.py`
- Fix 2 Calibration 0.35→0.55: **DONE** (`f8fe12f`)
- Fix 3 Gate pre-flight: **DONE** (`38023e6`) — sigma PASS + council PASS_TO_LEARNING + MC OPEN enforced before learning
- Fix 4 Council verdict de-forged: **DONE** (`6f6b073`) — reads real `data/council_runs/council_run_{date}.json`
- Fix 5 G shadow backtest: **DONE** (`c57e555`) — `scripts/analysis/g_shadow_backtest.py` — 1,746 races ALL in STRONG_DAMPEN (~0.516×); zero amplify cases
- Fix 7 Doctrine collapse: **DONE** (`de0c2ea`) — LAY_THE_STORY now fires only MDS>0.55; SHADOW_TRACKING only SP>=10; both state files reset to 0.5 neutral. Multiplier 0.516→0.994 avg.
- Fix 6 `VELO_G_SHADOW_MODE=live`: **BLOCKED** — needs 3+ months post-reset data showing positive signal. Earliest 2026-10-28.

## Railway Status (audited 2026-07-28)

Railway runs ONE thing: the FastAPI dashboard (`app.main:app` on port 8080 → reads Supabase).
Scoring cron is DEAD — requires local RP browser session that cannot exist in a Railway container.
If remote dashboard access matters: keep it. If local-only: cancel Railway, run dashboard locally.
Do NOT attempt to wire scoring/EOD on Railway — structurally impossible without local browser.

## Session start

```bash
PYTHONPATH=. venv/bin/python scripts/ops/velo_session_start_check.py
```

Then follow Steps 1–20 in `THE_ONE_TRUTH.md`.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **velo-oracle-prime** (47115 symbols, 65382 relationships, 484 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/velo-oracle-prime/context` | Codebase overview, check index freshness |
| `gitnexus://repo/velo-oracle-prime/clusters` | All functional areas |
| `gitnexus://repo/velo-oracle-prime/processes` | All execution flows |
| `gitnexus://repo/velo-oracle-prime/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
