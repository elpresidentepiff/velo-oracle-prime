"""
Production Racing Post PDF Parser
Parses 7 Racing Post PDF files into canonical database format.

Files:
- F_0003_XX: Racecards (primary race data)
- F_0012_XX: Colourcard (expert analysis, SP forecast)
- F_0016_XX: Spotlight (expert narratives)
- F_0032_TS: Topspeed ratings
- F_0015_OR: Official ratings
- F_0015_PM: Post-morning (fallback)
- F_0011_XX: Postdata (metadata)

No silent failures. Every error is structured and traceable.
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pdfplumber


def extract_metadata_from_filename(filename: str) -> dict:
    """Extract course, date, file type from Racing Post filename."""
    # Format: WOL_20260105_00_00_F_0012_XX_Wolverhampton.pdf
    parts = filename.split("_")
    
    course_code = parts[0]
    date_str = parts[1]  # YYYYMMDD
    file_code = parts[5] if len(parts) > 5 else "unknown"
    file_suffix = parts[6] if len(parts) > 6 else ""
    course_name = parts[-1].replace(".pdf", "")
    
    # Parse date
    import_date = datetime.strptime(date_str, "%Y%m%d").date()
    
    # Determine file type
    file_type = "unknown"
    if file_code == "0003":
        file_type = "racecards"
    elif file_code == "0012":
        file_type = "colourcard"
    elif file_code == "0016":
        file_type = "spotlight"
    elif file_code == "0032":
        file_type = "topspeed"
    elif file_code == "0015":
        if file_suffix == "OR":
            file_type = "official_ratings"
        elif file_suffix == "PM":
            file_type = "post_morning"
    elif file_code == "0011":
        file_type = "postdata"
    
    return {
        "course_code": course_code,
        "course_name": course_name,
        "import_date": str(import_date),
        "file_type": file_type,
    }


def generate_join_key(import_date: str, course: str, off_time: str, race_name: str = "", distance: str = "", race_class: str = "") -> str:
    """
    Generate deterministic join_key for race matching.
    
    Format: {import_date}|{course}|{off_time}|{identifier}
    """
    # Normalize time format (remove leading zeros)
    off_time = off_time.strip().lstrip("0")
    
    # Use race_name if available, else use distance+class
    if race_name:
        identifier = race_name[:50]  # Truncate long names
    elif distance and race_class:
        identifier = f"{distance}|{race_class}"
    elif distance:
        identifier = distance
    else:
        identifier = "unknown"
    
    join_key = f"{import_date}|{course}|{off_time}|{identifier}"
    
    return join_key


def parse_f0012_colourcard(pdf_path: str) -> Tuple[List[Dict], List[Dict], List[str]]:
    """
    Parse F_0012 Colourcard PDF.
    
    One race per page with detailed runner information.
    
    Returns:
        (races, runners, errors)
    """
    filename = pdf_path.split("/")[-1]
    metadata = extract_metadata_from_filename(filename)
    
    races = []
    runners = []
    errors = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                
                if not text:
                    errors.append(f"Page {page_num}: No text extracted")
                    continue
                
                lines = text.split("\n")
                
                # Extract race time (format: "4.00", "4:00", "4.30", etc.)
                race_time = None
                for line in lines[:15]:  # Check first 15 lines
                    # Try format with period: "4.00"
                    time_match = re.search(r'\b(\d{1,2}\.\d{2})\b', line)
                    if time_match:
                        race_time = time_match.group(1).replace(".", ":")
                        break
                    # Try format with colon: "4:00"
                    time_match = re.search(r'\b(\d{1,2}:\d{2})\b', line)
                    if time_match:
                        race_time = time_match.group(1)
                        break
                
                if not race_time:
                    errors.append(f"Page {page_num}: Could not find race time")
                    continue
                
                # Extract race details
                race_name = ""
                distance = ""
                race_class = ""
                going = "Standard"  # Default for AW
                prize = ""
                
                for line in lines[:10]:
                    # Look for distance pattern (e.g., "7f 36y", "1m 1f")
                    dist_match = re.search(r'(\d+[mf]\s*\d*[fy]*)', line, re.IGNORECASE)
                    if dist_match and not distance:
                        distance = dist_match.group(1).strip()
                    
                    # Look for class (e.g., "Class 6", "Class 4")
                    class_match = re.search(r'(Class\s+\d)', line, re.IGNORECASE)
                    if class_match:
                        race_class = class_match.group(1)
                    
                    # Look for prize money (e.g., "£9,000", "£12,000")
                    prize_match = re.search(r'£([\d,]+)', line)
                    if prize_match and not prize:
                        prize = prize_match.group(1)
                
                # Generate join_key
                join_key = generate_join_key(
                    import_date=metadata["import_date"],
                    course=metadata["course_name"],
                    off_time=race_time,
                    race_name=race_name,
                    distance=distance,
                    race_class=race_class
                )
                
                # Extract runners
                page_runners = []
                for line in lines:
                    # Pattern: cloth_no form horse_name
                    # Example: "1 30854- ABANDO 88"
                    runner_match = re.match(r'^(\d+)\s+([0-9\-/]+)\s+([A-Z\s]+)', line.strip())
                    
                    if runner_match:
                        cloth_no = int(runner_match.group(1))
                        form = runner_match.group(2).strip()
                        horse_name = runner_match.group(3).strip()
                        
                        # Skip if horse_name is single letter (likely jockey initial)
                        if len(horse_name) <= 2:
                            continue
                        
                        # Extract ratings from same line or next lines
                        or_rating = None
                        rpr = None
                        ts = None
                        
                        # Look for ratings pattern: "OR TS RPR" or just numbers
                        ratings_match = re.search(r'(\d+)\s+(\d+)\s+(\d+)$', line)
                        if ratings_match:
                            or_rating = int(ratings_match.group(1))
                            ts = int(ratings_match.group(2))
                            rpr = int(ratings_match.group(3))
                        
                        runner = {
                            "join_key": join_key,
                            "cloth_no": cloth_no,
                            "horse_name": horse_name,
                            "form_figures": form,
                            "or_rating": or_rating,
                            "ts": ts,
                            "rpr": rpr,
                            "raw": {"source_line": line.strip()},
                        }
                        
                        page_runners.append(runner)
                        runners.append(runner)
                
                # Create race record
                race = {
                    "join_key": join_key,
                    "import_date": metadata["import_date"],
                    "course": metadata["course_name"],
                    "off_time": race_time,
                    "race_name": race_name,
                    "race_type": "AW",  # Wolverhampton is all-weather
                    "distance": distance,
                    "class_band": race_class,
                    "going": going,
                    "field_size": len(page_runners),
                    "prize": prize,
                    "raw": {"page_num": page_num, "first_lines": lines[:5]},
                }
                
                races.append(race)
    
    except Exception as e:
        errors.append(f"Failed to parse PDF: {str(e)}")
    
    return races, runners, errors


def parse_batch(pdf_files: Dict[str, str], import_date: str) -> Dict:
    """
    Parse a complete batch of 7 PDF files.
    
    Args:
        pdf_files: Dict mapping file_type to pdf_path
        import_date: Import date (YYYY-MM-DD)
    
    Returns:
        Batch result with races, runners, errors, status
    """
    all_races = []
    all_runners = []
    all_errors = []
    
    # Parse F_0012 (Colourcard) - primary source for race structure
    if "colourcard" in pdf_files:
        races, runners, errors = parse_f0012_colourcard(pdf_files["colourcard"])
        all_races.extend(races)
        all_runners.extend(runners)
        all_errors.extend([f"[Colourcard] {e}" for e in errors])
    else:
        all_errors.append("Missing required file: colourcard (F_0012)")
    
    # TODO: Parse other files to enrich data
    # - F_0003: Racecards (fallback/verification)
    # - F_0016: Spotlight (expert comments)
    # - F_0032: Topspeed (TS ratings)
    # - F_0015_OR: Official ratings (OR/RPR)
    
    # Build race_id lookup
    race_join_keys = {race["join_key"] for race in all_races}
    
    # Check for unmatched runners
    unmatched_count = 0
    for runner in all_runners:
        if runner["join_key"] not in race_join_keys:
            unmatched_count += 1
            all_errors.append(f"Unmatched runner: {runner['horse_name']} (join_key: {runner['join_key']})")
    
    # Determine batch status
    status = "ready"
    if all_errors or unmatched_count > 0:
        status = "failed"
    elif len(all_races) == 0 or len(all_runners) == 0:
        status = "failed"
        all_errors.append("No races or runners extracted")
    
    return {
        "status": status,
        "import_date": import_date,
        "races": all_races,
        "runners": all_runners,
        "errors": all_errors,
        "counts": {
            "races_inserted": len(all_races),
            "runners_inserted": len(all_runners),
            "unmatched_runner_rows": unmatched_count,
            "total_errors": len(all_errors),
        },
    }


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_parser_production.py <colourcard.pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # Parse single file
    races, runners, errors = parse_f0012_colourcard(pdf_path)
    
    print(f"\n=== PARSING RESULTS ===")
    print(f"Races: {len(races)}")
    print(f"Runners: {len(runners)}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\nErrors:")
        for error in errors[:10]:
            print(f"  - {error}")
    
    if races:
        print("\nFirst race:")
        print(json.dumps(races[0], indent=2))
    
    if runners:
        print(f"\nFirst 3 runners:")
        for runner in runners[:3]:
            print(f"  {runner['cloth_no']}. {runner['horse_name']} - {runner['form_figures']}")
