#!/bin/bash
# VÉLØ PRIME Master Orchestrator
# Enforces all locks before any operation

set -e

PRIME_DIR="/home/ubuntu/velo-oracle-prime"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔐 VÉLØ PRIME MASTER ORCHESTRATOR${NC}"
echo "===================================="

# LOCK 1: Preflight checks
echo -e "\n${YELLOW}1️⃣  Running preflight checks...${NC}"
if ! "$SCRIPT_DIR/preflight.sh"; then
    echo -e "${RED}❌ Preflight failed - refusing to proceed${NC}"
    exit 1
fi

# LOCK 2: Completeness gate
echo -e "\n${YELLOW}2️⃣  Checking data completeness...${NC}"
if ! python3 "$SCRIPT_DIR/src/completeness_gate.py"; then
    echo -e "${RED}❌ Data incomplete - refusing to proceed${NC}"
    exit 1
fi

# LOCK 3: Backup before operations
echo -e "\n${YELLOW}3️⃣  Creating backup...${NC}"
"$SCRIPT_DIR/backup.sh"

echo -e "\n${GREEN}✅ ALL LOCKS PASSED - SAFE TO PROCEED${NC}"
echo ""
echo "Available operations:"
echo "  python3 src/layer_x.py          - Generate verdicts"
echo "  python3 src/file_ingest.py      - Ingest race data"
echo "  python3 src/verify.py           - Verify database"
echo ""
echo "To run any operation, execute it directly."
echo "This script enforces locks but does not execute operations."
