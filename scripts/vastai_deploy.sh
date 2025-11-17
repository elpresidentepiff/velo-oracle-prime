#!/bin/bash
#
# VÉLØ Oracle - Vast.ai Deployment Script
#
# Deploys VÉLØ to a Vast.ai instance for full-scale training
#
# Prerequisites:
# - Vast.ai account with instance running
# - SSH access to instance
# - raceform.csv uploaded to instance
#
# Usage: ./scripts/vastai_deploy.sh <instance_id>
#

set -e

INSTANCE_ID="${1:-}"

if [ -z "$INSTANCE_ID" ]; then
    echo "Error: Instance ID required"
    echo ""
    echo "Usage: $0 <instance_id>"
    echo ""
    echo "Example: $0 12345"
    exit 1
fi

echo "VÉLØ Oracle - Vast.ai Deployment"
echo "================================="
echo ""
echo "Instance ID: $INSTANCE_ID"
echo ""

# Get instance details
echo "Fetching instance details..."
INSTANCE_INFO=$(vastai show instance $INSTANCE_ID 2>/dev/null || echo "")

if [ -z "$INSTANCE_INFO" ]; then
    echo "Error: Instance $INSTANCE_ID not found"
    echo ""
    echo "Available instances:"
    vastai show instances
    exit 1
fi

echo "✓ Instance found"
echo ""

# Get SSH connection details
SSH_HOST=$(vastai ssh-url $INSTANCE_ID | cut -d'@' -f2 | cut -d':' -f1)
SSH_PORT=$(vastai ssh-url $INSTANCE_ID | cut -d':' -f2)

echo "SSH Details:"
echo "  Host: $SSH_HOST"
echo "  Port: $SSH_PORT"
echo ""

# Create deployment package
echo "Creating deployment package..."
DEPLOY_DIR="/tmp/velo_deploy_$(date +%s)"
mkdir -p "$DEPLOY_DIR"

# Copy project files
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='.pytest_cache' --exclude='venv' --exclude='data' \
    . "$DEPLOY_DIR/"

# Create deployment tarball
cd "$DEPLOY_DIR"
tar czf velo-oracle.tar.gz .
cd -

echo "✓ Package created: $(du -h $DEPLOY_DIR/velo-oracle.tar.gz | cut -f1)"
echo ""

# Upload to instance
echo "Uploading to Vast.ai instance..."
scp -P $SSH_PORT "$DEPLOY_DIR/velo-oracle.tar.gz" root@$SSH_HOST:/root/

echo "✓ Upload complete"
echo ""

# Deploy on instance
echo "Deploying on instance..."
ssh -p $SSH_PORT root@$SSH_HOST << 'REMOTE_SCRIPT'
set -e

echo "Extracting package..."
mkdir -p /workspace/velo-oracle
cd /workspace/velo-oracle
tar xzf /root/velo-oracle.tar.gz

echo "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3-pip postgresql postgresql-contrib

echo "Installing Python dependencies..."
pip3 install --quiet -r requirements.txt

echo "Setting up PostgreSQL..."
service postgresql start
sudo -u postgres psql -c "CREATE DATABASE velo_oracle;" || true
sudo -u postgres psql -c "CREATE USER velo WITH PASSWORD 'velo123';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE velo_oracle TO velo;" || true

echo "Running database migrations..."
export DATABASE_URL="postgresql://velo:velo123@localhost/velo_oracle"
alembic upgrade head

echo "Creating directories..."
mkdir -p /var/velo/memory
mkdir -p /var/log/velo

echo "✓ Deployment complete"
echo ""
echo "VÉLØ Oracle is ready on Vast.ai instance"
echo ""
echo "Next steps:"
echo "  1. Upload raceform.csv to /workspace/velo-oracle/data/"
echo "  2. Run training: python3 scripts/train_benter_chunked.py"
echo "  3. Run backtest: python3 scripts/backtest_convergence.py"
REMOTE_SCRIPT

echo ""
echo "================================="
echo "✓ Deployment Complete"
echo "================================="
echo ""
echo "Connect to instance:"
echo "  ssh -p $SSH_PORT root@$SSH_HOST"
echo ""
echo "Project location:"
echo "  /workspace/velo-oracle"
echo ""
echo "Next steps:"
echo "  1. Upload raceform.csv"
echo "  2. Run full training"
echo "  3. Execute comprehensive backtests"
echo ""

# Cleanup
rm -rf "$DEPLOY_DIR"

