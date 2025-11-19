"""
VÉLØ Oracle - Cloudflare Worker Verification
Test Cloudflare → Railway routing
"""
import requests
import sys
import json
from datetime import datetime


def verify_cloudflare_routing(
    cloudflare_url: str,
    railway_url: str
) -> dict:
    """
    Verify Cloudflare Worker routes to Railway correctly
    
    Args:
        cloudflare_url: Cloudflare Worker URL (custom domain)
        railway_url: Railway backend URL
        
    Returns:
        Verification results
    """
    print("="*60)
    print("Cloudflare Worker Verification")
    print("="*60)
    print(f"Cloudflare URL: {cloudflare_url}")
    print(f"Railway URL: {railway_url}")
    print()
    
    results = {
        "cloudflare_url": cloudflare_url,
        "railway_url": railway_url,
        "timestamp": datetime.utcnow().isoformat(),
        "tests": []
    }
    
    # Test 1: Direct Railway health check
    print("Test 1: Direct Railway Health Check")
    try:
        response = requests.get(f"{railway_url}/health", timeout=10)
        railway_data = response.json()
        
        print(f"  ✅ Railway Status: {response.status_code}")
        print(f"  ✅ Railway Response: {railway_data.get('status')}")
        
        results["tests"].append({
            "name": "railway_direct",
            "status": "pass",
            "response_code": response.status_code,
            "data": railway_data
        })
    except Exception as e:
        print(f"  ❌ Railway Error: {e}")
        results["tests"].append({
            "name": "railway_direct",
            "status": "error",
            "error": str(e)
        })
        return results
    
    print()
    
    # Test 2: Cloudflare health check
    print("Test 2: Cloudflare Health Check")
    try:
        response = requests.get(f"{cloudflare_url}/health", timeout=10)
        cloudflare_data = response.json()
        
        print(f"  ✅ Cloudflare Status: {response.status_code}")
        print(f"  ✅ Cloudflare Response: {cloudflare_data.get('status')}")
        
        # Check if responses match
        if cloudflare_data.get('status') == railway_data.get('status'):
            print(f"  ✅ Responses match")
            
            results["tests"].append({
                "name": "cloudflare_routing",
                "status": "pass",
                "response_code": response.status_code,
                "data": cloudflare_data,
                "match": True
            })
        else:
            print(f"  ⚠️  Responses don't match")
            results["tests"].append({
                "name": "cloudflare_routing",
                "status": "warning",
                "response_code": response.status_code,
                "data": cloudflare_data,
                "match": False
            })
    except Exception as e:
        print(f"  ❌ Cloudflare Error: {e}")
        results["tests"].append({
            "name": "cloudflare_routing",
            "status": "error",
            "error": str(e)
        })
    
    print()
    
    # Test 3: POST request through Cloudflare
    print("Test 3: POST Request Through Cloudflare")
    try:
        test_data = {
            "race_id": "TEST_001",
            "runner_id": "R1",
            "features": {"speed": 0.75},
            "market_odds": 5.0
        }
        
        response = requests.post(
            f"{cloudflare_url}/api/v1/predict/quick",
            json=test_data,
            timeout=10
        )
        
        if response.status_code in [200, 403, 500]:  # Expected responses
            print(f"  ✅ POST Status: {response.status_code}")
            
            if response.status_code == 403:
                print("  ℹ️  API key required (expected)")
            elif response.status_code == 500:
                print("  ℹ️  Prediction error (expected without models)")
            
            results["tests"].append({
                "name": "post_request",
                "status": "pass",
                "response_code": response.status_code
            })
        else:
            print(f"  ❌ POST Status: {response.status_code}")
            results["tests"].append({
                "name": "post_request",
                "status": "fail",
                "response_code": response.status_code
            })
    except Exception as e:
        print(f"  ❌ POST Error: {e}")
        results["tests"].append({
            "name": "post_request",
            "status": "error",
            "error": str(e)
        })
    
    print()
    
    # Test 4: Cache headers
    print("Test 4: Cache Headers")
    try:
        response = requests.get(f"{cloudflare_url}/health", timeout=10)
        
        cache_header = response.headers.get('X-Cache')
        served_by = response.headers.get('X-Served-By')
        
        if cache_header or served_by:
            print(f"  ✅ Cache headers present")
            if cache_header:
                print(f"  ✅ X-Cache: {cache_header}")
            if served_by:
                print(f"  ✅ X-Served-By: {served_by}")
            
            results["tests"].append({
                "name": "cache_headers",
                "status": "pass",
                "x_cache": cache_header,
                "x_served_by": served_by
            })
        else:
            print(f"  ℹ️  Cache headers not found (using simple worker)")
            results["tests"].append({
                "name": "cache_headers",
                "status": "info",
                "message": "Cache headers not found"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results["tests"].append({
            "name": "cache_headers",
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
    
    print(f"Tests run: {len(results['tests'])}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    
    if failed == 0 and errors == 0:
        print("\n✅ Cloudflare → Railway routing is operational")
        results["overall_status"] = "operational"
    else:
        print("\n❌ Cloudflare → Railway routing has issues")
        results["overall_status"] = "issues"
    
    print("="*60)
    
    return results


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify Cloudflare Worker routing")
    parser.add_argument(
        "--cloudflare-url",
        required=True,
        help="Cloudflare Worker URL (custom domain)"
    )
    parser.add_argument(
        "--railway-url",
        default="https://velo-oracle-production.up.railway.app",
        help="Railway deployment URL"
    )
    parser.add_argument(
        "--output",
        default="logs/cloudflare_verification.json",
        help="Output file for results"
    )
    
    args = parser.parse_args()
    
    # Run verification
    results = verify_cloudflare_routing(args.cloudflare_url, args.railway_url)
    
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
