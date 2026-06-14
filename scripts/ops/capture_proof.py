#!/usr/bin/env python3
"""
VÉLØ Hardened Capture Proof Sidecar
===================================
Generates verifiable evidence for browser-based data captures.
Prevents silent capture failures by writing screenshots, DOM snapshots,
and metadata on every run.

Usage:
    python scripts/ops/capture_proof.py --date YYYY-MM-DD --source rp --mode proof-only
    python scripts/ops/capture_proof.py --date YYYY-MM-DD --source rp --mode audit --manifest data/racing_post_account_raw/2026-06-11/manifest.json

Artifacts:
    data/current/capture_proof_latest.json
    data/reports/capture_proof_YYYY-MM-DD.md
    data/capture_proof/YYYY-MM-DD/
"""

import argparse
import json
import os
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

# Identify ROOT
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Failure States
CAPTURE_OK = "CAPTURE_OK"
CAPTURE_PARTIAL = "CAPTURE_PARTIAL"
CAPTURE_NO_BROWSER = "CAPTURE_NO_BROWSER"
CAPTURE_SESSION_MISSING = "CAPTURE_SESSION_MISSING"
CAPTURE_LOGIN_UNKNOWN = "CAPTURE_LOGIN_UNKNOWN"
CAPTURE_DOM_EMPTY = "CAPTURE_DOM_EMPTY"
CAPTURE_SCREENSHOT_FAILED = "CAPTURE_SCREENSHOT_FAILED"
CAPTURE_DOWNLOAD_MISSING = "CAPTURE_DOWNLOAD_MISSING"
CAPTURE_TIMEOUT = "CAPTURE_TIMEOUT"
CAPTURE_BLOCKED = "CAPTURE_BLOCKED"
CAPTURE_UNKNOWN_ERROR = "CAPTURE_UNKNOWN_ERROR"

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

class CaptureProof:
    def __init__(self, date_str: str, source: str = "rp"):
        self.date = date_str
        self.source = source
        self.started_at = _utc_now()
        self.status = "UNKNOWN"
        self.errors = []
        self.artifacts = []
        self.url_count = 0
        self.pages_reached = 0
        self.screenshots_written = 0
        self.dom_snapshots_written = 0
        self.downloads_expected = 0
        self.downloads_found = 0
        self.session_detected = None
        self.login_detected = None
        self.redaction_applied = False
        self.browser_engine = "unknown"
        
        self.proof_dir = ROOT / "data" / "capture_proof" / self.date
        self.latest_json = ROOT / "data" / "current" / "capture_proof_latest.json"
        self.report_md = ROOT / "data" / "reports" / f"capture_proof_{self.date}.md"

    def add_error(self, code: str, message: str = ""):
        self.errors.append({"code": code, "message": message})
        if self.status == "UNKNOWN" or self.status == "PASS" or self.status == "OK":
             self.status = "FAIL"

    def add_artifact(self, path: Path, label: str):
        try:
            rel_path = str(path.relative_to(ROOT))
        except ValueError:
            rel_path = str(path)
            
        self.artifacts.append({"label": label, "path": rel_path})
        if "screenshot" in label:
            self.screenshots_written += 1
        elif "dom" in label or "html" in label:
            self.dom_snapshots_written += 1

    def apply_redaction(self, text: str) -> str:
        """
        Simple redaction of common sensitive patterns.
        """
        # Redact email addresses
        redacted = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[REDACTED_EMAIL]', text)
        # Redact common token patterns (e.g. auth tokens in URLs or script tags)
        redacted = re.sub(r'bearer\s+[a-zA-Z0-9\-\._~+/]+=*', '[REDACTED_BEARER]', redacted, flags=re.I)
        
        if redacted != text:
            self.redaction_applied = True
            
        return redacted

    def save(self):
        finished_at = _utc_now()
        
        # Determine final status string
        # Default logic: 
        # 1. If errors exist and no pages reached -> FAIL
        # 2. If errors exist and some pages reached -> PARTIAL
        # 3. If no errors and all pages reached -> PASS
        # 4. If no errors and some pages reached -> PARTIAL
        
        if self.errors:
            if self.pages_reached > 0:
                final_status = "PARTIAL"
            else:
                final_status = "FAIL"
        else:
            if self.status in ["OK", "PASS"] or (self.pages_reached == self.url_count and self.url_count > 0):
                final_status = "PASS"
            elif self.pages_reached > 0:
                final_status = "PARTIAL"
            else:
                final_status = "FAIL"
            
        data = {
            "date": self.date,
            "source": self.source,
            "status": final_status,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "browser_engine": self.browser_engine,
            "url_count": self.url_count,
            "pages_reached": self.pages_reached,
            "screenshots_written": self.screenshots_written,
            "dom_snapshots_written": self.dom_snapshots_written,
            "downloads_expected": self.downloads_expected,
            "downloads_found": self.downloads_found,
            "session_detected": self.session_detected,
            "login_detected": self.login_detected,
            "redaction_applied": self.redaction_applied,
            "errors": self.errors,
            "artifacts": self.artifacts
        }
        
        # Ensure directories
        self.proof_dir.mkdir(parents=True, exist_ok=True)
        self.latest_json.parent.mkdir(parents=True, exist_ok=True)
        self.report_md.parent.mkdir(parents=True, exist_ok=True)
        
        # Write JSON
        with open(self.latest_json, "w") as f:
            json.dump(data, f, indent=2)
            
        # Write Markdown Report
        self._write_markdown_report(data)
        
        return data

    def _write_markdown_report(self, data: dict):
        lines = [
            f"# VÉLØ Capture Proof Report — {self.date}",
            f"- **Source:** {self.source}",
            f"- **Status:** {data['status']}",
            f"- **Time:** {data['started_at']} to {data['finished_at']}",
            f"- **Redaction Applied:** {data['redaction_applied']}",
            "",
            "## Summary",
            f"| Metric | Value |",
            "|---|---|",
            f"| URLs Attempted | {data['url_count']} |",
            f"| Pages Reached | {data['pages_reached']} |",
            f"| Screenshots | {data['screenshots_written']} |",
            f"| DOM Snapshots | {data['dom_snapshots_written']} |",
            f"| Session Detected | {data['session_detected']} |",
            f"| Login Detected | {data['login_detected']} |",
            "",
            "## Artifacts",
        ]
        if not data["artifacts"]:
            lines.append("- None")
        for art in data["artifacts"]:
            lines.append(f"- [{art['label']}]({art['path']})")
            
        if data["errors"]:
            lines.append("\n## Errors")
            for err in data["errors"]:
                lines.append(f"- **{err['code']}**: {err['message']}")
        
        lines.append("\n---")
        lines.append("*Generated by capture_proof.py*")
        
        self.report_md.write_text("\n".join(lines))

def audit_manifest(date_str: str, manifest_path: Path):
    """
    Audits an existing capture manifest and generates a proof report.
    """
    proof = CaptureProof(date_str)
    if not manifest_path.exists():
        proof.add_error(CAPTURE_UNKNOWN_ERROR, f"Manifest not found: {manifest_path}")
        return proof.save()
        
    try:
        manifest = json.loads(manifest_path.read_text())
        captures = manifest.get("captures", [])
        proof.url_count = manifest.get("url_count", 0)
        
        for cap in captures:
            label = cap.get("title") or cap.get("source_url")
            if cap.get("status") == "PASS":
                proof.pages_reached += 1
                
                # Check for expected files
                screenshot_file = cap.get("screenshot_path")
                html_file = cap.get("html_path")
                
                if screenshot_file:
                    sp = Path(screenshot_file)
                    if sp.exists():
                        proof.add_artifact(sp, f"capture_screenshot_{label}")
                    else:
                        proof.add_error(CAPTURE_DOWNLOAD_MISSING, f"Screenshot missing: {screenshot_file}")
                
                if html_file:
                    hp = Path(html_file)
                    if hp.exists():
                        proof.add_artifact(hp, f"capture_html_{label}")
                    else:
                        proof.add_error(CAPTURE_DOWNLOAD_MISSING, f"HTML file missing: {html_file}")
            else:
                proof.add_error(CAPTURE_PARTIAL, f"Failed URL: {cap.get('source_url')} - {cap.get('error')}")
                
        if proof.pages_reached == proof.url_count and proof.url_count > 0:
            proof.status = "OK"
        elif proof.pages_reached > 0:
            proof.status = "PARTIAL"
        else:
            proof.status = "FAIL"
            
    except Exception as e:
        proof.add_error(CAPTURE_UNKNOWN_ERROR, str(e))
        
    return proof.save()

def run_proof_only(date_str: str, source: str):
    """
    Launches browser to verify login state and take a 'proof of life' screenshot.
    """
    proof = CaptureProof(date_str, source)
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        proof.add_error(CAPTURE_NO_BROWSER, "Playwright not installed")
        return proof.save()
        
    try:
        # Import defaults from the collector
        from scripts.ops.racing_post_account_collector import DEFAULT_PROFILE_DIR, DEFAULT_LOGIN_URL
    except ImportError:
        proof.add_error(CAPTURE_UNKNOWN_ERROR, "Could not import from racing_post_account_collector")
        return proof.save()
    
    profile_dir = DEFAULT_PROFILE_DIR
    if not profile_dir.exists():
        proof.add_error(CAPTURE_SESSION_MISSING, f"Profile dir missing: {profile_dir}")
        return proof.save()
        
    try:
        with sync_playwright() as p:
            proof.browser_engine = "chromium"
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=True,
                args=["--ignore-certificate-errors", "--disable-dev-shm-usage", "--disable-gpu", "--use-gl=swiftshader"]
            )
            page = browser.new_page()
            proof.url_count = 1
            
            # Goto home page to check login
            response = page.goto(DEFAULT_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            proof.pages_reached = 1
            
            # Check for login indicators (RP specific)
            content = page.content()
            proof.session_detected = True
            
            # Simple check for login
            if any(kw in content for kw in ["Sign out", "Log out", "My Account"]):
                proof.login_detected = True
            else:
                proof.login_detected = False
                proof.add_error(CAPTURE_LOGIN_UNKNOWN, "Login indicators not found on home page")
            
            # Apply redaction to content before writing
            redacted_content = proof.apply_redaction(content)
            
            # Take proof screenshot
            screenshot_path = proof.proof_dir / f"proof_of_life_{datetime.now(timezone.utc).strftime('%H%M%S')}.png"
            page.screenshot(path=str(screenshot_path))
            proof.add_artifact(screenshot_path, "proof_of_life_screenshot")
            
            # Take DOM snapshot
            dom_path = proof.proof_dir / f"proof_of_life_{datetime.now(timezone.utc).strftime('%H%M%S')}.html"
            dom_path.write_text(redacted_content, encoding="utf-8")
            proof.add_artifact(dom_path, "proof_of_life_dom_snapshot")
            
            browser.close()
            
            if proof.login_detected:
                proof.status = "OK"
            else:
                proof.status = "PARTIAL"
                
    except Exception as e:
        proof.add_error(CAPTURE_UNKNOWN_ERROR, str(e))
        
    return proof.save()

def main():
    parser = argparse.ArgumentParser(description="VÉLØ Capture Proof")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--source", default="rp", help="rp | sl | etc")
    parser.add_argument("--mode", choices=["proof-only", "audit"], default="proof-only")
    parser.add_argument("--manifest", help="Path to manifest.json to audit")
    
    args = parser.parse_args()
    
    if args.mode == "audit" and args.manifest:
        result = audit_manifest(args.date, Path(args.manifest))
    else:
        result = run_proof_only(args.date, args.source)
        
    # Output the result as JSON to stdout
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
