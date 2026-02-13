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
        # Updated to read Chelmsford data
        with open("/home/ubuntu/velo-oracle-prime/data/chelmsford_modular_processed.json", "r") as f:
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
    
    # 3. Run Playbook E (The Brain - Genetics Upgrade)
    print("[3/3] Executing Attack Doctrine (Playbook E - Genetics Upgrade)...")
    
    from playbook_e_genetics import execute_attack_doctrine
    execute_attack_doctrine(v11_data)

    print("--- PHOENIX PROTOCOL COMPLETE ---")

if __name__ == "__main__":
    launch()
