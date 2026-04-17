import os
import time
import json
import subprocess
import requests
from datetime import datetime

# Configuration
REPO_URL = "https://github.com/elpresidentepiff/velo-oracle-prime.git"
LOCAL_REPO_PATH = os.path.abspath(".")
COMMAND_FILE = "COMMAND.json"
STATUS_FILE = "STATUS.json"
POLL_INTERVAL = 30  # Check for commands every 30 seconds

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def git_pull():
    """Pull the latest changes from the repository."""
    try:
        subprocess.run(["git", "pull"], check=True, cwd=LOCAL_REPO_PATH, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Git pull failed: {e}")
        return False

def git_push(files):
    """Commit and push changes to the repository."""
    try:
        subprocess.run(["git", "add"] + files, check=True, cwd=LOCAL_REPO_PATH)
        subprocess.run(["git", "commit", "-m", f"Worker update: {', '.join(files)}"], check=True, cwd=LOCAL_REPO_PATH)
        subprocess.run(["git", "push"], check=True, cwd=LOCAL_REPO_PATH)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Git push failed: {e}")
        return False

def execute_command(command_data):
    """Execute the command received from the repository."""
    cmd_type = command_data.get("type")
    payload = command_data.get("payload", {})
    
    log(f"Executing command: {cmd_type}")
    
    result = {"status": "success", "message": "Command executed"}
    
    if cmd_type == "ingest_punchestown":
        # Run the ingestion script
        try:
            subprocess.run(["python", "ingest_openclaw.py"], check=True, cwd=LOCAL_REPO_PATH)
            result["message"] = "Ingestion complete."
        except subprocess.CalledProcessError as e:
            result["status"] = "error"
            result["message"] = str(e)
            
    elif cmd_type == "run_script":
        script_name = payload.get("script")
        if script_name and os.path.exists(os.path.join(LOCAL_REPO_PATH, script_name)):
            try:
                subprocess.run(["python", script_name], check=True, cwd=LOCAL_REPO_PATH)
                result["message"] = f"Script {script_name} executed."
            except subprocess.CalledProcessError as e:
                result["status"] = "error"
                result["message"] = str(e)
        else:
            result["status"] = "error"
            result["message"] = f"Script {script_name} not found."

    return result

def main():
    log("VÉLØ Worker Agent Started")
    log(f"Watching repository: {LOCAL_REPO_PATH}")
    
    last_command_id = None
    
    while True:
        if git_pull():
            if os.path.exists(COMMAND_FILE):
                try:
                    with open(COMMAND_FILE, 'r') as f:
                        command_data = json.load(f)
                    
                    cmd_id = command_data.get("id")
                    
                    if cmd_id != last_command_id:
                        log(f"New command received: {cmd_id}")
                        result = execute_command(command_data)
                        
                        # Update status
                        status_data = {
                            "last_command_id": cmd_id,
                            "result": result,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        with open(STATUS_FILE, 'w') as f:
                            json.dump(status_data, f, indent=2)
                        
                        git_push([STATUS_FILE])
                        last_command_id = cmd_id
                        
                except json.JSONDecodeError:
                    log("Error decoding COMMAND.json")
                except Exception as e:
                    log(f"Error processing command: {e}")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
