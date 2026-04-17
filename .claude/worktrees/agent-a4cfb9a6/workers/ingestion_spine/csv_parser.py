"""
Racing Post CSV Parser
Parses racecards.csv and runners.csv into canonical database format.

No silent failures. Every error is structured and traceable.
"""

import csv
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib


def generate_join_key(import_date: str, course: str, off_time: str, race_name: str, distance: str, race_type: str) -> str:
    """
    Generate deterministic join_key for race matching.
    
    Format: {import_date}|{course}|{off_time}|{race_name_or_distance}|{race_type}
    """
    # Use race_name if available, else use distance
    identifier = race_name if race_name else f"{distance}|{race_type}"
    
    join_key = f"{import_date}|{course}|{off_time}|{identifier}"
    
    return join_key


def parse_racecards_csv(csv_path: str, import_date: str) -> Tuple[List[Dict], List[str]]:
    """
    Parse racecards.csv into canonical race records.
    
    Returns:
        (races, errors)
    """
    races = []
    errors = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    # Extract required fields
                    course = row.get('course', '').strip()
                    off_time = row.get('off_time', '').strip()
                    race_name = row.get('race_name', '').strip()
                    race_type = row.get('race_type', '').strip()
                    distance = row.get('distance', '').strip()
                    
                    # Validate required fields
                    if not course:
                        errors.append(f"Row {row_num}: Missing 'course'")
                        continue
                    
                    if not off_time:
                        errors.append(f"Row {row_num}: Missing 'off_time'")
                        continue
                    
                    # Generate join_key
                    join_key = generate_join_key(
                        import_date=import_date,
                        course=course,
                        off_time=off_time,
                        race_name=race_name,
                        distance=distance,
                        race_type=race_type
                    )
                    
                    # Build race record
                    race = {
                        "join_key": join_key,
                        "import_date": import_date,
                        "course": course,
                        "off_time": off_time,
                        "race_name": race_name,
                        "race_type": race_type,
                        "distance": distance,
                        "class_band": row.get('class_band', '').strip(),
                        "going": row.get('going', '').strip(),
                        "field_size": int(row.get('field_size', 0)) if row.get('field_size') else None,
                        "prize": row.get('prize', '').strip(),
                        "raw": row,  # Store original row for debugging
                    }
                    
                    races.append(race)
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
        
    except FileNotFoundError:
        errors.append(f"File not found: {csv_path}")
    except Exception as e:
        errors.append(f"Failed to read CSV: {str(e)}")
    
    return races, errors


def parse_runners_csv(csv_path: str, import_date: str, race_join_keys: List[str]) -> Tuple[List[Dict], List[str], int]:
    """
    Parse runners.csv into canonical runner records.
    
    Args:
        csv_path: Path to runners.csv
        import_date: Import date for join_key generation
        race_join_keys: List of valid race join_keys for matching
        
    Returns:
        (runners, errors, unmatched_count)
    """
    runners = []
    errors = []
    unmatched_count = 0
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Extract fields for join_key generation
                    course = row.get('course', '').strip()
                    off_time = row.get('off_time', '').strip()
                    race_name = row.get('race_name', '').strip()
                    distance = row.get('distance', '').strip()
                    race_type = row.get('race_type', '').strip()
                    
                    # Generate join_key to match with race
                    join_key = generate_join_key(
                        import_date=import_date,
                        course=course,
                        off_time=off_time,
                        race_name=race_name,
                        distance=distance,
                        race_type=race_type
                    )
                    
                    # Check if runner matches a race
                    if join_key not in race_join_keys:
                        unmatched_count += 1
                        errors.append(f"Row {row_num}: Runner '{row.get('horse_name')}' has no matching race (join_key: {join_key})")
                        continue
                    
                    # Extract runner data
                    runner = {
                        "join_key": join_key,  # For matching to race
                        "cloth_no": int(row.get('cloth_no', 0)) if row.get('cloth_no') else None,
                        "horse_name": row.get('horse_name', '').strip(),
                        "age": int(row.get('age', 0)) if row.get('age') else None,
                        "sex": row.get('sex', '').strip(),
                        "weight": row.get('weight', '').strip(),
                        "or_rating": int(row.get('or_rating', 0)) if row.get('or_rating') else None,
                        "rpr": int(row.get('rpr', 0)) if row.get('rpr') else None,
                        "ts": int(row.get('ts', 0)) if row.get('ts') else None,
                        "trainer": row.get('trainer', '').strip(),
                        "jockey": row.get('jockey', '').strip(),
                        "owner": row.get('owner', '').strip(),
                        "draw": int(row.get('draw', 0)) if row.get('draw') else None,
                        "headgear": row.get('headgear', '').strip(),
                        "form_figures": row.get('form_figures', '').strip(),
                        "raw": row,
                    }
                    
                    runners.append(runner)
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
        
    except FileNotFoundError:
        errors.append(f"File not found: {csv_path}")
    except Exception as e:
        errors.append(f"Failed to read CSV: {str(e)}")
    
    return runners, errors, unmatched_count


def parse_form_csv(csv_path: str) -> Tuple[List[Dict], List[str]]:
    """
    Parse form.csv into runner_form_lines records.
    
    Optional file - errors are warnings, not failures.
    """
    form_lines = []
    errors = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    form_line = {
                        "horse_name": row.get('horse_name', '').strip(),
                        "run_date": row.get('run_date', '').strip(),
                        "course": row.get('course', '').strip(),
                        "distance": row.get('distance', '').strip(),
                        "going": row.get('going', '').strip(),
                        "position": row.get('position', '').strip(),
                        "rpr": int(row.get('rpr', 0)) if row.get('rpr') else None,
                        "ts": int(row.get('ts', 0)) if row.get('ts') else None,
                        "or_rating": int(row.get('or_rating', 0)) if row.get('or_rating') else None,
                        "notes": row.get('notes', '').strip(),
                        "raw": row,
                    }
                    
                    form_lines.append(form_line)
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
        
    except FileNotFoundError:
        # Optional file - not an error
        pass
    except Exception as e:
        errors.append(f"Failed to read form CSV: {str(e)}")
    
    return form_lines, errors


def calculate_file_checksum(file_path: str) -> str:
    """Calculate SHA256 checksum of file."""
    sha256 = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    
    return sha256.hexdigest()


# Example usage
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 3:
        print("Usage: python csv_parser.py <racecards.csv> <runners.csv> [import_date]")
        sys.exit(1)
    
    racecards_path = sys.argv[1]
    runners_path = sys.argv[2]
    import_date = sys.argv[3] if len(sys.argv) > 3 else "2026-01-05"
    
    # Parse racecards
    print("Parsing racecards...")
    races, race_errors = parse_racecards_csv(racecards_path, import_date)
    print(f"  Races: {len(races)}")
    print(f"  Errors: {len(race_errors)}")
    
    if race_errors:
        print("\nRacecard Errors:")
        for error in race_errors:
            print(f"  - {error}")
    
    # Get join_keys for matching
    race_join_keys = [race['join_key'] for race in races]
    
    # Parse runners
    print("\nParsing runners...")
    runners, runner_errors, unmatched = parse_runners_csv(runners_path, import_date, race_join_keys)
    print(f"  Runners: {len(runners)}")
    print(f"  Unmatched: {unmatched}")
    print(f"  Errors: {len(runner_errors)}")
    
    if runner_errors:
        print("\nRunner Errors:")
        for error in runner_errors[:10]:  # Show first 10
            print(f"  - {error}")
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"Races: {len(races)}")
    print(f"Runners: {len(runners)}")
    print(f"Unmatched runners: {unmatched}")
    print(f"Total errors: {len(race_errors) + len(runner_errors)}")
    
    # Determine batch status
    if race_errors or runner_errors or unmatched > 0:
        print("\n❌ BATCH STATUS: FAILED")
    elif len(races) == 0 or len(runners) == 0:
        print("\n❌ BATCH STATUS: FAILED (no data)")
    else:
        print("\n✅ BATCH STATUS: READY")
