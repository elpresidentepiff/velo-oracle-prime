# VELO Operational Harness Protocol V1

**Status:** ACTIVE_DRAFT  
**Mission Owner:** VELO Command Authority  
**Task Type:** VELO agent harness architecture, execution control protocol, and gate checklist system  
**Next Gate:** `REAL_HFS_DRY_RUN_NO_WRITE`  
**HFS_TRAINING_SAFE:** `FALSE`

## 1. Executive Summary

VELO is moving from ad hoc agent execution to controlled harness execution. Future agent work must run inside a formal operational harness that defines scope, permissions, tests, evidence requirements, and stop conditions before any implementation begins.

## 2. Purpose

The harness exists to enforce:

- command discipline
- file discipline
- evidence discipline
- safety discipline

It is designed to stop agent drift, uncontrolled edits, fake PASS reports, scope creep, unsafe commits, and "while I was there" changes.

## 3. Harness Architecture

Canonical execution path:

`Planner -> Generator -> Evaluator -> Reject/Repair -> Improve -> LLM Council -> Commit/Next Gate`

Phases:

1. **Plan**
   Define the mission, scope, permissions, files, commands, tests, and verdict rules.
2. **Build**
   Implement only inside the allowed scope.
3. **Test**
   Verify artifacts, diffs, safety boundaries, and command results.
4. **Reject / Repair**
   Block forward motion if evidence contradicts claims.
5. **Improve**
   Make bounded corrections only.
6. **Council Sign-off**
   Audit the completed run.
7. **Next Gate**
   Allow progression only when the gate is explicitly named and safe.

## 4. Planner Role

Planner is responsible for:

- mission definition
- current status
- allowed files
- forbidden files
- commands to run
- required artifacts
- pass conditions
- fail and blocked conditions
- stop condition
- rollback plan
- return schema
- commit permission

Planner does not implement code and does not mark work complete without evaluator evidence.

## 5. Generator Role

Generator is responsible for:

- creating only requested artifacts
- editing only allowed files
- running only authorized commands
- reporting exact outputs
- never widening scope
- never touching forbidden files
- never claiming PASS without evidence
- never committing unless explicitly authorized

## 6. Evaluator Role

Evaluator is responsible for:

- running tests
- checking diffs
- checking forbidden files
- checking Supabase write status
- checking live state mutation
- checking artifact completeness
- checking JSON structure
- checking commit scope
- rejecting contradictions
- forcing repair when evidence does not match claim

Evaluator must distrust claims until verified.

## 7. Reject / Repair Loop

If any issue appears, work must not proceed.

Examples:

- forbidden file dirty
- missing artifact
- failed test
- contradictory metrics
- fake PASS
- Supabase write attempted
- live sentient state touched
- HFS marked safe without proof

Reject/Repair loop rule:

1. stop forward motion
2. record the contradiction
3. repair only inside scope
4. re-run the required tests
5. return updated evidence

## 8. Improve / Commit Loop

Commit is allowed only when all of the following are true:

- tests pass
- forbidden files are clean
- artifacts are present
- return schema is complete
- council sign-off is complete if required
- commit scope is verified

Without explicit commit permission, the loop ends at artifact return only.

## 9. Verdict Definitions

**PASS**  
All required artifacts exist, tests pass, forbidden files are clean, safety gates remain active, and evidence supports the verdict.

**PARTIAL**  
Useful work completed, but one or more non-critical requirements remain incomplete. No promotion allowed.

**BLOCKED**  
Work cannot proceed due missing credentials, dirty forbidden files, missing source data, unsafe state, or failed preflight.

**FAIL**  
Work violated safety rules, changed forbidden files, produced false claims, failed tests, or created unsafe output.

## 10. Evidence Requirements

Every run must include:

- `TASK_TYPE`
- `COMMANDS_RUN`
- `EXIT_CODES`
- `FILES_CREATED`
- `FILES_CHANGED`
- `FORBIDDEN_FILES_DIRTY`
- `TESTS_PASSED`
- `TESTS_FAILED`
- `SUPABASE_WRITES_ATTEMPTED`
- `LIVE_SENTIENT_STATE_TOUCHED`
- `HFS_TRAINING_SAFE`
- `VERDICT`

## 11. Production Protection Rules

- no production scoring change without a separate gate
- no dashboard edits during backend gates
- no SSL bypass ever
- no silent Supabase writes
- no live sentient state mutation
- no HFS write until dry-run proves safety

## 12. HFS-Specific Rules

`HFS_TRAINING_SAFE` remains `FALSE` until:

- real no-write dry-run passes
- timestamp safety is proven
- leakage-risk rows are isolated
- provenance exists
- sample rows are verified
- controlled write is explicitly authorized

## 13. Sentient Loop Rules

- outcome-only shadow learning may continue
- live learning remains blocked
- `data/sentient_state.json` must not be touched
- `data/sentient_state_shadow.json` may only be touched by authorized shadow-learning tasks

## 14. Shadow Analysis Rules

Shadow analysis may run only when:

- no production scoring changes occur
- no model weights change
- Supabase writes are false
- HFS features are not falsely marked safe
- output clearly states whether selection changed or only calibration changed

## 15. Commit Rules

No commit unless:

- explicit commit permission exists in the mission
- staged files are listed
- forbidden files are not staged
- `git diff --cached` is reviewed
- commit hash is returned

## Operating Notes

- The harness is the preventive control.
- The council is the adjudication layer.
- `HFS_TRAINING_SAFE` remains `FALSE`.
- The next technical gate after this protocol is `REAL_HFS_DRY_RUN_NO_WRITE`.
