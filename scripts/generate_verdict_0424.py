"""Generate full combined verdict report for 2026-04-24 — all 7 venues."""
import json, os
from itertools import combinations

DATE = '2026-04-24'
VENUES = ['FON', 'CHP', 'KLB', 'COR', 'DON', 'PER', 'SAN']

all_picks = []

for venue in VENUES:
    path = f'data/racecard_merged/racecard_{venue}_{DATE}.json'
    if not os.path.exists(path):
        continue
    data = json.load(open(path))

    for race_time in sorted(data.get('races', {}).keys()):
        race = data['races'][race_time]
        for horse in race.get('horses', []):
            conviction = float(horse.get('plot_conviction', 0) or 0)
            if conviction < 0.70:
                continue

            name = horse.get('horse_name', '?')
            current_or = horse.get('current_or', '')
            best_win_life = horse.get('best_winning_life', '')
            or_delta = horse.get('or_delta_to_best_win')
            compression = horse.get('or_compression', 0) or 0
            trainer_form = horse.get('trainer_form', '') or ''
            ts_trend = horse.get('ts_trend_signal', 0) or 0
            or_drops = horse.get('or_trend_drops', 0) or 0
            headgear = horse.get('headgear_code', '') or ''
            spotlight_sent = horse.get('spotlight_sentiment', 0) or 0

            reasons = []
            if or_delta is not None and or_delta <= 0:
                reasons.append(f'AT winning mark (OR{current_or} vs best {best_win_life})')
            elif or_delta is not None and or_delta <= 3:
                reasons.append(f'NEAR winning mark (OR{current_or}, best {best_win_life}, +{or_delta})')
            elif or_delta is not None:
                reasons.append(f'OR{current_or} vs best {best_win_life} (+{or_delta})')
            if compression >= 10:
                reasons.append(f'dropped {compression}pts from peak')
            if ts_trend > 0.10:
                reasons.append('TS improving')
            if or_drops >= 3:
                reasons.append(f'{or_drops} OR drops')
            if 'positive' in trainer_form:
                reasons.append('trainer firing')
            elif trainer_form == 'negative':
                reasons.append('cold stable')
            if headgear:
                reasons.append(f'headgear: {headgear}')
            if spotlight_sent > 0:
                reasons.append('positive spotlight')
            reason_str = ' | '.join(reasons) if reasons else 'OR compression + TS data'

            if conviction >= 0.88:
                stars = '★★★'
            elif conviction >= 0.80:
                stars = '★★'
            else:
                stars = '★'

            all_picks.append({
                'venue': venue, 'time': race_time, 'name': name,
                'stars': stars, 'conviction': conviction, 'reason': reason_str,
            })

# ── Build report ──────────────────────────────────────────────────────────────
lines = []
lines.append(f'# VÉLØ VERDICT REPORT — {DATE}')
lines.append(f'## All 7 Venues: FON | CHP | KLB | COR | DON | PER | SAN')
lines.append('')

for venue in VENUES:
    picks = sorted([p for p in all_picks if p['venue'] == venue], key=lambda x: x['time'])
    if picks:
        lines.append(f'---')
        lines.append(f'## {venue}')
        lines.append('')
        for p in picks:
            lines.append(f"{p['stars']} **{p['time']} {p['name']}** — {p['reason']} *({p['conviction']:.3f})*")
        lines.append('')
    else:
        lines.append(f'---')
        lines.append(f'## {venue} — no picks (no horses at/near winning mark)')
        lines.append('')

# Summary
s3 = [p for p in all_picks if p['stars'] == '★★★']
s2 = [p for p in all_picks if p['stars'] == '★★']
s1 = [p for p in all_picks if p['stars'] == '★']

lines.append('---')
lines.append('## SUMMARY')
lines.append(f'- ★★★: {len(s3)} picks')
lines.append(f'- ★★: {len(s2)} picks')
lines.append(f'- ★: {len(s1)} picks')
lines.append(f'- **Total: {len(all_picks)} picks across {len([v for v in VENUES if any(p["venue"]==v for p in all_picks)])} venues**')
lines.append('')

# ── Multiples ─────────────────────────────────────────────────────────────────
# Deduplicate: one horse per race (highest conviction)
seen_races = {}
for p in sorted(all_picks, key=lambda x: -x['conviction']):
    key = (p['venue'], p['time'])
    if key not in seen_races:
        seen_races[key] = p
unique_picks = list(seen_races.values())

s3_unique = [p for p in unique_picks if p['stars'] == '★★★']
s2_unique = [p for p in unique_picks if p['stars'] == '★★']
all_unique = sorted(s3_unique + s2_unique, key=lambda x: (x['venue'], x['time']))

lines.append('---')
lines.append('## MULTIPLES')
lines.append('')

if s3_unique:
    lines.append(f'### ★★★ Picks ({len(s3_unique)} unique races)')
    for p in sorted(s3_unique, key=lambda x: (x['venue'], x['time'])):
        lines.append(f"- **{p['time']} {p['venue']}**: {p['name']}")
    lines.append('')

    if len(s3_unique) >= 4:
        lines.append(f'### {len(s3_unique)}-Fold (all ★★★)')
        for p in sorted(s3_unique, key=lambda x: (x['venue'], x['time'])):
            lines.append(f"- {p['time']} {p['venue']}: {p['name']}")
        lines.append('')

    for fold in range(min(len(s3_unique)-1, 5), 2, -1):
        if fold < len(s3_unique):
            lines.append(f'### {fold}-Folds (★★★)')
            for combo in combinations(sorted(s3_unique, key=lambda x: (x['venue'], x['time'])), fold):
                names = ' / '.join([f"{p['time']} {p['venue']} {p['name']}" for p in combo])
                lines.append(f'- {names}')
            lines.append('')

if all_unique and len(all_unique) > len(s3_unique):
    lines.append(f'### Extended ({len(all_unique)}-Fold ★★★+★★)')
    for p in all_unique:
        lines.append(f"- {p['time']} {p['venue']}: {p['name']}")
    lines.append('')
    for fold in [6, 5, 4]:
        if fold < len(all_unique):
            lines.append(f'### {fold}-Folds (★★★+★★)')
            for combo in combinations(all_unique, fold):
                names = ' / '.join([f"{p['time']} {p['venue']} {p['name']}" for p in combo])
                lines.append(f'- {names}')
            lines.append('')

report = '\n'.join(lines)
out_path = f'data/racecard_merged/VERDICTS_{DATE}.md'
open(out_path, 'w').write(report)

multiples_path = f'data/racecard_merged/MULTIPLES_{DATE}.md'
mult_lines = [l for l in lines if 'MULTIPLES' in l or 'Fold' in l or l.startswith('-') or l.startswith('#')]
open(multiples_path, 'w').write('\n'.join(mult_lines))

print(report)
print(f'\nSaved: {out_path}')
