import pdfplumber
import json
from pathlib import Path
from datetime import datetime

PDF_DIR = Path("data/incoming_pdfs")
OUTPUT_FILE = Path(f"data/velo_races_{datetime.now().date()}.json")

all_races = []

for pdf_file in PDF_DIR.glob("*.pdf"):
    print(f"Reading {pdf_file.name}")
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    all_races.append({
        "file": pdf_file.name,
        "raw_text": text
    })

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_races, f, indent=2)

print(f"\nSaved JSON to {OUTPUT_FILE}")
