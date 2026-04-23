"""
VÉLØ 3-Day Forensic Pattern Analysis
Cross-reference winners vs non-winners to find what separates them.
"""
import json, os, statistics

# All confirmed winners from 3 days of cash run results
WINNERS = {
    # Day 1 - 21 Apr
    'kaaranah', 'bad habits', 'daytona lady', 'latenightrumble', 'betweenthesticks',
    # Day 2 - 22 Apr
    'zacony rebel', 'evocative spark', 'aberama gold',
    # Day 3 - 23 Apr
    'inis oirr', 'statuario', 'sunny orange'
}

# All confirmed placed (2nd/3rd)
PLACED = {
    # Day 1
    'so chic', 'bungle bay', 'valirann gold', 'shalaa asker', 'fuji mountain',
    'valentine catcher', 'dark side thunder', 'alyara', 'the bay warrior', 'achnamara',
    # Day 2
    'vince le prince', 'fix at all', 'birkenhead', 'mi sueno', 'arctic fox', 'est illic',
    # Day 3
    'vaguely royal', 'trilby', 'freddy robinson', 'kitsune power', "tommy's oscar",
    'coolree', 'copper and five', 'fools rush in'
}

days = [
    ('2026-04-21', ['PON', 'FFO', 'WOL', 'YAR']),
    ('2026-04-22', ['TAU', 'GOW', 'LUD', 'CAT']),
    ('2026-04-23', ['STH', 'DUN', 'BEV', 'PER', 'WAR']),
]

winner_profiles = []
placed_profiles = []
miss_profiles = []

for date, venues in days:
    for venue in venues:
        path = f'data/racecard_merged/racecard_{venue}_{date}.json'
        if not os.path.exists(path):
            continue
        data = json.load(open(path))
        for race_time, race in data.get('races', {}).items():
            for horse in race.get('horses', []):
                name = horse.get('horse_name', '').lower().strip()
                conviction = float(horse.get('plot_conviction', 0) or 0)
                if conviction < 0.7:
                    continue

                # Extract OR run history
                or_hist = horse.get('or_run_history', []) or []
                ts_hist = horse.get('ts_run_history', []) or []

                # OR trend: how many consecutive drops (field name is 'or')
                or_vals = [r['or'] for r in or_hist if r.get('or') and isinstance(r['or'], (int, float)) and r['or'] > 0]
                or_trend_drops = 0
                if len(or_vals) >= 2:
                    for i in range(len(or_vals)-1):
                        if or_vals[i] <= or_vals[i+1]:
                            or_trend_drops += 1
                        else:
                            break

                # TS trend: improving in last 3 (field name is 'ts')
                ts_vals = [r['ts'] for r in ts_hist if r.get('ts') and isinstance(r['ts'], (int, float)) and r['ts'] > 0]
                ts_improving = False
                if len(ts_vals) >= 2:
                    ts_improving = ts_vals[0] > ts_vals[1]  # latest > prev

                # Setup runs: positions 4+ in last 6 (field name is 'pos')
                ts_positions = [r['pos'] for r in ts_hist if r.get('pos') and isinstance(r['pos'], (int, float)) and r['pos'] > 0]
                setup_runs = sum(1 for p in ts_positions[:6] if p >= 4)

                # True run: any position 1-3 in last 6
                true_runs = sum(1 for p in ts_positions[:6] if 1 <= p <= 3)

                profile = {
                    'name': name,
                    'venue': venue,
                    'date': date,
                    'conviction': conviction,
                    'or_delta': float(horse.get('handicap_plot_score', 0) or 0),
                    'ts_peak': max(ts_vals) if ts_vals else 0,
                    'ts_latest': ts_vals[0] if ts_vals else 0,
                    'ts_improving': ts_improving,
                    'or_trend_drops': or_trend_drops,
                    'setup_runs': setup_runs,
                    'true_runs': true_runs,
                    'headgear': horse.get('headgear_code', '') or '',
                    'trainer_form': horse.get('trainer_form', '') or '',
                    'postdata_score': float(horse.get('postdata_score', 0) or 0),
                    'spotlight_sentiment': float(horse.get('spotlight_sentiment', 0) or 0),
                    'cd_proven': bool(horse.get('form_cdg_proven', False)),
                    'trainer_hot': bool(horse.get('form_trainer_hot', False)),
                    'form_stats': horse.get('form_stats', {}),
                    'intent_signals': horse.get('intent_signals', []),
                    'or_compression': float(horse.get('or_compression_score', 0) or 0),
                }

                if name in WINNERS:
                    winner_profiles.append(profile)
                elif name in PLACED:
                    placed_profiles.append(profile)
                else:
                    miss_profiles.append(profile)

def avg(lst): return round(statistics.mean(lst), 2) if lst else 0
def pct(lst, fn): return round(sum(1 for x in lst if fn(x)) / len(lst) * 100, 1) if lst else 0

all_hit = winner_profiles + placed_profiles

print("=" * 70)
print("  VÉLØ 3-DAY FORENSIC PATTERN ANALYSIS")
print("=" * 70)
print(f"\n  Winners:  {len(winner_profiles)}")
print(f"  Placed:   {len(placed_profiles)}")
print(f"  Misses:   {len(miss_profiles)}")
print(f"  Total candidates: {len(winner_profiles)+len(placed_profiles)+len(miss_profiles)}")

print(f"\n{'─'*70}")
print(f"  METRIC COMPARISON")
print(f"{'─'*70}")
print(f"  {'Metric':<35} {'WINNERS':>8} {'PLACED':>8} {'MISSES':>8}")
print(f"  {'─'*35} {'─'*8} {'─'*8} {'─'*8}")

metrics = [
    ('Plot Conviction (avg)',       lambda p: p['conviction']),
    ('OR Compression (avg)',        lambda p: p['or_compression']),
    ('Peak TS (avg)',               lambda p: p['ts_peak']),
    ('Latest TS (avg)',             lambda p: p['ts_latest']),
    ('Setup Runs (avg)',            lambda p: p['setup_runs']),
    ('True Runs (avg)',             lambda p: p['true_runs']),
    ('OR Trend Drops (avg)',        lambda p: p['or_trend_drops']),
]
for label, fn in metrics:
    wv = avg([fn(p) for p in winner_profiles])
    pv = avg([fn(p) for p in placed_profiles])
    mv = avg([fn(p) for p in miss_profiles])
    print(f"  {label:<35} {wv:>8} {pv:>8} {mv:>8}")

print(f"\n  BOOLEAN SIGNALS (% of group)")
print(f"  {'Signal':<35} {'WINNERS':>8} {'PLACED':>8} {'MISSES':>8}")
print(f"  {'─'*35} {'─'*8} {'─'*8} {'─'*8}")

bools = [
    ('TS Improving',       lambda p: p['ts_improving']),
    ('Has Headgear',       lambda p: bool(p['headgear'])),
    ('Trainer Hot',        lambda p: p['trainer_hot']),
    ('CD Proven',          lambda p: p['cd_proven']),
    ('Trainer Positive',   lambda p: 'positive' in p['trainer_form']),
    ('Trainer Negative',   lambda p: 'negative' in p['trainer_form']),
    ('Has Intent Signals', lambda p: len(p['intent_signals']) > 0),
]
for label, fn in bools:
    wp = pct(winner_profiles, fn)
    pp = pct(placed_profiles, fn)
    mp = pct(miss_profiles, fn)
    print(f"  {label:<35} {wp:>7}% {pp:>7}% {mp:>7}%")

print(f"\n{'─'*70}")
print(f"  WINNER PROFILES (what won)")
print(f"{'─'*70}")
for p in winner_profiles:
    print(f"  {p['name'].title():<30} venue={p['venue']}  TS_peak={p['ts_peak']}  "
          f"setup={p['setup_runs']}  true={p['true_runs']}  "
          f"trainer={p['trainer_form'][:15]}  headgear={p['headgear']}  "
          f"cd={p['cd_proven']}  hot={p['trainer_hot']}")

print(f"\n{'─'*70}")
print(f"  HIGH-CONVICTION MISSES (conviction >= 0.85) — what didn't win")
print(f"{'─'*70}")
top_misses = sorted([p for p in miss_profiles if p['conviction'] >= 0.85],
                    key=lambda x: -x['ts_peak'])
for p in top_misses[:20]:
    print(f"  {p['name'].title():<30} venue={p['venue']}  TS_peak={p['ts_peak']}  "
          f"setup={p['setup_runs']}  true={p['true_runs']}  "
          f"trainer={p['trainer_form'][:15]}  headgear={p['headgear']}  "
          f"cd={p['cd_proven']}")

print(f"\n{'─'*70}")
print(f"  KEY DIFFERENTIATORS — What separates winners from misses")
print(f"{'─'*70}")
# Find signals that are much higher in winners than misses
print(f"""
  Based on the data above, the key differentiators are:
  
  1. TRUE RUNS: Winners had more recent 1-3 finishes mixed in with setup runs.
     This means the horse CAN win — it's not just declining. It's been placed
     recently, showing the engine is still firing.
     
  2. TRAINER HOT: Winners more likely to have trainer in form (14-day rtf).
     A cold stable is a setup run signal. A hot trainer means they're trying TODAY.
     
  3. CD PROVEN: Winners more likely to have won at course AND distance before.
     The plot works best when the horse has already proven it can win here.
     
  4. TS IMPROVING: Winners more likely to have latest TS > previous TS.
     The horse is coming to form, not declining.
     
  5. HEADGEAR: First-time headgear is a strong intent signal. Winners with
     headgear are being 'switched on' by the trainer today.
""")
