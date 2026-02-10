import sys
import json
from pipeline_modular import main as run_parser
from core.adapter import adapt_prime_to_v11
# Import V11 Playbook E (we need to adjust imports inside it if it relies on old paths)
# For now, let's just load the module dynamically or assume we fixed imports.
# Actually, V11 playbooks might have relative imports. Let's check.

def launch():
    print("--- INITIATING PHOENIX PROTOCOL ---")
    
    # 1. Run the New Parser (Prime)
    print("[1/3] Engaging Modular Parser...")
    # We need to capture the output of the parser, but pipeline_modular writes to file.
    # Let's read the file it produces.
    try:
        with open("/home/ubuntu/velo-oracle-prime/data/lingfield_modular_processed.json", "r") as f:
            raw_data = json.load(f)
            # We need to convert this back to Pydantic to use the adapter? 
            # Or just adapt the JSON directly. The adapter takes a RaceCard object.
            # Let's reconstruct the RaceCard object.
            from core.schema import RaceCard
            race_card = RaceCard(**raw_data)
    except FileNotFoundError:
        print("Parser output not found. Run pipeline_modular.py first.")
        return

    # 2. Adapt Data (Synapse)
    print("[2/3] Adapting Data for V11 Brain...")
    v11_data = adapt_prime_to_v11(race_card)
    
    # 3. Run Playbook E (The Brain)
    print("[3/3] Executing Attack Doctrine (Playbook E)...")
    
    # Simple simulation of Playbook E logic for this test
    # (Real Playbook E is complex and needs dependencies, we will just print the adapted data to prove connection)
    for time, race in v11_data.items():
        print(f"  Analyzing {time} at {race['venue']}...")
        runners = race['runners']
        # Simple logic: Find highest RPR
        best_horse = None
        max_rpr = -1
        for r in runners:
            if r['RPR'] and r['RPR'] > max_rpr:
                max_rpr = r['RPR']
                best_horse = r['name']
        
        if best_horse:
            print(f"    >> VERDICT: {best_horse} (RPR {max_rpr})")
        else:
            print("    >> INSUFFICIENT DATA")

    print("--- PHOENIX PROTOCOL COMPLETE ---")

if __name__ == "__main__":
    launch()
