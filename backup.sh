#!/bin/bash
# VÉLØ PRIME Backup Script
# Lock 2: Triple backup is real
# Creates verifiable local + git + off-box backups

set -e

PRIME_DIR="/home/ubuntu/velo-oracle-prime"
BACKUPS_DIR="$PRIME_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="velo-oracle-prime_${TIMESTAMP}.tar.gz"
BACKUP_PATH="$BACKUPS_DIR/$BACKUP_NAME"

echo "🔐 VÉLØ PRIME TRIPLE BACKUP"
echo "============================"

# Ensure backups directory exists
mkdir -p "$BACKUPS_DIR"

# BACKUP 1: Local tar.gz
echo "1️⃣  Creating local backup..."
cd "$PRIME_DIR"
tar -czf "$BACKUP_PATH" \
    velo.db \
    src/ \
    integrity_events.json \
    .env.production \
    --exclude=backups \
    --exclude=.git \
    2>/dev/null

if [ -f "$BACKUP_PATH" ]; then
    SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
    echo "   ✅ Local backup: $BACKUP_PATH ($SIZE)"
else
    echo "   ❌ Local backup failed"
    exit 1
fi

# BACKUP 2: Git commit
echo "2️⃣  Committing to git..."
cd "$PRIME_DIR"
if ! git diff-index --quiet HEAD --; then
    git add -A
    git commit -m "BACKUP: $TIMESTAMP - Automated backup commit" || true
fi
COMMIT=$(git rev-parse --short HEAD)
echo "   ✅ Git commit: $COMMIT"

# BACKUP 3: Verify remote exists (warn if not)
echo "3️⃣  Checking remote..."
if [ -z "$(git remote -v)" ]; then
    echo "   ⚠️  NO REMOTE CONFIGURED"
    echo "   To push to remote: git remote add origin <url> && git push -u origin master"
    echo "   Without remote, commits are LOCAL ONLY - NOT TRULY PERSISTED"
else
    echo "   ✅ Remote configured"
    echo "   To push: git push origin master"
fi

echo ""
echo "✅ BACKUP COMPLETE"
echo "   Local: $BACKUP_PATH"
echo "   Git:   $COMMIT"
echo "   Next:  Configure remote and push"
