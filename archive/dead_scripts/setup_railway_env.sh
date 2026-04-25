#!/bin/bash
# VÉLØ Oracle - Railway Environment Setup Script
# ===============================================
# 
# This script sets up environment variables in Railway via CLI.
# 
# Prerequisites:
# - Railway CLI installed
# - Logged in to Railway (railway login)
# - In the correct project directory
#
# Usage:
#   ./scripts/setup_railway_env.sh

set -e

echo "🚂 VÉLØ Oracle - Railway Environment Setup"
echo "==========================================="

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Install it first:"
    echo "   npm install -g @railway/cli"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "❌ Not logged in to Railway. Run: railway login"
    exit 1
fi

echo ""
echo "Setting environment variables..."
echo ""

# Supabase
echo "📦 Supabase Configuration"
railway variables set SUPABASE_URL="https://ltbsxbvfsxtnharjvqcm.supabase.co"
# SUPABASE_KEY must be set via Railway dashboard — NEVER hardcode secrets in VCS.
if [ -z "$SUPABASE_KEY" ]; then
  echo "❌ SUPABASE_KEY not set in environment. Set via Railway dashboard or export before running."
  exit 1
fi
railway variables set SUPABASE_KEY="$SUPABASE_KEY"

# FastAPI Configuration
echo "⚙️  FastAPI Configuration"
railway variables set API_HOST="0.0.0.0"
railway variables set API_PORT="8000"
railway variables set LOG_LEVEL="INFO"

# Feature Flags
echo "🚩 Feature Flags"
railway variables set ENABLE_PREDICTION_LOGGING="true"
railway variables set ENABLE_MODEL_REGISTRY="true"
railway variables set ENABLE_CACHE="true"

echo ""
echo "✅ Environment variables set successfully!"
echo ""
echo "To verify, run: railway variables"
echo ""
echo "To trigger a redeploy, run: railway up"
