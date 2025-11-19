#!/usr/bin/env python3
"""
VÉLØ Oracle - Production Checks
================================

Automated production health and functionality checks.

Usage:
    python scripts/production_checks.py
"""

import sys
import requests
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Configuration
RAILWAY_URL = "https://velo-oracle-production.up.railway.app"
CLOUDFLARE_URL = "https://velo-oracle-api.purorestrepo1981.workers.dev"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def check_health(url: str, name: str) -> Tuple[bool, Dict[str, Any]]:
    """Check health endpoint."""
    try:
        response = requests.get(f"{url}/health", timeout=10)
        response.raise_for_status()
        data = response.json()
        return True, data
    except Exception as e:
        return False, {"error": str(e)}

def check_prediction_flow(url: str) -> Tuple[bool, Dict[str, Any]]:
    """Test prediction endpoint."""
    test_payload = {
        "race_id": f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "course": "Ascot",
        "date": "2025-11-19",
        "race_time": "14:30",
        "race_name": "Test Race",
        "dist": "1m",
        "going": "Good",
        "class": "1",
        "runners": [
            {
                "horse": "Test Horse 1",
                "trainer": "Test Trainer",
                "jockey": "Test Jockey",
                "age": 4,
                "weight": 9.0,
                "odds": 5.0
            },
            {
                "horse": "Test Horse 2",
                "trainer": "Test Trainer 2",
                "jockey": "Test Jockey 2",
                "age": 5,
                "weight": 9.2,
                "odds": 3.5
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{url}/v1/predict",
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return True, data
    except Exception as e:
        return False, {"error": str(e)}

def check_models_endpoint(url: str) -> Tuple[bool, Dict[str, Any]]:
    """Check models endpoint."""
    try:
        response = requests.get(f"{url}/v1/models", timeout=10)
        response.raise_for_status()
        data = response.json()
        return True, data
    except Exception as e:
        return False, {"error": str(e)}

def run_checks():
    """Run all production checks."""
    print_header("VÉLØ Oracle Production Checks")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = {
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
    
    # 1. Railway Health Check
    print_header("1. Railway Backend Health Check")
    success, data = check_health(RAILWAY_URL, "Railway")
    if success:
        print_success(f"Railway backend is healthy")
        print(f"   Status: {data.get('status', 'unknown')}")
        print(f"   Version: {data.get('version', 'unknown')}")
        print(f"   Database: {'connected' if data.get('database_connected') else 'disconnected'}")
        results["passed"] += 1
    else:
        print_error(f"Railway backend health check failed")
        print(f"   Error: {data.get('error', 'unknown')}")
        results["failed"] += 1
    
    # 2. Cloudflare Worker Health Check
    print_header("2. Cloudflare Worker Health Check")
    success, data = check_health(CLOUDFLARE_URL, "Cloudflare")
    if success:
        print_success(f"Cloudflare Worker is healthy")
        print(f"   Status: {data.get('status', 'unknown')}")
        if 'edge' in data:
            print(f"   Edge Location: {data['edge'].get('location', 'unknown')}")
            print(f"   Country: {data['edge'].get('country', 'unknown')}")
        if 'backend' in data:
            print(f"   Backend Status: {data['backend'].get('status', 'unknown')}")
        results["passed"] += 1
    else:
        print_error(f"Cloudflare Worker health check failed")
        print(f"   Error: {data.get('error', 'unknown')}")
        results["failed"] += 1
    
    # 3. Prediction Flow Test (via Cloudflare)
    print_header("3. Prediction Flow Test")
    success, data = check_prediction_flow(CLOUDFLARE_URL)
    if success:
        print_success(f"Prediction flow working")
        print(f"   Request ID: {data.get('request_id', 'unknown')}")
        print(f"   Race ID: {data.get('race_id', 'unknown')}")
        print(f"   Predictions: {len(data.get('predictions', []))}")
        print(f"   Logged to DB: {data.get('logged_to_database', False)}")
        results["passed"] += 1
    else:
        print_error(f"Prediction flow test failed")
        print(f"   Error: {data.get('error', 'unknown')}")
        results["failed"] += 1
    
    # 4. Models Endpoint Test
    print_header("4. Models Endpoint Test")
    success, data = check_models_endpoint(RAILWAY_URL)
    if success:
        print_success(f"Models endpoint working")
        print(f"   Models count: {data.get('count', 0)}")
        results["passed"] += 1
    else:
        print_error(f"Models endpoint test failed")
        print(f"   Error: {data.get('error', 'unknown')}")
        results["failed"] += 1
    
    # 5. Proxy Test (Cloudflare → Railway)
    print_header("5. Proxy Test (Cloudflare → Railway)")
    success, data = check_models_endpoint(CLOUDFLARE_URL)
    if success:
        print_success(f"Cloudflare proxy working")
        print(f"   Models count: {data.get('count', 0)}")
        results["passed"] += 1
    else:
        print_error(f"Cloudflare proxy test failed")
        print(f"   Error: {data.get('error', 'unknown')}")
        results["failed"] += 1
    
    # Summary
    print_header("Production Checks Summary")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⚠️  Warnings: {results['warnings']}")
    print()
    
    if results['failed'] == 0:
        print_success("All production checks passed! 🎉")
        return 0
    else:
        print_error(f"{results['failed']} check(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(run_checks())
