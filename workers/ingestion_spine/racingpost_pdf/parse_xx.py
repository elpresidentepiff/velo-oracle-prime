"""
Racing Post PDF Parser - XX Racecard Parser
Parse F_0012_XX racecards (identity backbone: races + runners).
"""

import re
from datetime import datetime, time
from typing import List, Optional, Dict, Any

import pdfplumber

from .types import Race, Runner, ParseError
from .normalize import (
    parse_distance,
    normalize_horse_name,
    parse_weight,
    extract_age_from_line,
    extract_days_since_run,
)
from .extract_words import (
    extract_page_words,
    group_words_by_line,
    extract_text_from_line,
)


def parse_xx_card(pdf_path: str, course_name: str, meeting_date: str) -> tuple[List[Race], List[ParseError]]:
    """
    Parse XX racecard PDF (F_0012_XX).
    
    The XX card has the identity backbone:
    - Race times, names, distances
    - Runner numbers, names, ages
    - Form figures, days since run
    
    Args:
        pdf_path: Path to XX PDF file
        course_name: Course name (e.g., "Wolverhampton")
        meeting_date: Meeting date string
        
    Returns:
        Tuple of (races, errors)
    """
    races = []
    errors = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    page_races = _parse_xx_page(page, course_name, meeting_date, page_num + 1)
                    races.extend(page_races)
                except Exception as e:
                    errors.append(ParseError(
                        severity="error",
                        message=f"Failed to parse page {page_num + 1}: {str(e)}",
                        location=f"page_{page_num + 1}"
                    ))
    except Exception as e:
        errors.append(ParseError(
            severity="error",
            message=f"Failed to open PDF: {str(e)}",
            location="file"
        ))
    
    return races, errors


def _parse_xx_page(page: pdfplumber.page.Page, course_name: str, meeting_date: str, page_num: int) -> List[Race]:
    """
    Parse a single page of XX racecard.
    
    Strategy:
    1. Extract all text
    2. Find race headers (time + race name + distance)
    3. Parse runners for each race
    
    Args:
        page: pdfplumber page object
        course_name: Course name
        meeting_date: Meeting date
        page_num: Page number
        
    Returns:
        List of races on this page
    """
    races = []
    
    # Extract full text for pattern matching
    full_text = page.extract_text()
    
    if not full_text:
        return races
    
    # Pattern: Race header like "1.30 Handicap 6f"
    # Time format: H.MM or HH.MM
    race_pattern = r"(\d{1,2}\.\d{2})\s+([^\n]+?)\s+(\d+[mf][^\n]*)"
    
    race_matches = list(re.finditer(race_pattern, full_text, re.MULTILINE))
    
    for i, match in enumerate(race_matches):
        off_time_str = match.group(1)  # "1.30"
        race_name = match.group(2).strip()  # "Handicap"
        distance_str = match.group(3).strip()  # "6f"
        
        # Parse off time
        try:
            time_parts = off_time_str.split(".")
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            off_time = time(hour=hour, minute=minute)
        except Exception:
            continue
        
        # Parse distance
        distance_yards, distance_furlongs, distance_meters = parse_distance(distance_str)
        
        # Extract race block text (from this race to next race)
        start_pos = match.end()
        if i + 1 < len(race_matches):
            end_pos = race_matches[i + 1].start()
            race_block = full_text[start_pos:end_pos]
        else:
            race_block = full_text[start_pos:]
        
        # Parse runners from race block
        runners = _parse_runners_from_block(race_block)
        
        # Create race
        race_id = f"{meeting_date}_{course_name}_{off_time_str.replace('.', '')}"
        
        race = Race(
            race_id=race_id,
            course=course_name,
            off_time=off_time,
            race_name=race_name,
            distance_text=distance_str,
            distance_yards=distance_yards,
            distance_furlongs=distance_furlongs,
            distance_meters=distance_meters,
            runners=runners,
            runners_count=len(runners),
            raw={"page": page_num, "text": race_block[:500]}  # Store sample
        )
        
        races.append(race)
    
    return races


def _parse_runners_from_block(race_block: str) -> List[Runner]:
    """
    Parse runners from a race block.
    
    Runner format (2 lines per runner):
    Line 1: [number] [form] [name] [DAYS_SINCE_RUN] D [other]
    Line 2: [AGE] [weight] [jockey] [OR: rating] [TS: rating] [RPR: rating]
    
    Example:
        1  09353-  BRAVE EMPIRE  21 D 5
        4  9-8  William Cox  OR: 70  TS: 65  RPR: 68
    
    Args:
        race_block: Text block for this race
        
    Returns:
        List of runners
    """
    runners = []
    
    lines = race_block.split("\n")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this line starts with a runner number (1-30)
        if re.match(r"^(\d{1,2})\s+", line):
            # This is likely a runner line
            runner_num_match = re.match(r"^(\d{1,2})\s+", line)
            runner_number = int(runner_num_match.group(1))
            
            # Extract horse name (after form figures, before days)
            # Pattern: number, form (optional), name (uppercase words), days
            name_match = re.search(r"([A-Z][A-Z\s\']+?)(?:\s+\d+\s+D|\s+$)", line)
            if name_match:
                raw_name = name_match.group(1).strip()
            else:
                # Fallback: take text after form figures
                parts = line.split()
                if len(parts) >= 3:
                    # Skip number and form, take rest
                    raw_name = " ".join(parts[2:5])  # Take a few words
                else:
                    i += 1
                    continue
            
            # Normalize name
            horse_name = normalize_horse_name(raw_name)
            
            # Extract days since run
            days_since_run = extract_days_since_run(line)
            
            # Look ahead to next line for age and weight
            age = None
            weight = None
            jockey = None
            or_rating = None
            ts = None
            rpr = None
            
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Extract age (first number on line)
                age = extract_age_from_line(next_line)
                
                # Extract weight (pattern: N-N)
                weight_match = re.search(r"(\d{1,2}-\d{1,2})", next_line)
                if weight_match:
                    weight = weight_match.group(1)
                
                # Extract jockey (name after weight, before "OR:")
                jockey_match = re.search(r"\d{1,2}-\d{1,2}\s+([A-Za-z\s]+?)(?:\s+OR:|\s+TS:|\s+RPR:|\s*$)", next_line)
                if jockey_match:
                    jockey = jockey_match.group(1).strip()
                
                # Extract ratings
                or_match = re.search(r"OR:\s*(\d+)", next_line)
                if or_match:
                    or_rating = int(or_match.group(1))
                
                ts_match = re.search(r"TS:\s*(\d+)", next_line)
                if ts_match:
                    ts = int(ts_match.group(1))
                
                rpr_match = re.search(r"RPR:\s*(\d+)", next_line)
                if rpr_match:
                    rpr = int(rpr_match.group(1))
                
                i += 1  # Skip next line since we consumed it
            
            # Create runner
            runner = Runner(
                runner_number=runner_number,
                cloth_no=runner_number,
                name=horse_name,
                age=age,
                days_since_run=days_since_run,
                weight=weight,
                jockey=jockey,
                or_rating=or_rating,
                ts=ts,
                rpr=rpr,
                raw={"line": line}
            )
            
            runners.append(runner)
        
        i += 1
    
    return runners
