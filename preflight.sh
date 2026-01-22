#!/bin/bash
# VÉLØ PRIME Preflight Checks
# Lock 1: No-run without persistence
# Must pass before any operation

set -e

PRIME_DIR="/home/ubuntu/velo-oracle-prime"
DB_PATH="$PRIME_DIR/velo.db"
SRC_PATH="$PRIME_DIR/src"
GIT_PATH="$PRIME_DIR/.git"

echo "🔒 VÉLØ PRIME PREFLIGHT CHECKS"
echo "================================"

# Check 1: Database exists
if [ ! -f "$DB_PATH" ]; then
    echo "❌ FAIL: Database not found: $DB_PATH"
    exit 1
fi
echo "✅ Database exists: $DB_PATH"

# Check 2: Source code exists
if [ ! -d "$SRC_PATH" ]; then
    echo "❌ FAIL: Source code not found: $SRC_PATH"
    exit 1
fi
echo "✅ Source code exists: $SRC_PATH"

# Check 3: Git repository exists
if [ ! -d "$GIT_PATH" ]; then
    echo "❌ FAIL: Git repository not found: $GIT_PATH"
    exit 1
fi
echo "✅ Git repository exists: $GIT_PATH"

# Check 4: Git is clean or committed
cd "$PRIME_DIR"
if ! git diff-index --quiet HEAD --; then
    echo "❌ FAIL: Uncommitted changes detected"
    echo "   Run: git add -A && git commit -m 'message'"
    exit 1
fi
echo "✅ Git working tree clean"

# Check 5: Git has commits
if ! git rev-parse HEAD > /dev/null 2>&1; then
    echo "❌ FAIL: Git has no commits"
    exit 1
fi
echo "✅ Git has commit history"

# Check 6: Remote is configured
if [ -z "$(git remote -v)" ]; then
    echo "⚠️  WARNING: No git remote configured"
    echo "   Commits are local only - not truly persisted"
    echo "   Configure remote: git remote add origin <url>"
fi

echo ""
echo "✅ PREFLIGHT PASSED - Safe to proceed"
exit 0
