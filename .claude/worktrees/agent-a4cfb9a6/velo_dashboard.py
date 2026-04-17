from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import uvicorn
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")
DB_PATH = "velo_memory.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get Recent Ingestions
    cursor.execute("SELECT * FROM ingestion_log ORDER BY timestamp DESC LIMIT 10")
    ingestions = cursor.fetchall()
    
    # Get Recent Runners (Parsed Data)
    try:
        cursor.execute("SELECT * FROM runners ORDER BY rowid DESC LIMIT 20")
        runners = cursor.fetchall()
    except sqlite3.OperationalError:
        runners = []

    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "ingestions": ingestions, "runners": runners})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
