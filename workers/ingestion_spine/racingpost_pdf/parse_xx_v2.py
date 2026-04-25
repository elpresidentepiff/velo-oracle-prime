"""
Racing Post PDF Parser - XX Racecard Parser V2
Parse F_0003_XX racecards (Token-based layout).
"""

import re
from datetime import time
from typing import Any

import pdfplumber

from .normalize import normalize_horse_name, parse_distance
from .types import ParseError, Race, Runner


_OFF_TIME_RE = re.compile(r"^\s*(?P<off>\d{1,2}\.\d{2})\b")

def parse_xx_v2_card(pdf_path: str, course_name: str, meeting_date: str) -> tuple[list[Race], list[ParseError]]:
    """
    Parse alternate XX racecard PDF (F_0003_XX) using word-stream tokenization.
    """
    races = []
    errors = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
            
            lines = full_text.splitlines()
            current_race = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue
                
                # 1. Detect Race Header
                off_match = _OFF_TIME_RE.match(line)
                if off_match:
                    if current_race: races.append(current_race)
                    off_time_str = off_match.group("off")
                    time_parts = off_time_str.split(".")
                    off_time = time(hour=int(time_parts[0]), minute=int(time_parts[1]))
                    race_id = f"{meeting_date}_{course_name}_{off_time_str.replace('.', '')}"
                    
                    # Distance search: look at this line and next 2 lines
                    dist_text = "unknown"
                    for j in range(i, min(i+3, len(lines))):
                        d_match = re.search(r"\b(\d+[mfy]\b.*)", lines[j])
                        if d_match:
                            dist_text = d_match.group(1).strip()
                            break

                    current_race = Race(
                        race_id=race_id, course=course_name, off_time=off_time,
                        race_name=line[len(off_time_str):].strip(),
                        distance_text=dist_text, runners=[], runners_count=0,
                        raw={"v2_layout": True}
                    )
                    dy, df, dm = parse_distance(dist_text)
                    current_race.distance_yards = dy
                    current_race.distance_furlongs = df
                    current_race.distance_meters = dm
                    continue
                    
                if not current_race: continue
                
                # 2. Stop Markers
                if any(m in line.upper() for m in ("FATE OF FAVOURITES", "TRAINERS IN THIS RACE", "SPOTLIGHT VERDICT")):
                    races.append(current_race)
                    current_race = None
                    continue
                
                # 3. Detect Runner (Token Stream)
                # Format: 1 (3) 12345 PPursuit Of Love 56 C Appleby73%
                # Or: 11(6) 12345 ...
                words = line.split()
                if not words: continue
                
                # Match runner number (first word or first part of word)
                num_match = re.match(r"^(\d+)", words[0])
                if not num_match: continue
                
                num = int(num_match.group(1))
                draw = None
                start_idx = 1
                
                # Handle Draw variants: (3) as words[1] or 1(3) as words[0]
                if "(" in words[0]:
                    d_match = re.search(r"\((\d+)\)", words[0])
                    if d_match: draw = int(d_match.group(1))
                elif len(words) > 1 and words[1].startswith("("):
                    d_match = re.search(r"\((\d+)\)", words[1])
                    if d_match:
                        draw = int(d_match.group(1))
                        start_idx = 2
                
                # The next word might be form figures
                if start_idx < len(words) and re.match(r"^[0-9\-/]+$", words[start_idx]):
                    start_idx += 1
                
                # Capture Name: everything until we hit a word that is just digits or contains %
                name_parts = []
                for k in range(start_idx, len(words)):
                    word = words[k]
                    # Boundary: first word that is purely numeric or has a %
                    if word.isdigit() or "%" in word or re.match(r"^\d+-\d+$", word):
                        break
                    name_parts.append(word)
                
                if name_parts:
                    raw_name = " ".join(name_parts)
                    # Strip leading "Running Style" flag (e.g. PPursuit -> Pursuit)
                    if len(raw_name) > 2 and raw_name[0].isupper() and raw_name[1].isupper() and raw_name[2].islower():
                        raw_name = raw_name[1:]
                    
                    runner = Runner(
                        runner_number=num, draw=draw,
                        name=normalize_horse_name(raw_name),
                        raw={"v2_line": line}
                    )
                    current_race.runners.append(runner)
                    current_race.runners_count += 1

            if current_race and current_race not in races:
                races.append(current_race)
                
    except Exception as e:
        errors.append(ParseError(severity="error", message=f"Failed XX V2 Tokenizer: {str(e)}", location="file"))

    return races, errors
