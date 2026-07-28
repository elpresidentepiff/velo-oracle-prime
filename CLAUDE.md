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
- Fix 6 `VELO_G_SHADOW_MODE=live`: **BLOCKED** — G uniformly halves VP (avg 0.380→0.196); flipping live would kill Tier A picks. Doctrine strength collapse must be diagnosed and reset first.

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

This project is indexed by GitNexus as **velo-oracle-prime** (20301 symbols, 42785 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/velo-oracle-prime/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/velo-oracle-prime/context` | Codebase overview, check index freshness |
| `gitnexus://repo/velo-oracle-prime/clusters` | All functional areas |
| `gitnexus://repo/velo-oracle-prime/processes` | All execution flows |
| `gitnexus://repo/velo-oracle-prime/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

**Index is currently STALE** — last indexed 2026-07-08, current branch has many commits since. Embeddings: 0 (never generated). Re-run after committing:

```bash
npx gitnexus analyze
```

Add `--embeddings` for semantic search (first time is slow, subsequent runs are incremental):

```bash
npx gitnexus analyze --embeddings
```

Note: if disk is full, `npx gitnexus analyze` will fail. Free space first.

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
