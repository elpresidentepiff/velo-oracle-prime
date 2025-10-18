# VÉLØ Oracle 2.0 - Deployment Guide

This guide will help you deploy VÉLØ Oracle 2.0 to GitHub and set up the system for production use.

## Prerequisites

Before deploying, ensure you have:

1. **GitHub Account** with access to create repositories
2. **PostgreSQL Server** (local or cloud-based like Supabase, AWS RDS, etc.)
3. **API Credentials**:
   - Betfair account with API access
   - The Racing API subscription
4. **Python 3.10+** installed on your deployment environment

## Step 1: Create GitHub Repository

The local repository is ready to be pushed to GitHub. You need to create the repository manually on GitHub first.

1. Go to [GitHub](https://github.com) and log in
2. Click the "+" icon in the top right and select "New repository"
3. Repository name: `velo-oracle`
4. Description: "VÉLØ Oracle 2.0 - AI-Powered Horse Racing Prediction Engine"
5. Choose **Private** (recommended for proprietary systems)
6. **DO NOT** initialize with README, .gitignore, or license (we already have these)
7. Click "Create repository"

## Step 2: Push Local Repository to GitHub

Once you've created the repository on GitHub, connect your local repository and push:

```bash
cd /home/ubuntu/velo-oracle

# Add GitHub remote (replace with your actual GitHub username)
git remote add origin https://github.com/elpresidentepiff/velo-oracle.git

# Push all commits to GitHub
git push -u origin main
```

If prompted for credentials, use your GitHub username and a **Personal Access Token** (not your password). You can create a token at: https://github.com/settings/tokens

## Step 3: Set Up PostgreSQL Database

### Option A: Local PostgreSQL

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql
```

In the PostgreSQL prompt:
```sql
CREATE DATABASE velo_racing;
CREATE USER velo_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE velo_racing TO velo_user;
\q
```

### Option B: Cloud PostgreSQL (Supabase)

1. Sign up at [Supabase](https://supabase.com)
2. Create a new project
3. Get your connection string from Project Settings > Database
4. Use the connection string in your `.env` file

## Step 4: Configure Environment Variables

Create a `.env` file in the project root (use `.env.example` as a template):

```bash
cd /home/ubuntu/velo-oracle
cp .env.example .env
nano .env
```

Fill in your credentials:

```env
# Betfair API
BETFAIR_USERNAME="your_betfair_username"
BETFAIR_PASSWORD="your_betfair_password"
BETFAIR_APP_KEY="your_betfair_app_key"

# The Racing API
RACING_API_KEY="your_racing_api_key"

# Database
VELO_DB_CONNECTION="postgresql://velo_user:your_secure_password@localhost:5432/velo_racing"
```

**Important**: Never commit the `.env` file to GitHub. It's already in `.gitignore`.

## Step 5: Install Dependencies

```bash
cd /home/ubuntu/velo-oracle

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 6: Initialize Database Schema

Run the database initialization script:

```bash
python -c "from src.data.db_connector import VeloDatabase; VeloDatabase().init_database()"
```

This will create all tables defined in `database/schema_v2.sql`.

## Step 7: Load Historical Data (Optional)

If you have historical CSV data from Kaggle:

```bash
python -c "
from src.data.data_pipeline import DataPipeline
pipeline = DataPipeline()
pipeline.load_historical_csv('path/to/your/data.csv', 'racing_data')
"
```

## Step 8: Test the System

Run a quick test to ensure everything is working:

```bash
# Test database connection
python src/data/db_connector.py

# Test Betfair API (requires valid credentials)
python src/integrations/betfair_api.py

# Test ML engine
python src/ml/ml_engine.py
```

## Step 9: Run VÉLØ Oracle

Start the main Oracle interface:

```bash
python src/agents/velo_prime.py
```

Or run the core oracle:

```bash
python src/core/oracle.py
```

## Production Deployment Considerations

### Security

1. **Never commit sensitive data** (API keys, passwords) to GitHub
2. Use **environment variables** for all credentials
3. Consider using a **secrets manager** (AWS Secrets Manager, HashiCorp Vault)
4. Enable **two-factor authentication** on GitHub

### Database

1. **Regular backups**: Set up automated database backups
2. **Connection pooling**: For production, consider using PgBouncer
3. **Monitoring**: Set up database monitoring (pg_stat_statements)

### API Rate Limits

1. **Betfair**: Be aware of API rate limits, implement exponential backoff
2. **The Racing API**: Use the built-in caching to minimize API calls

### Continuous Integration

Consider setting up GitHub Actions for automated testing:

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/
```

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check connection string format in `.env`
- Ensure database user has proper permissions

### API Authentication Failures

- Verify API credentials in `.env`
- Check Betfair account has API access enabled
- Ensure The Racing API subscription is active

### Import Errors

- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`

## Next Steps

1. **Train the ML model** with your historical data
2. **Set up automated data collection** (daily racecard scraping)
3. **Configure betting parameters** in `config/weights.json`
4. **Enable Genesis Protocol** for continuous learning

## Support

For issues or questions:
- Check the documentation in `/docs`
- Review the code comments in each module
- Consult the original Master Prompt and Developer Blueprint

---

**VÉLØ Oracle 2.0 is now ready for deployment. May the odds be ever in your favor.**

