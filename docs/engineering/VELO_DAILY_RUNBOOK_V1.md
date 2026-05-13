# VÉLØ Daily Runbook V1

## Morning Sequence (08:00 - 10:00)
1. **Ingest:**
   ```bash
   python3 workers/velo_ops_worker.py ingest --date YYYY-MM-DD --execute --allow-network
   ```
2. **Predict:**
   ```bash
   python3 workers/velo_ops_worker.py predict --date YYYY-MM-DD --execute
   ```

## Pre-Race Sequence (T-minus 15m)
1. **Market Snapshot:**
   ```bash
   python3 workers/velo_ops_worker.py snapshot-market --date YYYY-MM-DD --execute --allow-network
   ```

## Post-Race / EOD Sequence (18:00 - 21:00)
1. **Sigma:**
   ```bash
   python3 workers/velo_ops_worker.py sigma --date YYYY-MM-DD --execute --allow-network
   ```
2. **Shadow Learning:**
   ```bash
   python3 workers/velo_ops_worker.py learn-shadow --date YYYY-MM-DD --target-state shadow_repair_v1 --execute
   ```
3. **Healthcheck:**
   ```bash
   python3 workers/velo_ops_worker.py healthcheck --date YYYY-MM-DD
   ```

## Error Handling
- If `sigma` fails with `IDENTITY_MISMATCH`, manual mapping is required.
- If `ingest` fails, check Racing API status and Standard Plan rate limits.
