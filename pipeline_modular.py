import os
import json
from thefuzz import process
from core.parser import RobustPDFParser
from core.parsers.aux_parsers import ORParser, TSParser, PMParser

def fuzzy_match(name, choices, threshold=85):
    """Find best match for name in choices dict keys."""
    if not choices: return None
    match, score = process.extractOne(name, list(choices.keys()))
    if score >= threshold:
        return choices[match]
    return None

def main():
    pdf_dir = "/home/ubuntu/upload"
    # Filter for Lingfield files
    files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if "LIN_20260210" in f and f.endswith(".pdf")]
    
    # Identify files by suffix
    xx_file = next((f for f in files if "_XX_" in f and "0012" in f), None) # Main card
    or_file = next((f for f in files if "_OR_" in f), None)
    ts_file = next((f for f in files if "_TS_" in f), None)
    pm_file = next((f for f in files if "_PM_" in f), None)
    
    if not xx_file:
        print("FATAL: Main Card (XX) not found.")
        return

    print(f"Main Card: {os.path.basename(xx_file)}")
    
    # 1. Parse Main Card
    print("Parsing Main Card...")
    main_parser = RobustPDFParser()
    # We cheat slightly by passing just the XX file to the package parser, 
    # but we want to use the Robust logic for XX specifically.
    # Actually, RobustPDFParser.parse_package handles the whole package logic.
    # Let's use it just for the XX file to get the skeleton.
    race_card = main_parser.parse_package([xx_file]) 
    
    # 2. Parse Aux Files
    or_data = ORParser().parse(or_file) if or_file else {}
    ts_data = TSParser().parse(ts_file) if ts_file else {}
    pm_data = PMParser().parse(pm_file) if pm_file else {}
    
    print(f"Aux Data Loaded: OR({len(or_data)} races), TS({len(ts_data)} races), PM({len(pm_data)} races)")

    # 3. Merge (The Zipper)
    for time, race in race_card.races.items():
        print(f"Merging Race {time}...")
        
        # Get corresponding aux data for this time
        # Note: Aux parsers might use 12:48 vs 12.48. We normalized to colon in AuxParser.
        r_or = or_data.get(time, {})
        r_ts = ts_data.get(time, {})
        r_pm = pm_data.get(time, {})
        
        for runner in race.runners:
            # Fuzzy match runner name against aux keys
            # OR
            or_val = fuzzy_match(runner.horse_name, r_or)
            if or_val: runner.official_rating = or_val
            
            # TS
            ts_val = fuzzy_match(runner.horse_name, r_ts)
            if ts_val: runner.topspeed = ts_val
            
            # RPR (PM)
            rpr_val = fuzzy_match(runner.horse_name, r_pm)
            if rpr_val: runner.rpr = rpr_val
            
            # Debug print for verification
            # print(f"  {runner.horse_name} -> OR:{runner.official_rating} TS:{runner.topspeed} RPR:{runner.rpr}")

    # Output
    output_path = "/home/ubuntu/velo-oracle-prime/data/lingfield_modular_processed.json"
    with open(output_path, "w") as f:
        f.write(race_card.model_dump_json(indent=2))
        
    print(f"\nSUCCESS! Modular processed data saved to {output_path}")
    
    # Summary
    print("\n--- Modular Pipeline Summary ---")
    for time, race in race_card.races.items():
        if race.runners:
            r = race.runners[0]
            print(f"  {time}: {r.horse_name} | J: {r.jockey} | T: {r.trainer} | OR: {r.official_rating}")

if __name__ == "__main__":
    main()
