"""
VÉLØ PDF Persistence Layer
Upload incoming Racing Post PDFs to Supabase Storage (rp_imports bucket).
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.runtime_env import resolve_supabase_url, resolve_supabase_service_key, load_optional_env_file
from supabase import create_client

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="data/incoming_pdfs")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    load_optional_env_file(ROOT / ".env")
    url = resolve_supabase_url()
    key = resolve_supabase_service_key()
    if not url or not key:
        print("Error: Supabase credentials not found.")
        return
        
    sb = create_client(url, key)
    directory = Path(args.dir)
    if not directory.is_absolute():
        directory = ROOT / directory
        
    target_date_tag = args.date.replace("-", "")
    pdfs = list(directory.glob(f"*{target_date_tag}*.pdf"))
    
    if not pdfs:
        print(f"No PDFs found for date {args.date}")
        return

    print(f"Found {len(pdfs)} PDFs for {args.date}. Uploading to 'rp_imports'...")
    
    uploaded = 0
    for pdf in pdfs:
        # Key structure: pdfs/YYYY-MM-DD/filename.pdf
        storage_path = f"pdfs/{args.date}/{pdf.name}"
        
        try:
            with open(pdf, 'rb') as f:
                res = sb.storage.from_("rp_imports").upload(
                    path=storage_path,
                    file=f,
                    file_options={"upsert": "true"}
                )
            print(f"  ✓ Uploaded: {pdf.name}")
            uploaded += 1
        except Exception as e:
            print(f"  ✘ Failed: {pdf.name} - {e}")

    print(f"Summary: {uploaded} / {len(pdfs)} files persisted to Supabase.")

if __name__ == "__main__":
    main()
