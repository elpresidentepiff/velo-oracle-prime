import pdfplumber
import sys

path = "C:/Users/puror/Downloads/Horse_Population_Report_20260531.pdf"
try:
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages[:10]):
            text = page.extract_text()
            print(f"--- PAGE {i+1} ---")
            print(text)
            print("\n")
except Exception as e:
    print(f"ERROR: {e}")
