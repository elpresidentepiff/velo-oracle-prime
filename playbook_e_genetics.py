import json

def execute_attack_doctrine(v11_data):
    """
    V11 Brain - Playbook E (Genetics Upgrade)
    
    Logic:
    1. Ability Score (40%): RPR vs Field Average
    2. Suitability Score (30%): Course/Distance/Going
    3. Form Score (20%): Recent form + Profile Flags (Handicap Debut)
    4. Genetics Score (10%): Sire/Dam potential (NEW)
    """
    
    print("\n--- V11 BRAIN: ENGAGING GENETICS LAYER ---")
    
    # Mock Genetics Database (In production, this would be a real DB lookup)
    # We look for "Synthetic Sires" since Kempton is Polytrack
    SYNTHETIC_SIRES = ["Kodiac", "Dubawi", "Shamardal", "Lope De Vega", "Sea The Stars", "Kingman", "Frankel"]
    
    results = {}
    
    for time, race in v11_data.items():
        print(f"\nAnalyzing {time} at {race['venue']} ({race['meta']['distance']})")
        runners = race['runners']
        
        # Calculate Field Average RPR (ignoring 0/None)
        rprs = [r['RPR'] for r in runners if r['RPR']]
        avg_rpr = sum(rprs) / len(rprs) if rprs else 0
        
        scored_runners = []
        
        for r in runners:
            score = 0
            reasons = []
            
            # 1. Ability (RPR)
            if r['RPR']:
                diff = r['RPR'] - avg_rpr
                if diff > 5:
                    score += 40
                    reasons.append(f"Dominant RPR (+{diff:.1f})")
                elif diff > 0:
                    score += 20
                    reasons.append("Above Avg RPR")
            
            # 2. Suitability (Mocked for now, relying on Deep Dive in future)
            # If we had Course Winner data, we'd add it here.
            
            # 3. Form / Profile
            if r['form'] and r['form'].endswith('1'):
                score += 15
                reasons.append("Last Start Winner")
            
            # 4. Genetics (The New Layer)
            sire = r.get('sire')
            if sire:
                # Check against Synthetic Sires list
                # Fuzzy match or direct match
                is_synthetic_sire = any(s in sire for s in SYNTHETIC_SIRES)
                if is_synthetic_sire:
                    score += 15 # Big bonus for breeding
                    reasons.append(f"Elite Synthetic Sire ({sire})")
                else:
                    # Small bonus just for having data
                    score += 2
            
            # Final Tally
            scored_runners.append({
                "name": r['name'],
                "score": score,
                "reasons": reasons,
                "sire": sire,
                "odds": r['odds']
            })
            
        # Sort by Score
        scored_runners.sort(key=lambda x: x['score'], reverse=True)
        
        # Verdict
        top_pick = scored_runners[0]
        print(f"  >> VERDICT: {top_pick['name']} (Score: {top_pick['score']})")
        print(f"     Logic: {', '.join(top_pick['reasons'])}")
        if top_pick['sire']:
            print(f"     Bloodline: {top_pick['sire']}")
            
        results[time] = top_pick
        
    return results
