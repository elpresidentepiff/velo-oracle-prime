# VÉLØ HOOK NOISE AUDIT — 2026-05-15

## Problem

Every agent session produces repeated console noise:

```
Error: Bun not found. Please install Bun: https://bun.sh
After installation, restart your terminal.
```

This fires on every hook event (afterShellExecution, afterMCPExecution, afterFileEdit, stop)
from the `claude-mem` plugin (thedotmack). It does not block execution but pollutes every
agent report and signal feed.

---

## Root Cause

The `claude-mem` plugin (installed, enabled) uses `bun-runner.js` to execute its worker scripts.
`bun-runner.js` calls `findBun()` which checks these paths in order:

1. PATH → `which bun` (not found)
2. `~/.bun/bin/bun` (Linux home — does not exist)
3. `/usr/local/bin/bun` (not present)
4. `/opt/homebrew/bin/bun` (not present)
5. `/home/linuxbrew/.linuxbrew/bin/bun` (not present)

It does not check the WSL2 Windows path `/mnt/c/Users/puror/.bun/bin/bun.exe`.

**Bun IS installed** — at the Windows path `/mnt/c/Users/puror/.bun/bin/bun.exe` (v1.3.11).
WSL2's binfmt interop layer can execute Windows `.exe` files directly from Linux.

**Confirmed:** Running `/mnt/c/Users/puror/.bun/bin/bun.exe --version` from WSL2 returns `1.3.11`.

The gap: `bun-runner.js` doesn't search Windows paths when running on Linux/WSL2.

---

## Fix — WSL2 Wrapper (no new software, 4 lines)

Create a wrapper at `~/.bun/bin/bun` that delegates to the existing Windows binary:

```bash
mkdir -p ~/.bun/bin
cat > ~/.bun/bin/bun << 'BUNWRAP'
#!/bin/bash
exec /mnt/c/Users/puror/.bun/bin/bun.exe "$@"
BUNWRAP
chmod +x ~/.bun/bin/bun
```

This places a Linux-executable shell script at the exact path `bun-runner.js` checks first
(`~/.bun/bin/bun`). The wrapper calls the real Windows Bun binary via WSL2 interop.

**No new software is installed.** Bun v1.3.11 is already present on the system.
The wrapper is a thin shim that resolves the WSL2/Windows path gap.

---

## Alternate Fixes (not recommended)

| Option | Notes |
|---|---|
| Install Bun natively in WSL2 (`curl -fsSL https://bun.sh/install \| bash`) | Cleaner long-term, but installs a new binary when the Windows one works |
| Disable `claude-mem` plugin in settings | Loses the claude-mem memory tool entirely |
| Modify `bun-runner.js` to check Windows paths | Plugin file is in the cache — changes would be overwritten on plugin update |
| Create a stub that silently exits | Silences noise but breaks claude-mem functionality |

---

## Impact Assessment

| Aspect | Assessment |
|---|---|
| Blocking | No — hook failure is non-fatal |
| Frequency | Every hook event (shell execution, file edit, session stop) |
| claude-mem plugin | Fully non-functional without Bun — memory saves are silently dropped |
| Signal pollution | Medium — noise in every agent report |
| Fix risk | Very low — wrapper is a 4-line shell script pointing to existing binary |

---

## Pending Operator Decision

Apply the WSL2 wrapper fix? The command is:

```bash
mkdir -p ~/.bun/bin && cat > ~/.bun/bin/bun << 'BUNWRAP'
#!/bin/bash
exec /mnt/c/Users/puror/.bun/bin/bun.exe "$@"
BUNWRAP
chmod +x ~/.bun/bin/bun
~/.bun/bin/bun --version
```

Expected output: `1.3.11`

Confirm before applying. Once applied, the `claude-mem` plugin will begin saving
hook observations through Bun. This is the intended behavior of the plugin.

---

## Artifacts

| File | Content |
|---|---|
| `bun-runner.js` | `/home/purorpurorestrepo1981/.claude/plugins/marketplaces/thedotmack/plugin/scripts/bun-runner.js` |
| `bun-runner.js` (cache) | `/home/purorpurorestrepo1981/.claude/plugins/cache/thedotmack/claude-mem/12.1.0/scripts/bun-runner.js` |
| Bun Windows binary | `/mnt/c/Users/puror/.bun/bin/bun.exe` v1.3.11 |
| Proposed wrapper | `~/.bun/bin/bun` (does not exist yet) |

---

## Version History

| Version | Date | Notes |
|---|---|---|
| V1 | 2026-05-15 | Initial audit. WSL2 wrapper fix identified. Pending operator approval. |
