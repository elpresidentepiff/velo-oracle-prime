import sys
import os
import json
from core.parser import RobustPDFParser

def main():
    pdf_dir = "/home/ubuntu/upload"
    # Filter for Lingfield files (LIN_20260210)
    files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if "LIN_20260210" in f and f.endswith(".pdf")]
    
    if not files:
        print("No Lingfield PDF files found!")
        return

    print(f"Found {len(files)} files to process.")
    
    parser = RobustPDFParser()
    try:
        race_card = parser.parse_package(files)
        
        # Output JSON
        output_path = "/home/ubuntu/velo-oracle-prime/data/lingfield_processed.json"
        with open(output_path, "w") as f:
            f.write(race_card.model_dump_json(indent=2))
            
        print(f"\nSUCCESS! Processed data saved to {output_path}")
        
        # Print Summary
        print("\n--- Race Card Summary ---")
        print(f"Venue: {race_card.venue}")
        print(f"Date: {race_card.date}")
        print(f"Total Races: {len(race_card.races)}")
        for time, race in race_card.races.items():
            print(f"  {time}: {len(race.runners)} runners")
            if race.runners:
                r = race.runners[0]
                print(f"    Sample: {r.horse_name} | J: {r.jockey} | T: {r.trainer} (OR: {r.official_rating}, RPR: {r.rpr}, TS: {r.topspeed})")

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
