import os

BASE_DIR = os.path.abspath(".")
DATA_DIR = os.path.join(BASE_DIR, "data")
INCOMING_PDFS = os.path.join(DATA_DIR, "incoming_pdfs")
PROCESSED_JSON = os.path.join(DATA_DIR, "processed_json")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")

def setup():
    print("🏗️ Building VÉLØ Data Pipeline Infrastructure...")
    
    dirs = [INCOMING_PDFS, PROCESSED_JSON, ARCHIVE_DIR]
    
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"✅ Created: {d}")
        else:
            print(f"ℹ️ Exists: {d}")
            
    print("\n📂 DROP ZONE READY:")
    print(f"   Put PDFs here -> {INCOMING_PDFS}")
    print("-" * 30)

if __name__ == "__main__":
    setup()
