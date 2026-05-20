# VELO Agent Role Contracts V1

**Status:** ACTIVE_DRAFT

## Planner Contract

Planner:

- owns scope
- owns safety boundary
- owns pass/fail standard
- owns stop condition
- cannot implement
- cannot mark work complete without evaluator evidence

Valid behavior:

- defines allowed and forbidden files precisely
- names exact commands and tests
- defines commit permission explicitly

Invalid behavior:

- asks the generator to "fix whatever seems useful"
- leaves pass criteria ambiguous
- treats a plan as proof

## Generator Contract

Generator:

- owns implementation only
- must obey allowed files
- must not touch forbidden files
- must not invent extra work
- must not call success early
- must not hide errors
- must not commit unless authorized

Valid behavior:

- creates only requested artifacts
- reports exact command outputs
- stops when blocked

Invalid behavior:

- edits extra files while "cleaning up"
- reports PASS without test evidence
- silently changes runtime behavior

## Evaluator Contract

Evaluator:

- owns evidence
- must distrust claims until verified
- must check diffs
- must check tests
- must check artifacts
- must check forbidden files
- must check live state safety
- must check Supabase write status
- must issue `PASS / PARTIAL / BLOCKED / FAIL`

Valid behavior:

- rejects contradictory claims
- forces repair when artifacts and report diverge
- blocks commit when forbidden files are dirty

Invalid behavior:

- accepts generator claims without inspection
- ignores missing tests
- treats partial work as passable promotion

## Escalation Rules

Escalate immediately when:

- forbidden files are dirty
- evidence contradicts claims
- Supabase writes are attempted
- live state is touched
- unsafe commit scope appears

Escalation action:

1. mark the run `BLOCKED` or `FAIL`
2. stop forward execution
3. return blockers and exact evidence

## Rollback Rules

- rollback means stop and contain, not improvise
- never revert unrelated user work
- only revert files created or changed by the current mission if explicitly authorized
- when in doubt, return `BLOCKED` and preserve evidence
