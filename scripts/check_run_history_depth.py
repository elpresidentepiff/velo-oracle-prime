"""Check how many TS/OR runs are being captured per horse in merged JSONs."""
import json, os

best_ts = []
best_or = []

for date in ['2026-04-21', '2026-04-22', '2026-04-23']:
    for venue in ['PON', 'FFO', 'WOL', 'YAR', 'TAU', 'GOW', 'LUD', 'CAT', 'STH', 'DUN', 'BEV', 'PER', 'WAR']:
        path = f'data/racecard_merged/racecard_{venue}_{date}.json'
        if not os.path.exists(path):
            continue
        data = json.load(open(path))
        for race_time, race in data.get('races', {}).items():
            for horse in race.get('horses', []):
                ts_hist = horse.get('ts_run_history', []) or []
                or_hist = horse.get('or_run_history', []) or []
                name = horse.get('horse_name', '')
                if ts_hist:
                    best_ts.append((len(ts_hist), name, venue, date, ts_hist))
                if or_hist:
                    best_or.append((len(or_hist), name, venue, date, or_hist))

# Sort by count only
best_ts.sort(key=lambda x: x[0], reverse=True)
best_or.sort(key=lambda x: x[0], reverse=True)

print('TOP 5 HORSES BY TS RUN HISTORY LENGTH:')
for count, name, venue, date, hist in best_ts[:5]:
    print(f'  {name} ({venue} {date}): {count} runs')
    for r in hist:
        print(f'    {r}')
    print()

print()
print('TOP 5 HORSES BY OR RUN HISTORY LENGTH:')
for count, name, venue, date, hist in best_or[:5]:
    print(f'  {name} ({venue} {date}): {count} runs')
    for r in hist:
        print(f'    {r}')
    print()

ts_counts = [c for c,_,_,_,_ in best_ts]
or_counts = [c for c,_,_,_,_ in best_or]
avg_ts = sum(ts_counts)/len(ts_counts) if ts_counts else 0
avg_or = sum(or_counts)/len(or_counts) if or_counts else 0
print(f'TS run history: max={max(ts_counts) if ts_counts else 0}, avg={avg_ts:.1f}, horses_with_data={len(ts_counts)}')
print(f'OR run history: max={max(or_counts) if or_counts else 0}, avg={avg_or:.1f}, horses_with_data={len(or_counts)}')
