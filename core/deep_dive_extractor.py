import re
import pdfplumber
from typing import Dict, List, Optional

class DeepDiveExtractor:
    """
    Specialized extractor for 'Deep Dive' data found in _XX files:
    1. NOTE-BOOK comments (Expert analysis)
    2. RACE PM (Pace Monitor) figures
    3. In-Running Comments
    """

    def extract_notebook_comments(self, pdf_path: str) -> Dict[str, str]:
        """
        Extracts 'NOTE-BOOK' comments from the PDF.
        Returns a dictionary mapping Horse Name (or ID) to the comment.
        """
        notebook_comments = {}
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                # Look for the NOTE-BOOK section
                if "NOTE-BOOK" in text:
                    # Simple extraction strategy: Look for lines starting with a number (program number)
                    # followed by text, until the next section.
                    # This is a heuristic and might need refinement based on exact layout.
                    lines = text.split('\n')
                    in_notebook = False
                    current_horse_ref = None
                    current_comment = []

                    for line in lines:
                        if "NOTE-BOOK" in line:
                            in_notebook = True
                            continue
                        
                        if in_notebook:
                            # Check if we've hit the next section (e.g., "Wins Plcs")
                            if "Wins Plcs" in line or "Trainer:" in line:
                                in_notebook = False
                                if current_horse_ref and current_comment:
                                    notebook_comments[current_horse_ref] = " ".join(current_comment)
                                    current_horse_ref = None
                                    current_comment = []
                                continue

                            # Look for horse reference (e.g., "1197 " or "7 ")
                            # The PDF text often has the form number or horse number at the start
                            match = re.match(r'^(\d+)\s+(.*)', line)
                            if match:
                                if current_horse_ref and current_comment:
                                    notebook_comments[current_horse_ref] = " ".join(current_comment)
                                
                                current_horse_ref = match.group(1) # This might be form figures, need to map to horse
                                current_comment = [match.group(2)]
                            elif current_horse_ref:
                                current_comment.append(line.strip())
                    
                    # Save the last one
                    if current_horse_ref and current_comment:
                        notebook_comments[current_horse_ref] = " ".join(current_comment)

        return notebook_comments

    def extract_pace_monitor(self, pdf_path: str) -> Optional[str]:
        """
        Extracts the 'RACE PM' string (e.g., '59/56/51') from the PDF.
        """
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                
                # Look for RACE PM pattern
                match = re.search(r'RACE PM:\s*([\d/+]+)', text)
                if match:
                    return match.group(1)
        return None

    def extract_in_running_comments(self, pdf_path: str) -> Dict[str, List[str]]:
        """
        Extracts in-running comments for each horse's past runs.
        Returns a dict: Horse Name -> List of comments (e.g., "weakened final 110yds")
        """
        # This is complex because it requires associating lines with specific horses.
        # For now, we will focus on the NOTE-BOOK and PACE MONITOR as the high-value targets.
        return {}
