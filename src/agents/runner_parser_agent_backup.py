"""
RunnerParserAgent (Foundation Layer) - IMPROVED REAL IMPLEMENTATION

Role: Extract horse name, number, age, weight, trainer, jockey from PDFs.
No opinions. No ratings. Just facts.

Output: JSON list of runners with basic identity data.
"""

import re
import json
import pdfplumber
import sys
from pathlib import Path
from typing import List, Dict

def extract_runners(pdf_path: Path) -> List[Dict]:
    """
    IMPROVED IMPLEMENTATION: Extract runner data from XX PDF.
    More robust pattern matching.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Get text from first page
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            if not text:
                raise ValueError(f"Could not extract text from PDF: {pdf_path}")
            
            # Split by lines for line-by-line processing
            lines = [line.strip() for line in text.split('\n')]
            
            # Find the header line
            header_idx = -1
            for i, line in enumerate(lines):
                if 'No.' in line and 'Form' in line and 'Horse' in line:
                    header_idx = i
                    break
            
            if header_idx == -1:
                raise ValueError(f"Could not find header in PDF: {pdf_path}")
            
            # Process each horse entry
            runners = []
            i = header_idx + 1
            
            while i < len(lines):
                line = lines[i]
                
                # Pattern for horse entry: number followed by form and uppercase name
                # Example: "1 /888-0 BAVARIA IRON 20"
                horse_match = re.match(r'^(\d+)\s+[^A-Z]*([A-Z][A-Z\s\-]+)\s+\d+', line)
                
                if horse_match:
                    horse_number = int(horse_match.group(1))
                    horse_name = horse_match.group(2).strip()
                    
                    # Default values
                    age = 5
                    weight = "UNKNOWN"
                    jockey = "UNKNOWN"
                    trainer = "UNKNOWN"
                    
                    # Look at next 3 lines for additional data
                    for offset in range(1, 4):
                        if i + offset >= len(lines):
                            break
                        
                        next_line = lines[i + offset]
                        
                        # Try to extract age and weight from patterns like "7 9-9p Elle-May Croot (5) 60 - 58"
                        if re.search(r'\d+[-\d]+[a-z]?', next_line):
                            # Extract age (first number)
                            age_match = re.search(r'^(\d+)', next_line)
                            if age_match:
                                age = int(age_match.group(1))
                            
                            # Extract weight
                            weight_match = re.search(r'(\d+[-\d]+[a-z]?)\s+([A-Z][a-z]+[\s\-][A-Z][a-z]+)', next_line)
                            if weight_match:
                                weight = weight_match.group(1)
                                jockey = weight_match.group(2)
                        
                        # Try to extract trainer
                        trainer_match = re.search(r'\(\d+\)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', next_line)
                        if trainer_match:
                            trainer = trainer_match.group(1)
                    
                    runners.append({
                        "horse_name": horse_name,
                        "horse_number": horse_number,
                        "age": age,
                        "weight": weight,
                        "trainer": trainer,
                        "jockey": jockey
                    })
                    
                    # Skip ahead past this horse entry
                    i += 3
                else:
                    i += 1
            
            if not runners:
                raise ValueError(f"No runners found in PDF: {pdf_path}")
            
            return runners
            
    except Exception as e:
        raise ValueError(f"Failed to parse runners from PDF {pdf_path}: {str(e)}")

def main(pdf_path_str: str):
    """Entry point."""
    pdf_path = Path(pdf_path_str)
    try:
        runners = extract_runners(pdf_path)
        print(json.dumps(runners, indent=2))
    except Exception as e:
        print(f"ERROR in RunnerParserAgent: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python runner_parser_agent.py <pdf_path>")
        sys.exit(1)
    main(sys.argv[1])
