import pdfplumber
import re
import os
from typing import Dict, List
from core.schema import RaceCard, Race, Runner
from core.deep_dive_extractor import DeepDiveExtractor

class RobustPDFParser:
    def __init__(self):
        self.race_card = None
        self.deep_dive = DeepDiveExtractor()

    def parse_package(self, file_paths: List[str]) -> RaceCard:
        # Sort files to process XX (Main Card) first
        # Heuristic: The main card is usually the largest XX file
        xx_files = [f for f in file_paths if "_XX_" in f]
        if not xx_files:
            raise ValueError("No Main Race Card (_XX) file found!")
            
        # Sort by size descending
        xx_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
        xx_file = xx_files[0]
        print(f"Selected Main Card File: {os.path.basename(xx_file)} ({os.path.getsize(xx_file)} bytes)")
            
        # Extract Deep Dive Data (Note-Book, Pace Monitor)
        notebook_data = {}
        pace_monitor = None
        try:
            notebook_data = self.deep_dive.extract_notebook_comments(xx_file)
            pace_monitor = self.deep_dive.extract_pace_monitor(xx_file)
            print(f"[Deep Dive] Extracted {len(notebook_data)} notebook entries and PM: {pace_monitor}")
        except Exception as e:
            print(f"[Deep Dive] Extraction failed: {e}")

        # Initialize RaceCard from XX file
        self.race_card = self._parse_xx_file(xx_file, pace_monitor)
        
        # Enrich with other files
        for file_path in file_paths:
            if "_OR_" in file_path:
                self._enrich_with_ratings(file_path, "official_rating")
            elif "_PM_" in file_path:
                self._enrich_with_ratings(file_path, "rpr")
            elif "_TS_" in file_path:
                self._enrich_with_ratings(file_path, "topspeed")
                
        return self.race_card

    def _parse_xx_file(self, file_path: str, pace_monitor: str = None) -> RaceCard:
        print(f"Parsing Main Card: {os.path.basename(file_path)}")
        filename = os.path.basename(file_path)
        # Extract Venue and Date from filename (WOL_20260209...)
        parts = filename.split('_')
        venue = parts[-1].replace('.pdf', '')
        date = parts[1] # 20260209
        
        card = RaceCard(venue=venue, date=date)
        
        with pdfplumber.open(file_path) as pdf:
            current_race = None
            
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                
                # Skip pages that don't look like race card pages (heuristic)
                if "No. Form Horse" not in text and "Total Race Value" not in text:
                    continue
                    
                lines = text.split('\n')
                
                for i, line in enumerate(lines):
                    # Detect Race Header (e.g., "3.55 7f 36y (Class 6)...")
                    # Regex: Time (H.MM) followed by text
                    # Also handle cases where time is at start of line
                    race_match = re.search(r'^\s*(\d{1,2}\.\d{2})\s+(.*)', line)
                    
                    # Heuristic: Race header usually has "Class" or "Total Race Value" or "Stakes"
                    is_header = race_match and (
                        "Total Race Value" in line or 
                        "Class" in line or 
                        "Stakes" in line or 
                        "Handicap" in line
                    )
                    
                    if is_header:
                        time = race_match.group(1)
                        # Normalize time to HH:MM
                        if '.' in time:
                            h, m = time.split('.')
                            time = f"{h}:{m}"
                        
                        current_race = Race(
                            race_id=f"{venue}_{date}_{time.replace(':', '')}",
                            venue=venue,
                            date=date,
                            time=time,
                            title=line,
                            pace_monitor=pace_monitor  # Inject Pace Monitor
                        )
                        card.races[time] = current_race
                        print(f"  Found Race: {time}")
                        continue
                        
                    # Detect Runner (e.g., "1 84-845 BURABACK 13 C")
                    # Regex: Start with Number, space, Form, space, Name (UPPERCASE)
                    if current_race:
                        # Look for line starting with integer followed by form string
                        runner_match = re.match(r'^(\d+)\s+([0-9\-/PUF]+)\s+([A-Z\s\(\)\']+)', line)
                        if runner_match:
                            saddle = int(runner_match.group(1))
                            form = runner_match.group(2)
                            name_raw = runner_match.group(3).strip()
                            
                            # Clean name (remove trailing numbers/codes like "13 C")
                            name = re.sub(r'\s+\d+.*$', '', name_raw).strip()
                            name = re.sub(r'\s+(C|D|CD|BF|S|BF|b|h|t|p|v|e/s)$', '', name).strip()
                            
                            if len(name) <= 2: continue

                            # Extract Jockey from Line 1
                            # Heuristic: Look for text after the weight (e.g., "9-11")
                            # Example: ... 9-11 Hollie Doyle 87 ...
                            jockey = None
                            # Find the weight pattern (d-d)
                            weight_matches = list(re.finditer(r'(\d+-\d+)', line))
                            if weight_matches:
                                # Take the last weight match (sometimes there are multiple numbers)
                                # The Jockey follows the weight immediately.
                                last_weight = weight_matches[-1]
                                end_of_weight = last_weight.end()
                                
                                # Get text after weight
                                remaining_text = line[end_of_weight:].strip()
                                
                                # The Jockey name is usually text (Title Case) followed by numbers (Ratings)
                                # Regex: Capture text until the first digit or end of line
                                jockey_match = re.match(r'([A-Za-z\.\'\-\s]+)', remaining_text)
                                if jockey_match:
                                    potential_jockey = jockey_match.group(1).strip()
                                    
                                    # Filter out if it looks like the Horse Name (UPPERCASE)
                                    # Jockey names are usually "Hollie Doyle" (Mixed Case)
                                    # But sometimes they are "P J McDonald"
                                    
                                    # If it's exactly the same as the horse name, ignore it
                                    if potential_jockey != name:
                                        jockey = potential_jockey
                                        
                                    # If it's all uppercase and long, it might be a parsing error (capturing horse name again?)
                                    # But let's trust the position (after weight) for now.
                                    
                                    # Clean up any trailing single chars
                                    if len(jockey or "") <= 2:
                                        jockey = None

                            # Extract Trainer from Line 3 (Look ahead)
                            trainer = None
                            if i + 2 < len(lines):
                                line3 = lines[i+2]
                                # Line 3 usually starts with Draw: (3) Owner... Trainer
                                # We look for the last text segment
                                # Example: (3) Hambleton Racing Ltd XVIII A Watson
                                # Heuristic: Trainer is at the end.
                                # Split by spaces, take last 2-3 words? Risky.
                                # Better: Look for the Draw pattern `\(\d+\)`
                                if re.search(r'\(\d+\)', line3):
                                    # It's likely the connections line
                                    # Trainer is usually the last name.
                                    # Let's take the string after the last "Ltd" or "Partnership" or just take the last 2 words if they look like a name
                                    # This is hard. Let's try a simple heuristic:
                                    # Split by multiple spaces to separate Owner from Trainer?
                                    parts = re.split(r'\s{2,}', line3)
                                    if len(parts) > 1:
                                        trainer = parts[-1].strip()
                                    else:
                                        # If no double spaces, try to grab the end
                                        # Assuming Trainer name is 2 words (Initial + Surname)
                                        words = line3.split()
                                        if len(words) >= 2:
                                            trainer = f"{words[-2]} {words[-1]}"

                            runner = Runner(
                                horse_name=name,
                                saddle_cloth=saddle,
                                form_string=form,
                                jockey=jockey,
                                trainer=trainer
                            )
                            current_race.runners.append(runner)
                            # print(f"    Added Runner: {name}")

        return card

    def _enrich_with_ratings(self, file_path: str, field_name: str):
        print(f"Enriching with {field_name} from {os.path.basename(file_path)}")
        with pdfplumber.open(file_path) as pdf:
            current_race_time = None
            
            for page in pdf.pages:
                text = page.extract_text()
                lines = text.split('\n')
                
                for line in lines:
                    # Detect Race Header
                    race_match = re.search(r'^(\d{1,2}\.\d{2})\s+', line)
                    if race_match:
                        time = race_match.group(1)
                        if '.' in time:
                            h, m = time.split('.')
                            time = f"{h}:{m}"
                        current_race_time = time
                        continue
                    
                    # Detect Horse and Rating
                    if current_race_time and current_race_time in self.race_card.races:
                        race = self.race_card.races[current_race_time]
                        
                        # Try to match horse names in the line (Case Insensitive)
                        for runner in race.runners:
                            # Normalize both to lowercase for comparison
                            if runner.horse_name.lower() in line.lower():
                                # Found the horse line. Now extract the rating.
                                try:
                                    # Regex to find the rating pattern
                                    # Pattern: Weight (9-9) followed by Rating (60)
                                    # OR File: 9-9 60
                                    # PM File: 9-9 60 65 (OR then RPR) - Wait, PM file has OR then RPR?
                                    # Let's look at the text extraction again:
                                    # OR File: Invincible Melody 9-9 60 68 ... (OR is 60)
                                    # PM File: Invincible Melody 9-9 60 65 ... (OR is 60, RPR is 65?)
                                    # TS File: Bomb Squad 9-6 57 64 ... (OR is 57, TS is 64?)
                                    
                                    # Strategy: Find the weight (d-d), then look at subsequent numbers.
                                    # OR is usually the 1st number after weight.
                                    # RPR/TS is usually the 2nd number (or the 1st if OR is missing/different).
                                    
                                    parts = line.split()
                                    weight_idx = -1
                                    for i, part in enumerate(parts):
                                        if re.match(r'\d+-\d+', part):
                                            weight_idx = i
                                            break
                                    
                                    if weight_idx != -1:
                                        # Get numbers after weight
                                        subsequent_parts = parts[weight_idx+1:]
                                        numbers = [p for p in subsequent_parts if p.isdigit()]
                                        
                                        if numbers:
                                            val = int(numbers[0])
                                            # If we are looking for RPR or TS, it might be the second number if the first is OR
                                            # But often the OR is repeated.
                                            # Let's trust the first number for OR.
                                            # For RPR/TS, we might need to be smarter.
                                            # In the extracted text: "Invincible Melody 9-9 60 65" (PM file)
                                            # 60 is OR, 65 is RPR.
                                            
                                            if field_name == "official_rating":
                                                setattr(runner, field_name, val)
                                            elif field_name in ["rpr", "topspeed"]:
                                                # If there are 2 numbers, take the second one (assuming first is OR)
                                                # If only 1, take it.
                                                if len(numbers) >= 2:
                                                    setattr(runner, field_name, int(numbers[1]))
                                                else:
                                                    setattr(runner, field_name, val)
                                                    
                                except Exception as e:
                                    pass
                                break
