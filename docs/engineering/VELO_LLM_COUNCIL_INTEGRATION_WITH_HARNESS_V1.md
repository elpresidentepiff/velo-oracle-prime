# VELO LLM Council Integration With Harness V1

**Status:** DEFINED

## 1. The Council Does Not Replace the Harness

The operational harness controls execution before and during work.  
The LLM Council audits the completed run after execution.

## 2. The Council Audits the Harness Output

The council reads the harness return, reviews evidence, and decides whether the work deserves trust.

## 3. Council Verification Duties

The council must verify:

- mission compliance
- file discipline
- artifact completeness
- evidence quality
- safety status
- contradiction handling
- commit scope

## 4. Council Verdicts

- `COUNCIL_PASS`
- `COUNCIL_PASS_WITH_WARNINGS`
- `COUNCIL_REJECT`
- `COUNCIL_BLOCKED`

## 5. Live-Learning Restriction

The council cannot approve live learning if `HFS_TRAINING_SAFE = FALSE`.

## 6. Production-Change Restriction

The council cannot approve production scoring changes from shadow-only evidence.

## 7. Forbidden-File Rule

The council must reject any result with forbidden dirty files.

## 8. Council Audit Sequence

1. read the mission checklist
2. read the execution return schema
3. inspect artifacts
4. inspect tests and exit codes
5. inspect forbidden-file status
6. inspect safety fields
7. issue verdict

## 9. Relationship Summary

- harness prevents the crime
- council judges the case
