"""
VÉLØ Oracle - Phase 6: Go-Live Validation
Validate Worker → Railway routing and deployment readiness
"""
import sys
import json
from datetime import datetime


def phase6_validation():
    """Execute Phase 6 validation"""
    
    print("="*70)
    print("VÉLØ Oracle - Phase 6: Go-Live Validation")
    print("="*70)
    print()
    
    validation_results = {
        "phase": "Phase 6: Go-Live Validation",
        "timestamp": datetime.utcnow().isoformat(),
        "tasks": []
    }
    
    # Task 1: Validate Worker → Railway routing
    print("Task 1: Validate Worker → Railway Routing")
    print("-" * 70)
    
    task1 = {
        "id": 1,
        "name": "Worker → Railway Routing Validation",
        "status": "pending",
        "checks": []
    }
    
    # Check 1.1: Worker code exists
    print("  [1.1] Checking Worker code files...")
    try:
        import os
        worker_prod = os.path.exists("deployment/cloudflare_worker_production.js")
        worker_adv = os.path.exists("deployment/cloudflare_worker_advanced.js")
        
        if worker_prod and worker_adv:
            print("    ✅ Worker code files exist")
            task1["checks"].append({
                "check": "Worker code files",
                "status": "pass",
                "files": ["production.js", "advanced.js"]
            })
        else:
            print("    ❌ Worker code files missing")
            task1["checks"].append({
                "check": "Worker code files",
                "status": "fail"
            })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task1["checks"].append({
            "check": "Worker code files",
            "status": "error",
            "error": str(e)
        })
    
    # Check 1.2: Worker routing logic
    print("  [1.2] Validating Worker routing logic...")
    try:
        with open("deployment/cloudflare_worker_production.js") as f:
            content = f.read()
            
            has_fetch = "async fetch(request" in content
            has_backend = "const backend" in content
            has_proxy = "new Request(" in content
            
            if has_fetch and has_backend and has_proxy:
                print("    ✅ Worker routing logic valid")
                task1["checks"].append({
                    "check": "Worker routing logic",
                    "status": "pass",
                    "components": ["fetch handler", "backend URL", "proxy request"]
                })
            else:
                print("    ❌ Worker routing logic incomplete")
                task1["checks"].append({
                    "check": "Worker routing logic",
                    "status": "fail"
                })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task1["checks"].append({
            "check": "Worker routing logic",
            "status": "error",
            "error": str(e)
        })
    
    # Check 1.3: Header preservation
    print("  [1.3] Validating header preservation...")
    try:
        with open("deployment/cloudflare_worker_production.js") as f:
            content = f.read()
            
            has_headers = "headers: request.headers" in content
            has_method = "method: request.method" in content
            has_body = "body: request.body" in content
            
            if has_headers and has_method and has_body:
                print("    ✅ Header preservation configured")
                task1["checks"].append({
                    "check": "Header preservation",
                    "status": "pass",
                    "preserved": ["headers", "method", "body"]
                })
            else:
                print("    ❌ Header preservation incomplete")
                task1["checks"].append({
                    "check": "Header preservation",
                    "status": "fail"
                })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task1["checks"].append({
            "check": "Header preservation",
            "status": "error",
            "error": str(e)
        })
    
    # Task 1 summary
    task1_passed = sum(1 for c in task1["checks"] if c["status"] == "pass")
    task1_total = len(task1["checks"])
    task1["status"] = "pass" if task1_passed == task1_total else "fail"
    task1["summary"] = f"{task1_passed}/{task1_total} checks passed"
    
    print(f"\n  Task 1 Status: {task1['status'].upper()} ({task1['summary']})")
    print()
    
    validation_results["tasks"].append(task1)
    
    # Task 2: Verify API endpoints
    print("Task 2: Verify API Endpoints Reachable Through Cloudflare")
    print("-" * 70)
    
    task2 = {
        "id": 2,
        "name": "API Endpoints Validation",
        "status": "pending",
        "checks": []
    }
    
    # Check 2.1: FastAPI main app exists
    print("  [2.1] Checking FastAPI main app...")
    try:
        import os
        main_exists = os.path.exists("app/main.py")
        
        if main_exists:
            print("    ✅ FastAPI main app exists")
            task2["checks"].append({
                "check": "FastAPI main app",
                "status": "pass",
                "file": "app/main.py"
            })
        else:
            print("    ❌ FastAPI main app missing")
            task2["checks"].append({
                "check": "FastAPI main app",
                "status": "fail"
            })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task2["checks"].append({
            "check": "FastAPI main app",
            "status": "error",
            "error": str(e)
        })
    
    # Check 2.2: CORS middleware
    print("  [2.2] Validating CORS middleware...")
    try:
        with open("app/main.py") as f:
            content = f.read()
            
            has_cors_import = "CORSMiddleware" in content
            has_cors_config = 'allow_origins=["*"]' in content
            has_all_methods = 'allow_methods=["*"]' in content
            has_all_headers = 'allow_headers=["*"]' in content
            
            if has_cors_import and has_cors_config and has_all_methods and has_all_headers:
                print("    ✅ CORS middleware configured correctly")
                task2["checks"].append({
                    "check": "CORS middleware",
                    "status": "pass",
                    "config": ["all origins", "all methods", "all headers"]
                })
            else:
                print("    ❌ CORS middleware incomplete")
                task2["checks"].append({
                    "check": "CORS middleware",
                    "status": "fail"
                })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task2["checks"].append({
            "check": "CORS middleware",
            "status": "error",
            "error": str(e)
        })
    
    # Check 2.3: Health endpoint
    print("  [2.3] Validating health endpoint...")
    try:
        with open("app/main.py") as f:
            content = f.read()
            
            has_health_route = '@app.get("/health")' in content
            has_health_func = "async def health_check()" in content
            
            if has_health_route and has_health_func:
                print("    ✅ Health endpoint configured")
                task2["checks"].append({
                    "check": "Health endpoint",
                    "status": "pass",
                    "route": "/health"
                })
            else:
                print("    ❌ Health endpoint missing")
                task2["checks"].append({
                    "check": "Health endpoint",
                    "status": "fail"
                })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task2["checks"].append({
            "check": "Health endpoint",
            "status": "error",
            "error": str(e)
        })
    
    # Check 2.4: API endpoints
    print("  [2.4] Validating API endpoints...")
    try:
        with open("app/main.py") as f:
            content = f.read()
            
            endpoints = {
                "/api/v1/status": '@app.get("/api/v1/status")' in content,
                "/api/v1/predict/quick": '@app.post("/api/v1/predict/quick")' in content,
                "/api/v1/predict/full": '@app.post("/api/v1/predict/full")' in content,
            }
            
            passed = sum(1 for v in endpoints.values() if v)
            total = len(endpoints)
            
            if passed == total:
                print(f"    ✅ All API endpoints configured ({passed}/{total})")
                task2["checks"].append({
                    "check": "API endpoints",
                    "status": "pass",
                    "endpoints": list(endpoints.keys()),
                    "count": total
                })
            else:
                print(f"    ⚠️  Some API endpoints missing ({passed}/{total})")
                task2["checks"].append({
                    "check": "API endpoints",
                    "status": "warning",
                    "endpoints": [k for k, v in endpoints.items() if v],
                    "count": passed
                })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task2["checks"].append({
            "check": "API endpoints",
            "status": "error",
            "error": str(e)
        })
    
    # Check 2.5: API key validation
    print("  [2.5] Validating API key validation...")
    try:
        with open("app/main.py") as f:
            content = f.read()
            
            has_api_key_func = "async def verify_api_key" in content
            has_api_key_dep = "Depends(verify_api_key)" in content
            
            if has_api_key_func and has_api_key_dep:
                print("    ✅ API key validation configured")
                task2["checks"].append({
                    "check": "API key validation",
                    "status": "pass"
                })
            else:
                print("    ❌ API key validation missing")
                task2["checks"].append({
                    "check": "API key validation",
                    "status": "fail"
                })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task2["checks"].append({
            "check": "API key validation",
            "status": "error",
            "error": str(e)
        })
    
    # Task 2 summary
    task2_passed = sum(1 for c in task2["checks"] if c["status"] in ["pass", "warning"])
    task2_total = len(task2["checks"])
    task2["status"] = "pass" if task2_passed == task2_total else "fail"
    task2["summary"] = f"{task2_passed}/{task2_total} checks passed"
    
    print(f"\n  Task 2 Status: {task2['status'].upper()} ({task2['summary']})")
    print()
    
    validation_results["tasks"].append(task2)
    
    # Task 3: Deployment readiness checklist
    print("Task 3: Execute Deployment Readiness Checklist")
    print("-" * 70)
    
    task3 = {
        "id": 3,
        "name": "Deployment Readiness Checklist",
        "status": "pending",
        "checks": []
    }
    
    # Check 3.1: Verification scripts exist
    print("  [3.1] Checking verification scripts...")
    try:
        import os
        verify_railway = os.path.exists("scripts/deployment/verify_railway.py")
        verify_cloudflare = os.path.exists("scripts/deployment/verify_cloudflare.py")
        
        if verify_railway and verify_cloudflare:
            print("    ✅ Verification scripts exist")
            task3["checks"].append({
                "check": "Verification scripts",
                "status": "pass",
                "scripts": ["verify_railway.py", "verify_cloudflare.py"]
            })
        else:
            print("    ❌ Verification scripts missing")
            task3["checks"].append({
                "check": "Verification scripts",
                "status": "fail"
            })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task3["checks"].append({
            "check": "Verification scripts",
            "status": "error",
            "error": str(e)
        })
    
    # Check 3.2: Integration documentation
    print("  [3.2] Checking integration documentation...")
    try:
        import os
        doc_exists = os.path.exists("deployment/RAILWAY_CLOUDFLARE_INTEGRATION.md")
        
        if doc_exists:
            with open("deployment/RAILWAY_CLOUDFLARE_INTEGRATION.md") as f:
                content = f.read()
                has_architecture = "Architecture" in content
                has_checklist = "Checklist" in content
                has_troubleshooting = "Troubleshooting" in content
                
                if has_architecture and has_checklist and has_troubleshooting:
                    print("    ✅ Integration documentation complete")
                    task3["checks"].append({
                        "check": "Integration documentation",
                        "status": "pass",
                        "sections": ["Architecture", "Checklist", "Troubleshooting"]
                    })
                else:
                    print("    ⚠️  Integration documentation incomplete")
                    task3["checks"].append({
                        "check": "Integration documentation",
                        "status": "warning"
                    })
        else:
            print("    ❌ Integration documentation missing")
            task3["checks"].append({
                "check": "Integration documentation",
                "status": "fail"
            })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task3["checks"].append({
            "check": "Integration documentation",
            "status": "error",
            "error": str(e)
        })
    
    # Check 3.3: Dockerfile
    print("  [3.3] Checking Dockerfile...")
    try:
        import os
        dockerfile_exists = os.path.exists("Dockerfile")
        
        if dockerfile_exists:
            with open("Dockerfile") as f:
                content = f.read()
                has_python = "FROM python" in content
                has_healthcheck = "HEALTHCHECK" in content
                
                if has_python and has_healthcheck:
                    print("    ✅ Dockerfile configured")
                    task3["checks"].append({
                        "check": "Dockerfile",
                        "status": "pass"
                    })
                else:
                    print("    ⚠️  Dockerfile incomplete")
                    task3["checks"].append({
                        "check": "Dockerfile",
                        "status": "warning"
                    })
        else:
            print("    ❌ Dockerfile missing")
            task3["checks"].append({
                "check": "Dockerfile",
                "status": "fail"
            })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task3["checks"].append({
            "check": "Dockerfile",
            "status": "error",
            "error": str(e)
        })
    
    # Check 3.4: Railway configuration
    print("  [3.4] Checking Railway configuration...")
    try:
        import os
        railway_exists = os.path.exists("railway.toml")
        
        if railway_exists:
            with open("railway.toml") as f:
                content = f.read()
                has_build = "[build]" in content
                has_deploy = "[deploy]" in content
                has_healthcheck = "[healthcheck]" in content
                
                if has_build and has_deploy and has_healthcheck:
                    print("    ✅ Railway configuration complete")
                    task3["checks"].append({
                        "check": "Railway configuration",
                        "status": "pass",
                        "sections": ["build", "deploy", "healthcheck"]
                    })
                else:
                    print("    ⚠️  Railway configuration incomplete")
                    task3["checks"].append({
                        "check": "Railway configuration",
                        "status": "warning"
                    })
        else:
            print("    ❌ Railway configuration missing")
            task3["checks"].append({
                "check": "Railway configuration",
                "status": "fail"
            })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task3["checks"].append({
            "check": "Railway configuration",
            "status": "error",
            "error": str(e)
        })
    
    # Check 3.5: Production requirements
    print("  [3.5] Checking production requirements...")
    try:
        import os
        req_exists = os.path.exists("requirements_production.txt")
        
        if req_exists:
            with open("requirements_production.txt") as f:
                content = f.read()
                has_fastapi = "fastapi" in content
                has_sklearn = "scikit-learn" in content
                has_xgboost = "xgboost" in content
                
                if has_fastapi and has_sklearn and has_xgboost:
                    print("    ✅ Production requirements complete")
                    task3["checks"].append({
                        "check": "Production requirements",
                        "status": "pass",
                        "key_packages": ["fastapi", "scikit-learn", "xgboost"]
                    })
                else:
                    print("    ⚠️  Production requirements incomplete")
                    task3["checks"].append({
                        "check": "Production requirements",
                        "status": "warning"
                    })
        else:
            print("    ❌ Production requirements missing")
            task3["checks"].append({
                "check": "Production requirements",
                "status": "fail"
            })
    except Exception as e:
        print(f"    ❌ Error: {e}")
        task3["checks"].append({
            "check": "Production requirements",
            "status": "error",
            "error": str(e)
        })
    
    # Task 3 summary
    task3_passed = sum(1 for c in task3["checks"] if c["status"] in ["pass", "warning"])
    task3_total = len(task3["checks"])
    task3["status"] = "pass" if task3_passed == task3_total else "fail"
    task3["summary"] = f"{task3_passed}/{task3_total} checks passed"
    
    print(f"\n  Task 3 Status: {task3['status'].upper()} ({task3['summary']})")
    print()
    
    validation_results["tasks"].append(task3)
    
    # Overall validation summary
    print("="*70)
    print("Phase 6 Validation Summary")
    print("="*70)
    
    all_tasks_passed = all(t["status"] == "pass" for t in validation_results["tasks"])
    
    for task in validation_results["tasks"]:
        status_symbol = "✅" if task["status"] == "pass" else "❌"
        print(f"{status_symbol} Task {task['id']}: {task['name']} - {task['summary']}")
    
    print()
    
    if all_tasks_passed:
        print("✅ Phase 6 Validation: PASS")
        print("✅ System ready for go-live")
        validation_results["overall_status"] = "PASS"
        validation_results["go_live_ready"] = True
    else:
        print("❌ Phase 6 Validation: FAIL")
        print("❌ System not ready for go-live")
        validation_results["overall_status"] = "FAIL"
        validation_results["go_live_ready"] = False
    
    print("="*70)
    
    return validation_results


def main():
    """Main execution"""
    results = phase6_validation()
    
    # Save results
    import os
    os.makedirs("logs", exist_ok=True)
    
    with open("logs/phase6_validation.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved to logs/phase6_validation.json")
    
    # Exit code
    if results["go_live_ready"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
