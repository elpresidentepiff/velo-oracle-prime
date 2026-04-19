import json, pathlib
from collections import defaultdict

in_file = pathlib.Path('tmp/training_sigma_audit_dataset.json')
with open(in_file, 'r') as f:
    data = json.load(f)

# 1. Corpus truth
total_races = len(data)
mutated_races = [r for r in data if r.get('field_mutated') or r.get('miss_category') == 'field_mutation']
clean_races = [r for r in data if not (r.get('field_mutated') or r.get('miss_category') == 'field_mutation')]

tiers = defaultdict(int)
outcomes = defaultdict(int)
for r in data:
    tiers[r.get('decision_tier') or '?'] += 1
    outcomes[r.get('outcome') or 'UNKNOWN'] += 1

# 2. Outcome breakdown
def get_stats(subset):
    n = len(subset)
    if n == 0: return {"n":0, "win_rate":0.0, "place_rate":0.0, "avg_prob":0.0}
    wins = [r for r in subset if r.get('top_pick_won')]
    places = [r for r in subset if r.get('top_pick_placed')]
    probs = [float(r.get('score', 0) or 0) for r in subset if r.get('score') is not None]
    return {
        "n": n,
        "wins": len(wins),
        "places": len(places),
        "win_rate": round(len(wins)/n * 100, 2),
        "place_rate": round(len(places)/n * 100, 2),
        "avg_prob": round(sum(probs)/len(probs) if probs else 0, 4)
    }

overall = get_stats(data)

by_tier = {}
for t in set(r.get('decision_tier') or '?' for r in data):
    subset = [r for r in data if (r.get('decision_tier') or '?') == t]
    by_tier[t] = get_stats(subset)

by_conf = {}
for c in set(r.get('confidence', '?') for r in data):
    subset = [r for r in data if r.get('confidence', '?') == c]
    by_conf[c or '?'] = get_stats(subset)

mutation_stats = {
    "clean": get_stats(clean_races),
    "mutated": get_stats(mutated_races)
}

# 3. Miss taxonomy
miss_reasons = defaultdict(int)
misses = [r for r in data if not r.get('top_pick_won')]
for r in misses:
    reason = r.get('miss_category') or r.get('miss_reason') or 'unknown'
    if 'divergence' in str(reason) or 'non-runner' in str(reason):
        reason = 'field_mutation'
    miss_reasons[reason] += 1

# 4. Cash-run audit
cash_runs = [r for r in data if r.get('cash_run_flag')]
cash_run_stats = get_stats(cash_runs)
cash_by_tier = defaultdict(int)
for r in cash_runs:
    cash_by_tier[r.get('decision_tier', '?')] += 1

# Output JSON
scoreboard = {
    "corpus": {
        "total_races": total_races,
        "clean_races": len(clean_races),
        "mutated_races": len(mutated_races),
        "tier_distribution": dict(tiers),
        "outcomes": dict(outcomes)
    },
    "breakdown": {
        "overall": overall,
        "by_tier": by_tier,
        "by_confidence": by_conf,
        "mutation_impact": mutation_stats
    },
    "miss_taxonomy": dict(miss_reasons),
    "cash_run_audit": {
        "total": len(cash_runs),
        "stats": cash_run_stats,
        "tier_distribution": dict(cash_by_tier)
    }
}

out_json = pathlib.Path('tmp/training_sigma_audit_scoreboard.json')
with open(out_json, 'w') as f:
    json.dump(scoreboard, f, indent=2)

# Output MD
md_lines = [
    "# VÉLØ Training Sigma Audit Scoreboard",
    "",
    "## 1. Corpus Truth",
    f"- **Total Reconciled Races:** {total_races}",
    f"- **Clean Races:** {len(clean_races)}",
    f"- **Mutated Races:** {len(mutated_races)}",
    "",
    "**Outcomes:**",
    "\n".join([f"- {k}: {v}" for k, v in outcomes.items()]),
    "",
    "**Tier Distribution:**",
    "\n".join([f"- {k}: {v}" for k, v in sorted(tiers.items())]),
    "",
    "## 2. Outcome Breakdown",
    "### Overall",
    f"- Win Rate: {overall['win_rate']}%",
    f"- Place Rate: {overall['place_rate']}%",
    f"- Avg Predicted Prob: {overall['avg_prob']}",
    "",
    "### By Tier",
]
for t in sorted(by_tier.keys()):
    st = by_tier[t]
    md_lines.append(f"- **Tier {t}** (n={st['n']}): {st['win_rate']}% Win, {st['place_rate']}% Place")

md_lines.extend(["", "### By Mutation Status"])
md_lines.append(f"- **Clean** (n={mutation_stats['clean']['n']}): {mutation_stats['clean']['win_rate']}% Win, {mutation_stats['clean']['place_rate']}% Place")
md_lines.append(f"- **Mutated** (n={mutation_stats['mutated']['n']}): {mutation_stats['mutated']['win_rate']}% Win, {mutation_stats['mutated']['place_rate']}% Place")

md_lines.extend(["", "## 3. Miss Taxonomy"])
for reason, count in sorted(miss_reasons.items(), key=lambda x: -x[1]):
    md_lines.append(f"- **{reason}**: {count}")

md_lines.extend(["", "## 4. Cash Run Audit"])
md_lines.append(f"- **Total Flagged:** {len(cash_runs)}")
if len(cash_runs) > 0:
    md_lines.append(f"- **Win Rate:** {cash_run_stats['win_rate']}%")
    md_lines.append(f"- **Place Rate:** {cash_run_stats['place_rate']}%")
    md_lines.append(f"- **Tier Distribution:** {dict(cash_by_tier)}")
else:
    md_lines.append("- No cash runs identified in current corpus.")

out_md = pathlib.Path('tmp/training_sigma_audit_scoreboard.md')
with open(out_md, 'w') as f:
    f.write('\n'.join(md_lines))

print(f"Scoreboard saved to {out_json.absolute()} and {out_md.absolute()}")
