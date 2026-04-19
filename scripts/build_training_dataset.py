import os, json, urllib.request, pathlib
from dotenv import load_dotenv

env_file = pathlib.Path('.env')
load_dotenv(str(env_file))
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')

if not url or not key:
    print('Error: SUPABASE_URL or key not found')
    exit(1)

base_url = url.strip().rstrip('/')
headers = {
    'apikey': key,
    'Authorization': 'Bearer ' + key,
    'Accept': 'application/json'
}

def fetch_table(table, select='*', limit=2000):
    endpoint = f"{base_url}/rest/v1/{table}?select={select}&limit={limit}"
    req = urllib.request.Request(endpoint, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Failed to fetch {table}: {e}")
        return []

# Fetch data
print("Fetching verdicts...")
verdicts = fetch_table('velo_verdicts', 'id,race_id,generated_at,top_rank_horse_id,top_rank_score,confidence_level,decision_tier,full_analysis', 3000)

print("Fetching reviews...")
reviews = fetch_table('velo_post_race_reviews', 'verdict_id,race_id,top_pick_won,top_pick_placed,top_pick_position,actual_winner_id,actual_winner_sp,review_outcome,miss_category', 3000)

print("Fetching sigma audits...")
audits = fetch_table('sigma_audits', 'race_id,outcome,miss_reason,patch_note,top_pick_position,actual_winner_id,actual_winner_sp,decision_tier', 3000)

# Build joined dataset
dataset = []
reviews_by_race = {r['race_id']: r for r in reviews}
audits_by_race = {a['race_id']: a for a in audits}

# Group verdicts by race_id and keep the latest
verdicts_by_race = {}
for v in verdicts:
    rid = v['race_id']
    if rid not in verdicts_by_race or v['generated_at'] > verdicts_by_race[rid]['generated_at']:
        verdicts_by_race[rid] = v

for rid, v in verdicts_by_race.items():
    vid = v['id']
    audit = audits_by_race.get(rid)
    
    # We only want races that have been reconciled in sigma_audits
    if not audit:
        continue
        
    review = reviews_by_race.get(rid, {})
    outcome_data = review.get('review_outcome', {})
    
    # Extract cash_run_flag or doctrine flags if available in full_analysis
    cash_run_flag = False
    doctrine_flags = []
    top_pick = v.get('top_rank_horse_id')
    fa = v.get('full_analysis')
    if isinstance(fa, str):
        try:
            fa = json.loads(fa)
        except:
            fa = []
            
    if isinstance(fa, list):
        for runner in fa:
            if isinstance(runner, dict):
                h_id = runner.get('horse_id') or runner.get('horse', '')
                if h_id == top_pick:
                    cash_run_flag = runner.get('cash_run_flag', False)
                    doctrine_flags = runner.get('doctrines_fired', [])
                    break

    # Determine outcome from sigma_audits
    top_pick_won = (audit.get('outcome') == 'WIN')
    top_pick_placed = (audit.get('outcome') in ('WIN', 'PLACED'))
    
    # Determine miss category
    miss_category = review.get('miss_category')
    miss_reason = outcome_data.get('miss_reason') or audit.get('miss_reason')
    if not miss_category and miss_reason:
        if 'divergence' in miss_reason or 'non-runner' in miss_reason:
            miss_category = 'field_mutation'
        else:
            miss_category = miss_reason
            
    # Field sizes
    predicted_field_size = outcome_data.get('predicted_size') or (len(fa) if fa else 0)
    actual_field_size = outcome_data.get('actual_size')
    field_divergence = outcome_data.get('field_divergence', 0)
    field_mutated = outcome_data.get('field_mutated', False)
    
    # Fallback for historical mutation check if reviews are missing
    if not actual_field_size:
        # If we lack runner_results counts, we assume clean for legacy audits unless miss_reason tells us otherwise
        if miss_category == 'field_mutation':
            field_mutated = True

    record = {
        'verdict_id': vid,
        'race_id': rid,
        'generated_at': v.get('generated_at'),
        'decision_tier': v.get('decision_tier') or audit.get('decision_tier'),
        'top_pick': top_pick,
        'confidence': v.get('confidence_level'),
        'score': v.get('top_rank_score'),
        'predicted_field_size': predicted_field_size,
        'actual_field_size': actual_field_size,
        'field_divergence': field_divergence,
        'field_mutated': field_mutated,
        'outcome': audit.get('outcome'),
        'top_pick_won': top_pick_won,
        'top_pick_placed': top_pick_placed,
        'top_pick_position': audit.get('top_pick_position'),
        'winner_id': audit.get('actual_winner_id'),
        'winner_sp': audit.get('actual_winner_sp'),
        'miss_reason': miss_reason,
        'miss_category': miss_category,
        'cash_run_flag': cash_run_flag,
        'doctrine_flags': doctrine_flags,
        'top_pick_rpd_tag': outcome_data.get('top_pick_rpd_tag'),
        'winner_rpd_tag': outcome_data.get('winner_rpd_tag')
    }
    dataset.append(record)

print(f"Joined {len(dataset)} reconciled races.")

out_dir = pathlib.Path('tmp')
out_dir.mkdir(exist_ok=True, parents=True)
out_file = out_dir / 'training_sigma_audit_dataset.json'
with open(out_file, 'w') as f:
    json.dump(dataset, f, indent=2)
print(f"Dataset saved to {out_file.absolute()}")
