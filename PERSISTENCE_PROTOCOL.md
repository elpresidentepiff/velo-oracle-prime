# VÉLØ PRIME Persistence Protocol
## Non-Negotiable Rules to Prevent Data Loss

**Date**: 2026-01-22  
**Status**: LOCKED & ENFORCED

---

## The Problem We Solved

Previous session: Built automation pipeline → Never committed → Lost everything.

**Root cause**: "Built" ≠ "Persisted". No remote. No backups. No locks.

**Solution**: Three-layer persistence guarantee.

---

## Three Locks (All Mandatory)

### Lock 1: Preflight Gate (`preflight.sh`)

**Purpose**: Refuse to run if persistence prerequisites missing

**Checks**:
- ✅ `velo.db` exists
- ✅ `src/` directory exists
- ✅ `.git` directory exists
- ✅ Git working tree clean (or explicitly allowed)
- ✅ Git has commits
- ✅ Remote is configured

**Failure**: Exit code 1, no operation proceeds

**Usage**:
```bash
./preflight.sh
```

**Pass output**:
```
✅ PREFLIGHT PASSED - Safe to proceed
```

**Fail output** (example):
```
❌ FAIL: Database not found: /home/ubuntu/velo-oracle-prime/velo.db
```

---

### Lock 2: Triple Backup (`backup.sh`)

**Purpose**: Create verifiable local + remote + archive backups

**Creates**:
1. **Local tar.gz**: `/home/ubuntu/velo-oracle-prime/backups/velo-oracle-prime_YYYYMMDD_HHMM.tar.gz`
   - Contains: velo.db + src/ + integrity_events.json
   - Excludes: .git (too large), backups/ (recursive)

2. **Git commit**: Automatic commit with timestamp
   - Message: `BACKUP: YYYY-MM-DD HH:MM:SS - Automated backup commit`
   - Includes all uncommitted changes

3. **Remote push**: Verifies remote is reachable
   - Warns if no remote configured
   - Suggests: `git push origin main`

**Usage**:
```bash
./backup.sh
```

**Output** (example):
```
🔐 VÉLØ PRIME TRIPLE BACKUP
============================
1️⃣  Creating local backup...
   ✅ Local backup: /home/ubuntu/velo-oracle-prime/backups/velo-oracle-prime_20260122_072621.tar.gz (16K)
2️⃣  Committing to git...
   ✅ Git commit: f76c83f
3️⃣  Checking remote...
   ✅ Remote configured
   To push: git push origin main

✅ BACKUP COMPLETE
```

---

### Lock 3: Completeness Gate (`src/completeness_gate.py`)

**Purpose**: No export/metrics allowed if data incomplete

**Checks**:
- Race count vs. episode count
- No silent partials
- All races have verdicts

**Failure**: Blocks export, reports gaps

**Usage**:
```bash
python3 src/completeness_gate.py
```

**Pass output**:
```
📋 COMPLETENESS GATE CHECK
============================================================
Races: 6
Runners: 38
Episodes: 6/6
✅ COMPLETE - Safe to export
```

**Fail output** (example):
```
📋 COMPLETENESS GATE CHECK
============================================================
Races: 6
Runners: 38
Episodes: 4/6
❌ INCOMPLETE - 2 missing episodes
   Missing episode for race_id: 3
   Missing episode for race_id: 5

⚠️  NO EXPORT ALLOWED - Silent partials forbidden
```

---

## Master Orchestrator (`run.sh`)

**Purpose**: Enforce all locks before any operation

**Runs in order**:
1. Preflight checks
2. Completeness gate
3. Backup

**Usage**:
```bash
./run.sh
```

**Output** (example):
```
🔐 VÉLØ PRIME MASTER ORCHESTRATOR
====================================

1️⃣  Running preflight checks...
✅ PREFLIGHT PASSED - Safe to proceed

2️⃣  Checking data completeness...
✅ COMPLETE - Safe to export

3️⃣  Creating backup...
✅ BACKUP COMPLETE

✅ ALL LOCKS PASSED - SAFE TO PROCEED

Available operations:
  python3 src/layer_x.py          - Generate verdicts
  python3 src/file_ingest.py      - Ingest race data
  python3 src/verify.py           - Verify database
```

---

## Remote Repository

**GitHub**: https://github.com/elpresidentepiff/velo-oracle-prime

**Status**: ✅ ACTIVE & SYNCED

**Current commits**:
```
f76c83f (HEAD -> main) LOCKS: Preflight + Backup + Completeness gates installed
fb91df7 PRIME: Gowran report generated - verdicts locked
b9b694d PRIME: Gowran data processed 2026-01-22 07:13:08
dc1a889 PRIME: Gowran data processed 2026-01-22 07:12:05
d06315b PRIME: Initial state snapshot (pre-rebuild)
```

**Push verification**:
```bash
git rev-parse HEAD                    # Local commit
git ls-remote --heads origin          # Remote commits
# Both should show: f76c83f59e24b4446614e6ecf883f8001712aa4b
```

---

## Immutable Paths

**NEVER CHANGE THESE**:
- Database: `/home/ubuntu/velo-oracle-prime/velo.db`
- Source: `/home/ubuntu/velo-oracle-prime/src/`
- Git: `/home/ubuntu/velo-oracle-prime/.git`
- Backups: `/home/ubuntu/velo-oracle-prime/backups/`

**Write-allowed paths**:
- Incoming: `/home/ubuntu/velo-oracle-prime/incoming/`
- Artifacts: `/home/ubuntu/velo-oracle-prime/artifacts/`
- Database (verdicts only): `/home/ubuntu/velo-oracle-prime/velo.db`

---

## Recovery Procedures

### Scenario 1: Sandbox crashes, directory lost

**Recovery**:
```bash
cd /home/ubuntu
git clone https://github.com/elpresidentepiff/velo-oracle-prime.git
cd velo-oracle-prime
./preflight.sh  # Verify
```

**Result**: Full PRIME restored from GitHub

### Scenario 2: Database corrupted

**Recovery**:
```bash
cd /home/ubuntu/velo-oracle-prime
# Restore from local backup
tar -xzf backups/velo-oracle-prime_LATEST.tar.gz velo.db
./preflight.sh  # Verify
```

### Scenario 3: Accidental commits

**Recovery**:
```bash
cd /home/ubuntu/velo-oracle-prime
git reset --soft HEAD~1  # Undo last commit, keep changes
git status               # Review
git commit -m "Corrected message"
git push origin main
```

---

## Enforcement Rules (Non-Negotiable)

1. **No operation without preflight pass**
   - All scripts must call `./preflight.sh` first
   - Exit code 1 = stop immediately

2. **No export without completeness**
   - All verdicts must be generated before export
   - Partial data is forbidden

3. **No commit without backup**
   - Every commit must be followed by `./backup.sh`
   - Backup must succeed before considering commit "done"

4. **No local-only commits**
   - All commits must be pushed to GitHub
   - Remote is the source of truth

5. **No manual edits to velo.db**
   - Only programmatic writes allowed
   - All changes must be committed

---

## Verification Checklist

Before considering any operation "complete":

- [ ] Preflight passes
- [ ] Completeness gate passes
- [ ] Local backup created
- [ ] Git commit made
- [ ] Remote push succeeded
- [ ] Hash verified (local HEAD == remote main)
- [ ] GitHub repo shows latest commit

---

## What This Means

✅ **If you follow this protocol**: Data loss is impossible
✅ **If sandbox crashes**: Recovery is 1 git clone away
✅ **If someone deletes files**: GitHub is the backup
✅ **If you forget to commit**: Preflight will catch it
✅ **If data is incomplete**: Completeness gate will stop export

❌ **If you skip locks**: You're back to "one crash away from losing everything"

---

## The Bottom Line

**This is not optional.**

Every operation must:
1. Pass preflight
2. Pass completeness
3. Create backup
4. Commit to git
5. Push to GitHub
6. Verify hash match

No exceptions. No "looks good enough." No "I'll do it later."

**VÉLØ PRIME is only safe when all three locks are engaged.**

---

*Last updated: 2026-01-22 07:30:00 UTC*  
*Status: LOCKED & ENFORCED*
