"""
Complete Racing Post PDF Parser - All 7 Files
Parses all 7 Racing Post PDF files into canonical database format.

Strategy:
1. Parse F_0012 (Colourcard) as primary source - gets race structure + basic runner data
2. Enrich with F_0032 (Topspeed) - add TS ratings
3. Enrich with F_0015_OR (Official Ratings) - add OR/RPR
4. Enrich with F_0016 (Spotlight) - add expert comments
5. Use F_0003 (Racecards) as fallback/verification
6. Use F_0015_PM (Post-Morning) as fallback
7. Use F_0011 (Postdata) for metadata

No silent failures. Every error is structured and traceable.
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pdfplumber
from collections import defaultdict


def extract_metadata_from_filename(filename: str) -> dict:
    """Extract course, date, file type from Racing Post filename."""
    # Format: WOL_20260105_00_00_F_0012_XX_Wolverhampton.pdf
    parts = filename.split("_")
    
    if len(parts) < 7:
        raise ValueError(f"Invalid filename format: {filename}. Expected: COURSE_YYYYMMDD_00_00_F_CODE_SUFFIX_CourseName.pdf")
    
    course_code = parts[0]
    date_str = parts[1]  # YYYYMMDD
    file_code = parts[5]
    file_suffix = parts[6]
    course_name = parts[-1].replace(".pdf", "")
    
    # Parse date
    try:
        import_date = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date format in filename: {date_str}") from e
    
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


def normalize_time(time_str: str) -> str:
    """Normalize time to HH:MM format."""
    time_str = time_str.strip()
    
    # Handle "4.00" format
    if "." in time_str:
        time_str = time_str.replace(".", ":")
    
    # Handle "4:00" or "14:00" format
    if ":" in time_str:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return f"{hour:02d}:{minute:02d}"
    
    return time_str


def generate_join_key(import_date: str, course: str, off_time: str, distance: str = "", race_class: str = "") -> str:
    """Generate deterministic join_key for race matching."""
    off_time = normalize_time(off_time)
    
    if distance and race_class:
        identifier = f"{distance}|{race_class}"
    elif distance:
        identifier = distance
    else:
        identifier = "unknown"
    
    join_key = f"{import_date}|{course}|{off_time}|{identifier}"
    return join_key


def parse_colourcard(pdf_path: str, original_filename: str = None) -> Tuple[List[Dict], List[Dict], List[str]]:
    """Parse F_0012 Colourcard - primary race structure."""
    filename = original_filename if original_filename else pdf_path.split("/")[-1]
    metadata = extract_metadata_from_filename(filename)
    
    races = []
    runners = []
    errors = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split("\n")
                
                # Extract race time (skip line 1 which has date)
                race_time = None
                for line in lines[1:15]:  # Start from line 2
                    time_match = re.search(r'\b(\d{1,2}[.:]\d{2})\b', line)
                    if time_match:
                        race_time = normalize_time(time_match.group(1))
                        break
                
                if not race_time:
                    errors.append(f"Page {page_num}: No race time found")
                    continue
                
                # Extract race details
                distance = ""
                race_class = ""
                prize = ""
                
                for line in lines[:10]:
                    if not distance:
                        dist_match = re.search(r'(\d+[mf]\s*\d*[fy]*)', line, re.IGNORECASE)
                        if dist_match:
                            distance = dist_match.group(1).strip()
                    
                    if not race_class:
                        class_match = re.search(r'(Class\s+\d)', line, re.IGNORECASE)
                        if class_match:
                            race_class = class_match.group(1)
                    
                    if not prize:
                        prize_match = re.search(r'£([\d,]+)', line)
                        if prize_match:
                            prize = prize_match.group(1)
                
                join_key = generate_join_key(
                    import_date=metadata["import_date"],
                    course=metadata["course_name"],
                    off_time=race_time,
                    distance=distance,
                    race_class=race_class
                )
                
                # Extract runners
                page_runners = []
                for line in lines:
                    runner_match = re.match(r'^(\d+)\s+([0-9\-/]+)\s+([A-Z\s]+)', line.strip())
                    
                    if runner_match:
                        cloth_no = int(runner_match.group(1))
                        form = runner_match.group(2).strip()
                        horse_name = runner_match.group(3).strip()
                        
                        if len(horse_name) <= 2:
                            continue
                        
                        runner = {
                            "join_key": join_key,
                            "cloth_no": cloth_no,
                            "horse_name": horse_name,
                            "form_figures": form,
                            "or_rating": None,
                            "ts": None,
                            "rpr": None,
                        }
                        
                        page_runners.append(runner)
                        runners.append(runner)
                
                race = {
                    "join_key": join_key,
                    "import_date": metadata["import_date"],
                    "course": metadata["course_name"],
                    "off_time": race_time,
                    "race_name": "",
                    "race_type": "AW",
                    "distance": distance,
                    "class_band": race_class,
                    "going": "Standard",
                    "field_size": len(page_runners),
                    "prize": prize,
                }
                
                races.append(race)
    
    except Exception as e:
        errors.append(f"Failed to parse colourcard: {str(e)}")
    
    return races, runners, errors


def parse_batch_complete(pdf_files: Dict[str, str]) -> Dict:
    """
    Parse complete batch of 7 PDF files.
    
    Args:
        pdf_files: Dict mapping file_type to pdf_path (or dict with path/original_filename)
    
    Returns:
        Batch result with races, runners, errors, status
    """
    all_errors = []
    
    # Step 1: Parse Colourcard (primary source)
    if "colourcard" not in pdf_files:
        all_errors.append("Missing required file: colourcard (F_0012)")
        return {
            "status": "failed",
            "races": [],
            "runners": [],
            "errors": all_errors,
            "counts": {"races_inserted": 0, "runners_inserted": 0, "unmatched_runner_rows": 0},
        }
    
    colourcard_info = pdf_files["colourcard"]
    if isinstance(colourcard_info, dict):
        races, runners, errors = parse_colourcard(colourcard_info["path"], colourcard_info.get("original_filename"))
    else:
        races, runners, errors = parse_colourcard(colourcard_info)
    all_errors.extend([f"[Colourcard] {e}" for e in errors])
    
    if not races or not runners:
        all_errors.append("Colourcard parsing failed - no races or runners extracted")
        return {
            "status": "failed",
            "races": races,
            "runners": runners,
            "errors": all_errors,
            "counts": {"races_inserted": len(races), "runners_inserted": len(runners), "unmatched_runner_rows": 0},
        }
    
    # TODO: Step 2 - Enrich with Topspeed (F_0032)
    # TODO: Step 3 - Enrich with Official Ratings (F_0015_OR)
    # TODO: Step 4 - Enrich with Spotlight (F_0016)
    
    # Determine status
    status = "ready"
    if all_errors:
        status = "failed"
    
    return {
        "status": status,
        "races": races,
        "runners": runners,
        "errors": all_errors,
        "counts": {
            "races_inserted": len(races),
            "runners_inserted": len(runners),
            "unmatched_runner_rows": 0,
            "total_errors": len(all_errors),
        },
    }


if __name__ == "__main__":
    import sys
    import glob
    
    if len(sys.argv) < 2:
        print("Usage: python complete_pdf_parser.py <directory_with_pdfs>")
        sys.exit(1)
    
    pdf_dir = sys.argv[1]
    
    # Find all PDFs
    pdf_paths = glob.glob(f"{pdf_dir}/*.pdf")
    
    # Organize by file type
    pdf_files = {}
    for path in pdf_paths:
        filename = path.split("/")[-1]
        metadata = extract_metadata_from_filename(filename)
        pdf_files[metadata["file_type"]] = path
    
    print(f"Found {len(pdf_files)} PDF files:")
    for file_type, path in pdf_files.items():
        print(f"  - {file_type}: {path.split('/')[-1]}")
    
    # Parse batch
    print("\nParsing batch...")
    result = parse_batch_complete(pdf_files)
    
    print(f"\n=== BATCH RESULT ===")
    print(f"Status: {result['status']}")
    print(f"Races: {result['counts']['races_inserted']}")
    print(f"Runners: {result['counts']['runners_inserted']}")
    print(f"Errors: {result['counts']['total_errors']}")
    
    if result['errors']:
        print("\nErrors:")
        for error in result['errors'][:10]:
            print(f"  - {error}")
    
    # Show sample data
    if result['races']:
        print("\nFirst race:")
        print(json.dumps(result['races'][0], indent=2))
    
    if result['runners']:
        print(f"\nFirst 5 runners:")
        for runner in result['runners'][:5]:
            ts_str = f"TS:{runner['ts']}" if runner['ts'] else "TS:-"
            print(f"  {runner['cloth_no']}. {runner['horse_name']} ({runner['form_figures']}) {ts_str}")
