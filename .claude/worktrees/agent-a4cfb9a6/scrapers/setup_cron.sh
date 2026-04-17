#!/bin/bash
# VÉLØ Daily Scraper Cron Setup

echo "🔮 Setting up VÉLØ daily scraper cron job..."

# Create cron job that runs daily at 2 AM
CRON_JOB="0 2 * * * /usr/bin/python3.11 /home/ubuntu/velo-oracle/scrapers/velo_scraper.py daily >> /home/ubuntu/velo-oracle/logs/scraper.log 2>&1"

# Create logs directory
mkdir -p /home/ubuntu/velo-oracle/logs

# Add to crontab
(crontab -l 2>/dev/null | grep -v "velo_scraper.py"; echo "$CRON_JOB") | crontab -

echo "✅ Cron job installed:"
echo "   - Runs daily at 2:00 AM"
echo "   - Scrapes yesterday's results"
echo "   - Scrapes today's racecards"
echo "   - Imports data to database"
echo "   - Logs to: /home/ubuntu/velo-oracle/logs/scraper.log"
echo ""
echo "Current crontab:"
crontab -l | grep velo_scraper
echo ""
echo "To manually run the scraper:"
echo "  python3.11 /home/ubuntu/velo-oracle/scrapers/velo_scraper.py daily"

