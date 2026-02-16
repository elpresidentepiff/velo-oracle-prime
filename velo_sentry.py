import time
import os
import shutil
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pdfplumber

# Configuration
BASE_DIR = os.path.abspath(".")
INCOMING_DIR = os.path.join(BASE_DIR, "data", "incoming_pdfs")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed_json")
ARCHIVE_DIR = os.path.join(BASE_DIR, "data", "archive")
DB_PATH = "velo_memory.db"

class RaceCardHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".pdf"):
            print(f"👀 SENTRY: New Race Card Detected: {event.src_path}")
            # Wait a moment for file copy to finish
            time.sleep(2)
            self.process_pdf(event.src_path)

    def process_pdf(self, pdf_path):
        print(f"⚙️ SENTRY: Processing {os.path.basename(pdf_path)}...")
        
        try:
            # 1. Extract Text (Simple Extraction for now)
            text_content = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text_content += page.extract_text() + "\n"
            
            print(f"   - Extracted {len(text_content)} characters.")
            
            # 2. Log to Database (The "Memory")
            # For now, we just log that we saw the file. 
            # In the future, we parse the runners here.
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            filename = os.path.basename(pdf_path)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Create an ingestion log table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingestion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                timestamp TEXT,
                status TEXT
            )
            ''')
            
            cursor.execute("INSERT INTO ingestion_log (filename, timestamp, status) VALUES (?, ?, ?)",
                           (filename, timestamp, "RECEIVED"))
            
            conn.commit()
            conn.close()
            print("   - Logged to Memory Vault.")
            
            # 3. Archive the File
            shutil.move(pdf_path, os.path.join(ARCHIVE_DIR, filename))
            print(f"✅ SENTRY: File archived. Ready for next race.")
            
        except Exception as e:
            print(f"❌ SENTRY ERROR: {str(e)}")

def start_sentry():
    # Ensure directories exist
    for d in [INCOMING_DIR, PROCESSED_DIR, ARCHIVE_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

    event_handler = RaceCardHandler()
    observer = Observer()
    observer.schedule(event_handler, INCOMING_DIR, recursive=False)
    observer.start()
    
    print(f"🛡️ VÉLØ SENTRY ACTIVE")
    print(f"   Watching: {INCOMING_DIR}")
    print("   Drop a PDF to test me.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_sentry()
