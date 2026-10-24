# VÉLØ: One Truth / One Path

Decision date: 2026-10-18. Scope: target architecture, not a claim that every Railway service already follows it.

## Canonical chain
`velo-oracle-prime/main` (reviewed source) -> identified Railway scoring service and immutable deployed SHA -> timestamped pre-race runner prediction snapshot (`run_id`, race ID, runner ID, source/hash) -> certified official race results -> Sigma reconciliation -> immutable `velo_learning_events` + evidence/learned-pattern log -> **offline Evo² challenger proposal** -> frozen forward-time holdout comparison -> operator review -> reviewed model version/commit -> deliberately deployed canonical scoring service.

Production source of truth is **not** a mutable shadow-state file. Supabase stores the evidence; an approved, versioned model artifact and deployed commit determine production inference. Every result has one verified source classification and never silently promotes an experiment.

## Current work
- Evo² issue #167 and PR #168: the only active improvement implementation lane.
- Issue #169: model evidence/source-completeness dependency; do not treat 5,969 scorecards as 5,969 races.
- Issue #170: read-only deployed-code-path audit. No unrelated service refactoring until mapped.
- `hermes-agent` is RETIRED by owner confirmation. Exclude from active incident count and Evo² execution.
- `velo-oracle` legacy repo and `feature/v10-launch` ingestion branch must not be given new roles until independently verified; no silent routing or deletion.

## Required Evo² milestones
1. Ingest only verified, immutable, timestamped race-level outcomes and prior predictions.
2. Proposer produces a versioned hypothesis with no access to held-out outcomes.
3. Evaluator compares matched races across Prime and challenger, accounts for non-runners and documented source completeness. Run no promotion analysis when result completeness is false.
4. Reflector produces reasoned REJECT or REVIEW_REQUIRED with a hash of inputs/results.
5. Existing 300-clean-runner threshold, identity safeguards, no contamination, plus forward-date and operator gate remain mandatory.
6. Only a human-reviewed PR changes approved model code; deployment SHA is recorded and compared to the prediction audit.

## Non-negotiables
No independent 'truth' tables, shadow-to-live shortcuts, invisible inference mutations, automatic deployment, uncontrolled agents, or results from incomplete sources presented as certified. For every divergence, use `docs/research/VELO_LIVING_AUDIT_REGISTER.md`: evidence, severity, effect, state and next action.
