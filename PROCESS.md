# VELO Daily Process — CANONICAL. DO NOT CHANGE.

## Morning (9:00 UTC) — Race Card
```
python scripts/run_prime_today.py
```
Fetches racecards → scores → persists to Supabase → sends Telegram card

## Evening (21:00 UTC) — Sigma Results
```
python scripts/run_results_sigma.py --date YYYY-MM-DD
```
Fetches results → reconciles verdicts → sigma audit → sends Telegram report

## Telegram Sigma Format — LOCKED. TATTOOED. NEVER CHANGES.
```
VELO SIGMA REPORT — {DD Mon YYYY}
===================================
Races evaluated:  {n}
Hits (1st):       {w}  ({strike}%)
Frames (top 3):   {f}  ({frame}%)
Misses:           {m}

High-conf (>=0.30): {hc} picks, {hc_hits} hits ({hc_pct}%)
Avg prob (hits):    {avg_hit_prob}
Avg prob (misses):  {avg_miss_prob}

SIGMA: {verdict} — {note}
Engine: velo_prime_v1 (SQPE v17 + specialists)

VELO WINS — {DD Mon YYYY}
  WIN  {course}  {time}  {horse} (prob={p})

VELO MISS ANALYSIS — {DD Mon YYYY}
Miss classes:
  {class}: {n}
Notable fades (prob>=0.25 but missed):
  {course} {time}  {horse} (prob={p}) — won: {winner}

VELO PLACED (2nd/3rd) — {DD Mon YYYY}
  {course} {time}  {horse} placed — won: {winner}

VELO RESULTS COMPLETE — {DD Mon YYYY}
Races: {n}
Strike rate: {s}%
Frame rate:  {f}%
Ledger bets: {b}  bankroll: £{bank}
Supabase: sigma_audits={a}/{total}  learned_patterns={lp}
Status: PASS
```

## DO NOT USE
- close_sigma_loops.py — wrong format, replaced by run_results_sigma.py
- feed_sigma_loop.py — fragment, not part of daily process
- daily_pipeline.py — superseded by run_prime_today.py
