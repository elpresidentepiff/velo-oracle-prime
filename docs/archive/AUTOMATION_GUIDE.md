# VELO Oracle - Automation Guide

## 🤖 Automated Daily Predictions

VELO Oracle now includes fully automated daily prediction capabilities with Racing Post integration.

---

## 📁 New Modules

### `app/scrapers/racing_post.py`
- Scrapes daily UK/Ireland race cards from Racing Post
- Extracts: course, time, runners, jockeys, trainers, form, odds
- Supports paid account login for TS (Topspeed) and RPR ratings
- Rate-limited to respect Racing Post servers

### `app/pipeline/predictor.py`
- Automated prediction pipeline
- Loads VELO model and generates predictions
- Calculates edge (predicted probability - implied probability)
- Kelly Criterion stake sizing
- Filters high-value bets (>5% edge by default)

### `run_daily_predictions.py`
- Main automation script
- Runs complete pipeline: scrape → predict → filter → save
- Can be scheduled with cron or Railway

---

## 🚀 Quick Start

### Local Usage

```bash
# Set Racing Post credentials (optional - for TS/RPR ratings)
export RACING_POST_USERNAME="your_email@example.com"
export RACING_POST_PASSWORD="your_password"

# Run daily predictions
python run_daily_predictions.py
```

### Output

```
🏇 VELO ORACLE - DAILY PREDICTION PIPELINE
======================================================================
Date: 2025-11-24 14:30:00
Minimum edge: 5.0%

📅 Fetching races for 2025-11-24...
✅ Found 45 races

🤖 Generating predictions for 45 races...

[1/45] Ascot 14:30
  Top 3 predictions:
    1. HORSE_NAME: Edge 12.3%, Odds 5.50, Stake £4.50
    2. HORSE_NAME: Edge 8.1%, Odds 7.00, Stake £2.80
    3. HORSE_NAME: Edge 3.2%, Odds 3.50, Stake £0.00

...

📊 SUMMARY
======================================================================
Total races analyzed: 45
Total predictions: 387
High-value bets (>5% edge): 23

🎯 TOP 5 BETS:
1. Ascot 14:30 - HORSE_NAME
   Edge: 12.3%, Odds: 5.50, Stake: £4.50
2. Kempton 15:00 - HORSE_NAME
   Edge: 10.7%, Odds: 6.00, Stake: £3.90
...

💾 Saved to velo_predictions_20251124_143000.json
```

---

## ⏰ Automated Scheduling

### Option 1: Cron (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add this line to run every hour from 8 AM to 10 PM
0 8-22 * * * cd /path/to/velo-oracle && python3 run_daily_predictions.py >> logs/predictions.log 2>&1
```

### Option 2: Railway (Cloud)

1. **Deploy to Railway:**
   ```bash
   # Install Railway CLI
   npm install -g @railway/cli
   
   # Login
   railway login
   
   # Deploy
   railway up
   ```

2. **Set Environment Variables:**
   - `RACING_POST_USERNAME` (optional)
   - `RACING_POST_PASSWORD` (optional)

3. **Configure Cron:**
   - Railway supports cron jobs via the dashboard
   - Set schedule: `0 */2 * * *` (every 2 hours)
   - Or use Railway's built-in scheduler

### Option 3: GitHub Actions (Free)

```yaml
# .github/workflows/daily-predictions.yml
name: Daily Predictions

on:
  schedule:
    - cron: '0 8,12,16,20 * * *'  # 8 AM, 12 PM, 4 PM, 8 PM UTC
  workflow_dispatch:  # Manual trigger

jobs:
  predict:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run predictions
        env:
          RACING_POST_USERNAME: ${{ secrets.RACING_POST_USERNAME }}
          RACING_POST_PASSWORD: ${{ secrets.RACING_POST_PASSWORD }}
        run: |
          python run_daily_predictions.py
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: predictions
          path: velo_predictions_*.json
```

---

## 📊 Output Format

Predictions are saved to JSON files with this structure:

```json
{
  "timestamp": "2025-11-24T14:30:00",
  "summary": {
    "total_races": 45,
    "total_predictions": 387,
    "high_value_bets_count": 23,
    "min_edge": 0.05
  },
  "high_value_bets": [
    {
      "race_course": "Ascot",
      "race_time": "14:30",
      "race_date": "2025-11-24",
      "runner_name": "HORSE_NAME",
      "runner_number": "5",
      "odds": 5.5,
      "predicted_prob": 0.305,
      "implied_prob": 0.182,
      "edge": 0.123,
      "edge_pct": 12.3,
      "recommended_stake": 4.50,
      "confidence": "HIGH",
      "jockey": "J. SMITH",
      "trainer": "T. JONES",
      "form": "1-2-3",
      "ts": "85",
      "rpr": "120"
    }
  ],
  "races": [...]
}
```

---

## 🔧 Configuration

### Minimum Edge Threshold

Edit `run_daily_predictions.py`:

```python
MIN_EDGE = 0.05  # 5% minimum edge (default)
# MIN_EDGE = 0.10  # 10% for more conservative bets
# MIN_EDGE = 0.03  # 3% for more aggressive bets
```

### Stake Sizing

The pipeline uses **fractional Kelly Criterion** (25% of full Kelly) for safety.

To adjust, edit `app/pipeline/predictor.py`:

```python
# Current: 25% Kelly
recommended_stake = max(0, kelly_fraction * 0.25 * 100)

# More aggressive: 50% Kelly
recommended_stake = max(0, kelly_fraction * 0.50 * 100)

# More conservative: 10% Kelly
recommended_stake = max(0, kelly_fraction * 0.10 * 100)
```

---

## 🎯 Racing Post Paid Features

With a Racing Post paid account, you get:

- **TS (Topspeed)** - Speed ratings for each horse
- **RPR (Racing Post Rating)** - Form ratings

These ratings significantly improve prediction accuracy.

**To enable:**

1. Subscribe to Racing Post
2. Set environment variables:
   ```bash
   export RACING_POST_USERNAME="your_email"
   export RACING_POST_PASSWORD="your_password"
   ```
3. Run predictions - TS/RPR will be automatically included

---

## 📈 Next Steps

1. **Test locally** - Run `python run_daily_predictions.py`
2. **Get Racing Post account** - For TS/RPR ratings
3. **Deploy to Railway** - For 24/7 automation
4. **Set up notifications** - Email/SMS for high-value bets
5. **Build dashboard** - Web UI for viewing predictions

---

## 🐛 Troubleshooting

### "No races found"

- Check date format
- Verify Racing Post website is accessible
- Try different date: `scraper.get_todays_races('2025-11-24')`

### "Model failed to load"

- Verify model path: `models/marathon_1hour/model_cycle_961_best_roi.pkl`
- Check file exists: `ls -la models/marathon_1hour/`

### "Login failed" (Racing Post)

- Verify credentials
- Check Racing Post account is active
- Try logging in manually on website first

---

## 📞 Support

For issues or questions:
- GitHub Issues: https://github.com/elpresidentepiff/velo-oracle/issues
- Email: support@velo-oracle.com

---

**Built with ❤️ by the VELO Oracle team**
