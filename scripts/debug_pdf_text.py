#!/usr/bin/env python3.11
"""Extract raw text from F_0011 and O_0006 PDFs to understand parsing patterns."""
import pdfplumber
from pathlib import Path

BASE = Path("/home/ubuntu/velo-oracle-prime/data/incoming_pdfs")

for name, label in [
    ("PON_20260421_00_00_F_0011_XX_Pontefract.pdf", "F_0011 POSTDATA"),
    ("PON_20260421_13_42_O_0006_XX_Pontefract.pdf", "O_0006 FORM DETAILED"),
]:
    path = BASE / name
    print(f"\n{'='*90}")
    print(f"  {label}: {name}")
    print(f"{'='*90}")
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"\n--- PAGE {i+1} ---")
            
            # Raw text
            text = page.extract_text()
            if text:
                for line in text.split("\n")[:80]:
                    print(f"  TEXT: {line}")
            
            # Tables
            tables = page.extract_tables()
            if tables:
                for j, table in enumerate(tables):
                    print(f"\n  TABLE {j+1}: {len(table)} rows x {len(table[0]) if table else 0} cols")
                    for ri, row in enumerate(table[:15]):
                        print(f"    R{ri:02d}: {row}")
                    if len(table) > 15:
                        print(f"    ... ({len(table)-15} more rows)")
