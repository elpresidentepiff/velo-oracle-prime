"""
VÉLØ Oracle - Railway Deployment Verification
Test Railway backend health and endpoints
"""
import requests
import sys
import json
from datetime import datetime


def verify_railway_backend(railway_url: str) -> dict:
    """
    Verify Railway backend is operational
    
    Args:
        railway_url: Railway deployment URL
        
    Returns:
        Verification results
    """
    print("="*60)
    print("Railway Backend Verification")
    print("="*60)
    print(f"URL: {railway_url}")
    print()
    
    results = {
        "url": railway_url,
        "timestamp": datetime.utcnow().isoformat(),
        "tests": []
    }
    
    # Test 1: Health check
    print("Test 1: Health Check")
    try:
        response = requests.get(f"{railway_url}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Response: {json.dumps(data, indent=2)}")
            
            results["tests"].append({
                "name": "health_check",
                "status": "pass",
                "response_code": 200,
                "response_time_ms": response.elapsed.total_seconds() * 1000
            })
        else:
            print(f"  ❌ Status: {response.status_code}")
            results["tests"].append({
                "name": "health_check",
                "status": "fail",
                "response_code": response.status_code
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["tests"].append({
            "name": "health_check",
            "status": "error",
            "error": str(e)
        })
    
    print()
    
    # Test 2: Root endpoint
    print("Test 2: Root Endpoint")
    try:
        response = requests.get(f"{railway_url}/", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Status: {response.status_code}")
            print(f"  ✅ Message: {data.get('message')}")
            
            results["tests"].append({
                "name": "root_endpoint",
                "status": "pass",
                "response_code": 200
            })
        else:
            print(f"  ❌ Status: {response.status_code}")
            results["tests"].append({
                "name": "root_endpoint",
                "status": "fail",
                "response_code": response.status_code
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["tests"].append({
            "name": "root_endpoint",
            "status": "error",
            "error": str(e)
        })
    
    print()
    
    # Test 3: API status
    print("Test 3: API Status")
    try:
        response = requests.get(f"{railway_url}/api/v1/status", timeout=10)
        
        if response.status_code in [200, 403]:  # 403 = API key required (expected)
            print(f"  ✅ Status: {response.status_code}")
            if response.status_code == 403:
                print("  ℹ️  API key required (expected)")
            
            results["tests"].append({
                "name": "api_status",
                "status": "pass",
                "response_code": response.status_code
            })
        else:
            print(f"  ❌ Status: {response.status_code}")
            results["tests"].append({
                "name": "api_status",
                "status": "fail",
                "response_code": response.status_code
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["tests"].append({
            "name": "api_status",
            "status": "error",
            "error": str(e)
        })
    
    print()
    
    # Test 4: CORS headers
    print("Test 4: CORS Headers")
    try:
        response = requests.options(f"{railway_url}/health", timeout=10)
        
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers')
        }
        
        if cors_headers['Access-Control-Allow-Origin']:
            print(f"  ✅ CORS enabled")
            print(f"  ✅ Allow-Origin: {cors_headers['Access-Control-Allow-Origin']}")
            
            results["tests"].append({
                "name": "cors_headers",
                "status": "pass",
                "cors_headers": cors_headers
            })
        else:
            print(f"  ⚠️  CORS headers not found")
            results["tests"].append({
                "name": "cors_headers",
                "status": "warning",
                "message": "CORS headers not found"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["tests"].append({
            "name": "cors_headers",
            "status": "error",
            "error": str(e)
        })
    
    print()
    
    # Summary
    print("="*60)
    print("Verification Summary")
    print("="*60)
    
    passed = sum(1 for t in results["tests"] if t["status"] == "pass")
    failed = sum(1 for t in results["tests"] if t["status"] == "fail")
    errors = sum(1 for t in results["tests"] if t["status"] == "error")
    warnings = sum(1 for t in results["tests"] if t["status"] == "warning")
    
    print(f"Tests run: {len(results['tests'])}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print(f"Warnings: {warnings}")
    
    if failed == 0 and errors == 0:
        print("\n✅ Railway backend is operational")
        results["overall_status"] = "operational"
    else:
        print("\n❌ Railway backend has issues")
        results["overall_status"] = "issues"
    
    print("="*60)
    
    return results


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify Railway deployment")
    parser.add_argument(
        "--url",
        default="https://velo-oracle-production.up.railway.app",
        help="Railway deployment URL"
    )
    parser.add_argument(
        "--output",
        default="logs/railway_verification.json",
        help="Output file for results"
    )
    
    args = parser.parse_args()
    
    # Run verification
    results = verify_railway_backend(args.url)
    
    # Save results
    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to {args.output}")
    
    # Exit code
    if results["overall_status"] == "operational":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
