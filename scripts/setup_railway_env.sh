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
railway variables set SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0YnN4YnZmc3h0bmhhcmp2cWNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjM0ODgzNjksImV4cCI6MjA3OTA2NDM2OX0.iS1Sixo77BhZ2UQVwqVQcGOyBocSIy9ApABvsgLGmhY"

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
