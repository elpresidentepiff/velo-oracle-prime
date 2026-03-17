# VÉLØ Deploy Proof Rule
> Non-negotiable. Read before every deploy action.

## The Rule

**STATUS = DEPLOYED only when ALL 6 are true:**

```
1. local SHA  == origin/main SHA  == origin/feature/v10-launch SHA
2. Railway deployment trigger repo  == elpresidentepiff/velo-oracle-prime
3. Railway tracked branch           == feature/v10-launch  (or explicitly updated)
4. GET /health                      → {"status": "ok"}  HTTP 200
5. GET /openapi.json paths          → contains /api/v1/predict/race
6. POST /api/v1/predict/race        → returns velo_prime_prob in response body
```

If **any one** fails: **STATUS = NOT DEPLOYED. Stop. Do not proceed.**

---

## Pre-Deploy Checklist (run before every deploy)

```bash
# 1. Confirm correct repo on Railway trigger
# Must be: elpresidentepiff/velo-oracle-prime
# NOT:     elpresidentepiff/velo-oracle

# 2. Confirm start.sh exists and is correct
cat start.sh
# Must contain: exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"

# 3. Confirm local/remote SHAs match
git log --oneline -1
git ls-remote origin main | cut -f1
git ls-remote origin feature/v10-launch | cut -f1

# 4. Confirm Railway startCommand = bash start.sh (NOT inline uvicorn with $PORT)
# Check via Railway GraphQL or Railway dashboard
```

---

## Post-Deploy Proof (run after every deploy)

```bash
# Health
curl -s https://velo-oracle-production.up.railway.app/health

# Route present
curl -s https://velo-oracle-production.up.railway.app/openapi.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('/api/v1/predict/race' in d.get('paths',{}))"

# Endpoint responds
curl -s -X POST https://velo-oracle-production.up.railway.app/api/v1/predict/race \
  -H "Content-Type: application/json" \
  -d '{"race_id":"proof","course":"Test","runners":[{"horse":"Proofhorse","ofr":"110","rpr":"108","ts":"95","odds":[{"bookmaker":"Bet365","decimal":"5.0"}],"trainer":"T Smith","jockey":"J Doe","form":"112","draw":"3","lbs":"126","age":"4"}]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('velo_prime_prob:', d.get('top_pick',{}).get('velo_prime_prob'))"
```

---

## Known Failure Traps

| Symptom | Root Cause | Fix |
|---|---|---|
| Build SUCCESS but route 404 | Wrong source code (stale Railway snapshot) | Check webhook fired for correct repo |
| `$PORT` not a valid integer | startCommand not shell-expanded | Use `bash start.sh`, never inline `$PORT` |
| `bash: start.sh: No such file or directory` | Railway built from stale snapshot pre-start.sh | Push a new commit to trigger fresh webhook |
| "Commit not found" in Railway API | Railway webhook broken / stale commit index | Push a new commit to fire webhook |
| Routes empty in openapi | App crashed on startup | Check Railway logs immediately |
| Railway builds but serves old code | Trigger pointed at wrong repo (`velo-oracle` not `velo-oracle-prime`) | Fix trigger repo via Railway GraphQL |
| `serviceInstanceUpdate startCommand: null` does nothing | Railway API ignores null for startCommand | Must set to explicit working value |

---

## Service Truth

| Service | Use | Label |
|---|---|---|
| `velo-oracle` (0992976e) | Canonical production | **USE THIS** |
| `ingestion-spine` (b9a52e75) | Canonical ingestion | **USE THIS** |
| `enchanting-exploration` (cfd844fb) | Wrong repo, orphaned | **DO NOT USE** |
| `velo-oracle-prime` (e48d14ce) | Never had clean deploy | **DO NOT USE** |

---

## Railway Incident Rule

If Railway dashboard shows an EU West incident banner:
- Do not deploy
- Do not restart services
- Do not attribute failures to code
- Wait for incident to clear, then re-verify

---

*Committed: 2026-03-17. Do not edit without updating VELO_CANONICAL_STATE.md.*
