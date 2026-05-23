# Claude Hook Noise — Local Hygiene Note

**Date:** 2026-05-23  
**Classification:** Local workstation issue — not a VÉLØ pipeline failure  
**Action required:** Local fix only. Do not commit workstation-specific paths or binaries.

---

## Symptom

Repeated error messages appearing in Claude Code terminal output during commits and tool calls:

```
Error: Cannot find module '/path/to/worker-service.cjs'
```

or similar variants referencing:
- `worker-service.cjs`
- `claude-mem`
- MCP plugin worker processes

The error repeats on every git operation, file edit, or tool use hook trigger.

---

## Diagnosis

This is a Claude Code **PostToolUse hook** or **MCP plugin** misconfiguration on the local workstation. Specifically, the `claude-mem` plugin (or a similar MCP server) is registered in Claude Code settings but its worker binary (`worker-service.cjs`) is missing from the expected path.

**This is not:**
- A VÉLØ codebase error
- A failed commit or pipeline step
- A Supabase connection failure
- A Python import failure
- A scoring pipeline issue
- An ops worker failure

**This is:**
- A Claude Code local settings issue
- A missing or misplaced MCP plugin binary
- A workstation-specific path problem

---

## Impact Assessment

| Area | Impact |
|---|---|
| VÉLØ scoring pipeline | None |
| Shadow learning | None |
| Supabase writes | None |
| Git commits | None (commits succeed, the error is cosmetic) |
| Mission Control | None |
| Telegram delivery | None |

The error is **non-blocking**. All commits, file writes, and tool operations succeed normally. The error appears in stderr/console output only.

---

## Recommended Fix (Local Only)

Check Claude Code settings for registered hooks:

```bash
cat ~/.claude/settings.json | grep -A5 "hooks"
# or
cat ~/.claude/settings.local.json | grep -A5 "hooks"
```

Look for a `PostToolUse` hook or MCP server entry pointing to `worker-service.cjs`. Either:

1. **Remove the hook** if the plugin is no longer needed
2. **Reinstall the plugin** via its package manager (npm/npx) to restore the missing binary
3. **Update the path** in the hook configuration if the binary moved

Do not commit any changes to VÉLØ codebase files to fix this — it is purely a local Claude Code configuration issue.

---

## What Not To Do

```
Do NOT add error-handling code to VÉLØ scripts for this
Do NOT add the worker-service.cjs binary to the VÉLØ repo
Do NOT commit .claude/ directory contents
Do NOT add workstation-specific paths to CLAUDE.md
```

---

## Classification

```
error_source:        LOCAL_CLAUDE_CODE_HOOK
velo_codebase_bug:   False
pipeline_failure:    False
commit_failure:      False
blocking:            False
fix_location:        local ~/.claude/ settings only
```
