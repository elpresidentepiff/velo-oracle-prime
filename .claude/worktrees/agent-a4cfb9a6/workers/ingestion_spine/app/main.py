"""
VÉLØ Racing Post Parser API
Minimal FastAPI worker for PDF parsing.
"""

import os
import sys
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from typing import Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from complete_pdf_parser import parse_batch_complete, extract_metadata_from_filename

app = FastAPI(title="VÉLØ RP Parser", version="1.0.0")

SECRET = os.getenv("PARSER_SHARED_SECRET", "")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True, "service": "velo-rp-parser"}


@app.post("/parse/racingpost")
async def parse_racingpost(
    file: UploadFile = File(...),
    x_velo_secret: Optional[str] = Header(default=None),
):
    """
    Parse Racing Post PDF file.
    
    Returns races and runners in canonical format.
    """
    # Auth check
    if SECRET and x_velo_secret != SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Read PDF bytes
    pdf_bytes = await file.read()
    
    # Write to temp file (control the filename, no games)
    original_filename = file.filename or "upload.pdf"
    tmp_path = f"/tmp/{original_filename}"
    
    with open(tmp_path, "wb") as f:
        f.write(pdf_bytes)
    
    try:
        # Extract metadata from original filename
        metadata = extract_metadata_from_filename(original_filename)
        
        # Parse PDF
        pdf_files = {
            metadata["file_type"]: {
                "path": tmp_path,
                "original_filename": original_filename
            }
        }
        
        result = parse_batch_complete(pdf_files)
        
        # Build response
        return {
            "day_key": metadata["import_date"],
            "source": "racing_post",
            "races": result["races"],
            "runners": result["runners"],
            "errors": result["errors"],
            "stats": result["counts"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
