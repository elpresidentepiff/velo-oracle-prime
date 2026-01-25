"""
RunnerParserAgent (Foundation Layer) - UPDATED REAL IMPLEMENTATION

Role: Extract horse name, number, age, weight, trainer, jockey from Colourcard (XX) PDFs.
Now correctly extracts trainer and jockey information that was in the PDFs.

Output: JSON list of runners with complete identity data.
"""

import re
import json
import pdfplumber
import sys
from pathlib import Path
from typing import List, Dict

def extract_runners(pdf_path: Path) -> List[Dict]:
    """
    UPDATED IMPLEMENTATION: Correctly extracts trainer and jockey from Colourcard PDF.
    Based on analysis of Newcastle PDF structure.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Get text from first page
            first_page = pdf.pages[0]
            text = first_page.extract_text()

            if not text:
                raise ValueError(f"Could not extract text from PDF: {pdf_path}")

            # Split by lines for line-by-line processing
            lines = [line.strip() for line in text.split('
')]

            # Find the header line
            header_idx = -1
            for i, line in enumerate(lines):
                if 'No.' in line and 'Form' in line and 'Horse' in line:
                    header_idx = i
                    break

            if header_idx == -1:
                raise ValueError(f"Could not find header in PDF: {pdf_path}")

            # Process each horse entry (4 lines per horse)
            runners = []
            i = header_idx + 1

            while i + 3 < len(lines):
                # Get the 4 lines for this horse entry
                line1 = lines[i]      # Number/Form/Name (e.g., '1 /888-0 BAVARIA IRON 20')
                line2 = lines[i + 1]  # Age/Weight/Jockey/Ratings (e.g., '7 9-9p Elle-May Croot (5) 60 - 58')
                line3 = lines[i + 2]  # Breeding (ignore)
                line4 = lines[i + 3]  # Trainer (e.g., '(8) Ivan Furtado I Furtado')

                # Parse line1: Extract horse number and name
                line1_match = re.match(r'^(\d+)\s+[^A-Z]*([A-Z][A-Z\s\-]+)\s+\d+', line1)
                if not line1_match:
                    # Not a horse entry, skip
                    i += 1
                    continue

                horse_number = int(line1_match.group(1))
                horse_name = line1_match.group(2).strip()

                # Default values
                age = 5
                weight = "UNKNOWN"
                jockey = "UNKNOWN"
                trainer = "UNKNOWN"
                official_rating = 0
                topspeed = 0
                rpr = 0

                # Parse line2: Extract age, weight, jockey, ratings
                # Two possible patterns:
                # 1. With claim allowance: '7 9-9p Elle-May Croot (5) 60 - 58'
                # 2. Without claim: '7 9-8p Billy Garritty 59 - 68'

                # Try pattern with claim allowance first
                line2_match_with_claim = re.search(r'^(\d+)\s+(\d+[-\d]+[a-z]?)\s+([A-Za-z\-\s]+)\(\d+\)\s+(\d+)\s+([\-\d]+)\s+([\-\d]+)', line2)

                if line2_match_with_claim:
                    age = int(line2_match_with_claim.group(1))
                    weight = line2_match_with_claim.group(2)
                    jockey = line2_match_with_claim.group(3).strip()
                    official_rating = int(line2_match_with_claim.group(4))
                    topspeed = line2_match_with_claim.group(5) if line2_match_with_claim.group(5) != '-' else 0
                    rpr = int(line2_match_with_claim.group(6))
                else:
                    # Try pattern without claim allowance
                    line2_match_no_claim = re.search(r'^(\d+)\s+(\d+[-\d]+[a-z]?)\s+([A-Za-z\-\s]+)\s+(\d+)\s+([\-\d]+)\s+([\-\d]+)', line2)
                    if line2_match_no_claim:
                        age = int(line2_match_no_claim.group(1))
                        weight = line2_match_no_claim.group(2)
                        jockey = line2_match_no_claim.group(3).strip()
                        official_rating = int(line2_match_no_claim.group(4))
                        topspeed = line2_match_no_claim.group(5) if line2_match_no_claim.group(5) != '-' else 0
                        rpr = int(line2_match_no_claim.group(6))

                # Parse line4: Extract trainer
                # Pattern: '(8) Ivan Furtado I Furtado' - extract 'I Furtado'
                # Look for single initial + surname pattern at the end
                trainer_match = re.search(r'([A-Z]\s+[A-Z][a-z]+)$', line4)
                if trainer_match:
                    trainer = trainer_match.group(1).strip()
                else:
                    # Alternative pattern: full name at the end
                    trainer_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)$', line4)
                    if trainer_match:
                        trainer = trainer_match.group(1).strip()

                runners.append({
                    "horse_name": horse_name,
                    "horse_number": horse_number,
                    "age": age,
                    "weight": weight,
                    "trainer": trainer,
                    "jockey": jockey,
                    "official_rating": official_rating,
                    "topspeed": topspeed,
                    "rpr": rpr
                })

                # Move to next horse entry (skip 4 lines)
                i += 4

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
