# VELO Gate Checklist Template V1

Use this template for future Gemini, Codex, or Claude missions.

```text
TASK_TYPE:
CURRENT_STATUS:
MISSION:
WHY:
ABSOLUTE_RULES:
FILES_TO_READ:
FILES_ALLOWED_TO_CREATE:
FILES_ALLOWED_TO_CHANGE:
FORBIDDEN_FILES:
COMMANDS_TO_RUN:
REQUIRED_ARTIFACTS:
REQUIRED_TESTS:
PASS_CONDITIONS:
PARTIAL_CONDITIONS:
BLOCKED_CONDITIONS:
FAIL_CONDITIONS:
STOP_CONDITION:
ROLLBACK_PLAN:
COMMIT_ALLOWED:
FILES_ALLOWED_TO_COMMIT:
RETURN_ONLY:
NEXT_GATE:
```

## Practical Use Rules

- define scope before implementation
- keep allowed files narrow
- name forbidden files explicitly
- list exact commands
- define exact pass conditions
- define stop condition before work starts
- define commit permission explicitly

## Standard PASS Conditions

- all required artifacts exist
- required tests pass
- forbidden files are clean
- no Supabase writes attempted unless explicitly allowed
- no live state touched
- return schema is complete

## Standard BLOCKED Conditions

- missing credentials
- missing source data
- forbidden file dirty
- unsafe state
- failed preflight

## Standard FAIL Conditions

- forbidden file changed
- false PASS claim
- unsafe write attempted
- missing evidence for claimed result

## Return-Only Rule

If `COMMIT_ALLOWED` is false, return artifacts and evidence only.
