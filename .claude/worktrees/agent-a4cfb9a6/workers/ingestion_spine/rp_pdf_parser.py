"""
Racing Post PDF Parser
Extracts race and runner data from Racing Post PDF files using pdfplumber.

Supports 7 file types:
- F_0003_XX: Racecards (primary race data)
- F_0011_XX: Postdata (cross-reference)
- F_0012_XX: Colourcard (expert analysis)
- F_0015_PM: Post-Morning Ratings
- F_0015_OR: Official Ratings
- F_0016_XX: Spotlight (expert narratives)
- F_0032_TS: Topspeed Ratings
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pdfplumber


class RacingPostPDFParser:
    """Parser for Racing Post PDF files."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.file_type = self._detect_file_type()
        
    def _detect_file_type(self) -> str:
        """Detect file type from filename."""
        filename = self.pdf_path.split("/")[-1]
        
        if "_F_0003_" in filename:
            return "racecards"
        elif "_F_0011_" in filename:
            return "postdata"
        elif "_F_0012_" in filename:
            return "colourcard"
        elif "_F_0015_PM_" in filename:
            return "post_morning"
        elif "_F_0015_OR_" in filename:
            return "official_ratings"
        elif "_F_0016_" in filename:
            return "spotlight"
        elif "_F_0032_TS_" in filename:
            return "topspeed"
        else:
            return "unknown"
    
    def parse(self) -> Dict:
        """Parse PDF and return structured data."""
        if self.file_type == "racecards":
            return self._parse_racecards()
        elif self.file_type == "colourcard":
            return self._parse_colourcard()
        elif self.file_type == "spotlight":
            return self._parse_spotlight()
        elif self.file_type == "topspeed":
            return self._parse_topspeed()
        elif self.file_type == "official_ratings":
            return self._parse_official_ratings()
        elif self.file_type == "post_morning":
            return self._parse_racecards()  # Same format as racecards
        elif self.file_type == "postdata":
            return self._parse_postdata()
        else:
            raise ValueError(f"Unknown file type: {self.file_type}")
    
    def _extract_metadata_from_filename(self) -> Dict:
        """Extract course, date from filename."""
        filename = self.pdf_path.split("/")[-1]
        
        # Pattern: WOL_20260105_00_00_F_0003_XX_Wolverhampton.pdf
        parts = filename.split("_")
        
        course_code = parts[0]
        date_str = parts[1]  # YYYYMMDD
        course_name = parts[-1].replace(".pdf", "")
        
        # Parse date
        import_date = datetime.strptime(date_str, "%Y%m%d").date()
        
        return {
            "course_code": course_code,
            "course_name": course_name,
            "import_date": str(import_date),
        }
    
    def _parse_racecards(self) -> Dict:
        """Parse F_0003 (Racecards) - Primary race data."""
        metadata = self._extract_metadata_from_filename()
        races = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
        
        # Split by race times
        race_pattern = r"(\d{1,2}\.\d{2})\s+(.*?)(?=\d{1,2}\.\d{2}|$)"
        race_matches = re.finditer(race_pattern, full_text, re.DOTALL)
        
        for match in race_matches:
            race_time = match.group(1).replace(".", ":")
            race_content = match.group(2)
            
            # Extract race details
            race_data = self._extract_race_details(race_time, race_content, metadata)
            if race_data:
                races.append(race_data)
        
        return {
            "file_type": "racecards",
            "metadata": metadata,
            "races": races,
        }
    
    def _extract_race_details(self, race_time: str, content: str, metadata: Dict) -> Optional[Dict]:
        """Extract race details from text block."""
        lines = content.strip().split("\n")
        
        if len(lines) < 2:
            return None
        
        # First line usually contains distance and class
        first_line = lines[0]
        
        # Extract distance (e.g., "7f 36y", "1m 142y")
        distance_match = re.search(r"(\d+[mf]\s*\d*y?)", first_line)
        distance = distance_match.group(1) if distance_match else ""
        
        # Extract class
        class_match = re.search(r"Class\s+(\d+)", first_line, re.IGNORECASE)
        race_class = f"Class {class_match.group(1)}" if class_match else ""
        
        # Extract race type (AW = All-Weather, etc.)
        race_type = "AW" if "(AW)" in first_line else "Turf"
        
        # Extract race name (second line usually)
        race_name = lines[1].strip() if len(lines) > 1 else ""
        
        # Extract prize money
        prize_match = re.search(r"£([\d,]+)", content)
        prize_money = prize_match.group(1) if prize_match else ""
        
        # Extract runners
        runners = self._extract_runners_from_racecard(content)
        
        # Generate join key
        join_key = f"{metadata['import_date']}|{metadata['course_code']}|{race_time}|{distance}|{race_class}"
        
        return {
            "join_key": join_key,
            "course": metadata["course_name"],
            "off_time": race_time,
            "race_name": race_name,
            "race_type": race_type,
            "distance": distance,
            "race_class": race_class,
            "going": "Standard",  # Default for AW
            "prize_money": prize_money,
            "runners": runners,
        }
    
    def _extract_runners_from_racecard(self, content: str) -> List[Dict]:
        """Extract runner data from racecard content."""
        runners = []
        lines = content.split("\n")
        
        # Look for runner lines (usually have form figures + horse name)
        for i, line in enumerate(lines):
            # Pattern: form figures followed by horse name
            # Example: "4027-1 CALL GLORY"
            runner_match = re.match(r"^([0-9\-/]+)\s+([A-Z\s]+)", line)
            
            if runner_match:
                form = runner_match.group(1)
                horse_name = runner_match.group(2).strip()
                
                # Try to extract additional data from same or next line
                # Look for weight, OR, jockey, trainer
                runner_data = {
                    "horse_name": horse_name,
                    "form": form,
                    "cloth_no": None,
                    "weight": None,
                    "or_rating": None,
                    "jockey": None,
                    "trainer": None,
                }
                
                # Try to find OR (Official Rating) in nearby text
                or_match = re.search(r"OR\s*(\d+)", line)
                if or_match:
                    runner_data["or_rating"] = int(or_match.group(1))
                
                runners.append(runner_data)
        
        return runners
    
    def _parse_colourcard(self) -> Dict:
        """Parse F_0012 (Colourcard) - Expert analysis."""
        metadata = self._extract_metadata_from_filename()
        races = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            # Each page is one race
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                
                if not text or "colourcard" not in text.lower():
                    continue
                
                race_data = self._extract_colourcard_race(text, metadata, page_num)
                if race_data:
                    races.append(race_data)
        
        return {
            "file_type": "colourcard",
            "metadata": metadata,
            "races": races,
        }
    
    def _extract_colourcard_race(self, text: str, metadata: Dict, page_num: int) -> Optional[Dict]:
        """Extract race data from colourcard page."""
        lines = text.split("\n")
        
        # Extract race time from header
        time_match = re.search(r"(\d{1,2}\.\d{2})", text)
        race_time = time_match.group(1).replace(".", ":") if time_match else f"{page_num}:00"
        
        # Extract race details
        distance_match = re.search(r"(\d+[mf]\s*\d*y?)", text)
        distance = distance_match.group(1) if distance_match else ""
        
        class_match = re.search(r"Class\s+(\d+)", text, re.IGNORECASE)
        race_class = f"Class {class_match.group(1)}" if class_match else ""
        
        # Extract betting forecast
        forecast_match = re.search(r"Betting forecast:\s*(.+?)(?:\n|$)", text)
        betting_forecast = forecast_match.group(1).strip() if forecast_match else ""
        
        # Extract spotlight verdict
        verdict_match = re.search(r"\[SPOTLIGHT VERDICT\](.+?)(?:\[|$)", text, re.DOTALL)
        spotlight_verdict = verdict_match.group(1).strip() if verdict_match else ""
        
        # Extract runners
        runners = self._extract_colourcard_runners(text)
        
        join_key = f"{metadata['import_date']}|{metadata['course_code']}|{race_time}|{distance}|{race_class}"
        
        return {
            "join_key": join_key,
            "betting_forecast": betting_forecast,
            "spotlight_verdict": spotlight_verdict,
            "runners": runners,
        }
    
    def _extract_colourcard_runners(self, text: str) -> List[Dict]:
        """Extract runner data from colourcard."""
        runners = []
        
        # Pattern: No. Form Horse, breeding, owner
        # Example: "1 [Silks] 4027-1 CALL GLORY 17"
        runner_pattern = r"(\d+)\s+.*?([0-9\-/]+)\s+([A-Z\s]+)"
        
        for match in re.finditer(runner_pattern, text):
            cloth_no = int(match.group(1))
            form = match.group(2)
            horse_name = match.group(3).strip()
            
            runners.append({
                "cloth_no": cloth_no,
                "horse_name": horse_name,
                "form": form,
            })
        
        return runners
    
    def _parse_spotlight(self) -> Dict:
        """Parse F_0016 (Spotlight) - Expert narratives."""
        metadata = self._extract_metadata_from_filename()
        races = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                
                if not text or "spotlight" not in text.lower():
                    continue
                
                race_data = self._extract_spotlight_race(text, metadata, page_num)
                if race_data:
                    races.append(race_data)
        
        return {
            "file_type": "spotlight",
            "metadata": metadata,
            "races": races,
        }
    
    def _extract_spotlight_race(self, text: str, metadata: Dict, page_num: int) -> Optional[Dict]:
        """Extract race data from spotlight page."""
        # Extract race time
        time_match = re.search(r"(\d{1,2}\.\d{2})", text)
        race_time = time_match.group(1).replace(".", ":") if time_match else f"{page_num}:00"
        
        # Extract spotlight verdict
        verdict_match = re.search(r"\[SPOTLIGHT VERDICT\](.+?)(?:\[|$)", text, re.DOTALL)
        spotlight_verdict = verdict_match.group(1).strip() if verdict_match else ""
        
        # Extract runners with narratives
        runners = self._extract_spotlight_runners(text)
        
        return {
            "race_time": race_time,
            "spotlight_verdict": spotlight_verdict,
            "runners": runners,
        }
    
    def _extract_spotlight_runners(self, text: str) -> List[Dict]:
        """Extract runner narratives from spotlight."""
        runners = []
        
        # Pattern: Horse name followed by trainer, jockey, ratings, then narrative
        # This is complex - simplified extraction
        lines = text.split("\n")
        
        current_runner = None
        for line in lines:
            # Check if line is a horse name (all caps)
            if re.match(r"^[A-Z\s]+\d+\s+\d+-\d+p?$", line.strip()):
                if current_runner:
                    runners.append(current_runner)
                
                horse_name = line.strip().split()[0]
                current_runner = {
                    "horse_name": horse_name,
                    "narrative": "",
                }
            elif current_runner and line.strip():
                # Add to narrative
                current_runner["narrative"] += line.strip() + " "
        
        if current_runner:
            runners.append(current_runner)
        
        return runners
    
    def _parse_topspeed(self) -> Dict:
        """Parse F_0032 (Topspeed) - Topspeed ratings."""
        # Similar structure to racecards
        return self._parse_racecards()
    
    def _parse_official_ratings(self) -> Dict:
        """Parse F_0015_OR (Official Ratings)."""
        # Similar structure to racecards
        return self._parse_racecards()
    
    def _parse_postdata(self) -> Dict:
        """Parse F_0011 (Postdata) - Cross-reference."""
        metadata = self._extract_metadata_from_filename()
        
        with pdfplumber.open(self.pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
        
        return {
            "file_type": "postdata",
            "metadata": metadata,
            "raw_text": text,
        }


def parse_racing_post_pdf(pdf_path: str) -> Dict:
    """
    Main entry point for parsing Racing Post PDFs.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Structured data dictionary
    """
    parser = RacingPostPDFParser(pdf_path)
    return parser.parse()


# Example usage
if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python rp_pdf_parser.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    result = parse_racing_post_pdf(pdf_path)
    
    print(json.dumps(result, indent=2))
