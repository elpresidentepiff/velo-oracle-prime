# VELO v12 Quick Start Guide

**For daily operations and quick reference**

---

## 🚀 Run Analysis (Most Common Commands)

### Analyze Today's Races

```bash
cd /home/ubuntu/velo-oracle-prime
python3.11 scripts/run_live_analysis.py
```

### Test Mode (First Race Only)

```bash
python3.11 scripts/run_live_analysis.py --test
```

### Analyze Specific Number of Races

```bash
python3.11 scripts/run_live_analysis.py --limit 5
```

---

## 📊 Check System Status

### View Recent Logs

```bash
tail -50 logs/live_analysis.log
```

### Check API Connection

```bash
curl -u "VkP2i6RRIDp2GGrxR6XAaViB:fqvqgIMujliFV94D38uPvwUA" \
  "https://api.theracingapi.com/v1/courses/regions"
```

### Test Pipeline

```bash
python3.11 scripts/run_live_analysis.py --test
```

---

## 🔍 Query Results (Supabase)

### Check Recent Engine Runs

```sql
SELECT * FROM engine_runs 
ORDER BY created_at DESC 
LIMIT 10;
```

### View Today's Verdicts

```sql
SELECT * FROM verdicts 
WHERE created_at::date = CURRENT_DATE 
ORDER BY created_at DESC;
```

### Learning Gate Summary

```sql
SELECT learning_status, COUNT(*) as count
FROM learning_events 
WHERE created_at::date = CURRENT_DATE
GROUP BY learning_status;
```

---

## 🛠️ Common Tasks

### Update Repository

```bash
cd /home/ubuntu/velo-oracle-prime
git pull origin feature/v10-launch
```

### View Available Races

```bash
python3.11 -c "
from app.data.racing_api_client import TheRacingAPIClient
client = TheRacingAPIClient()
data = client.get_todays_racecards()
for race in data['racecards'][:10]:
    print(f\"{race['course']} {race['off_time']}: {race['race_name']}\")
"
```

### Check Logs for Errors

```bash
grep ERROR logs/live_analysis.log | tail -20
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `scripts/run_live_analysis.py` | Main production script |
| `app/data/racing_api_client.py` | TheRacingAPI integration |
| `app/pipeline/orchestrator.py` | V12 pipeline orchestration |
| `.env` | Credentials (never commit!) |
| `logs/live_analysis.log` | Execution logs |

---

## 🆘 Quick Troubleshooting

### Problem: "No races found"
**Solution**: Racing might not be scheduled today. Check tomorrow's races:
```bash
python3.11 -c "
from app.data.racing_api_client import TheRacingAPIClient
client = TheRacingAPIClient()
data = client.get_tomorrows_racecards()
print(f'Tomorrow: {len(data[\"racecards\"])} races')
"
```

### Problem: "API 401 Unauthorized"
**Solution**: Check credentials are loaded:
```bash
python3.11 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Username:', os.getenv('RACING_API_USERNAME')[:10] + '...')
"
```

### Problem: Pipeline fails
**Solution**: Run in test mode to see detailed error:
```bash
python3.11 scripts/run_live_analysis.py --test 2>&1 | grep -A 5 ERROR
```

---

## 📞 Support

- **Documentation**: `/docs/PRODUCTION_DEPLOYMENT.md`
- **Repository**: https://github.com/elpresidentepiff/velo-oracle-prime
- **Branch**: `feature/v10-launch`

---

**Quick Tip**: Bookmark this file for daily reference!
