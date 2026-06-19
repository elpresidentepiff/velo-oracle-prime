import json

try:
    with open('data/new_build/reports/old_vs_new_build_outcome_eval_2026_06_16.json', encoding='utf-8') as f:
        data = json.load(f)
        
    with open('data/sigma_results/sigma_results_2026_06_16.json', encoding='utf-8') as f:
        sigma = json.load(f)
    
    sp_map = {r['race_id']: r.get('winner_sp', 0) for r in sigma.get('rows', [])}
        
    old_wins = []
    nb_wins = []
    
    for r in data.get('race_evaluations', []):
        if not r.get('outcome_available'):
            continue
            
        time = r.get('off_time')
        course = r.get('course')
        rid = r.get('race_id')
        sp = sp_map.get(rid, 0.0)
        
        old_horse = r.get('old_velo_top', '')
        nb_top = r.get('nb_top', '')
        
        if r.get('old_velo_top_win'):
            old_wins.append(f"{time} {course}: {old_horse} (SP: {sp:.2f})")
        if r.get('nb_top_win'):
            nb_wins.append(f"{time} {course}: {nb_top} (SP: {sp:.2f})")

    print("🏆 OLD VELO WINS (Top Pick Only):")
    for w in old_wins: print("  • " + w)
    if not old_wins: print("  None.")
    
    print("\n🏆 NEW BUILD WINS (Top Pick Only):")
    for w in nb_wins: print("  • " + w)
    if not nb_wins: print("  None.")
except Exception as e:
    print(e)
