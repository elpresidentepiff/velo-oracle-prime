#!/usr/bin/env python3
"""
VÉLØ Oracle - Smoke Tests
Quick smoke tests for critical functionality
"""
import sys
import os
import logging
from pathlib import Path
import requests
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SmokeTestRunner:
    """Run smoke tests for VÉLØ Oracle"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
    
    def test_health_endpoint(self) -> bool:
        """Test health endpoint"""
        try:
            logger.info("Testing health endpoint...")
            response = requests.get(f"{self.base_url}/health", timeout=5)
            
            if response.status_code == 200:
                logger.info("✓ Health endpoint OK")
                return True
            else:
                logger.error(f"✗ Health endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Health endpoint error: {e}")
            return False
    
    def test_predict_endpoint(self) -> bool:
        """Test predict endpoint with dummy data"""
        try:
            logger.info("Testing predict endpoint...")
            
            # Dummy prediction payload
            payload = {
                "race_id": "SMOKE_TEST_001",
                "course": "Flemington",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "race_time": "15:00",
                "race_name": "Smoke Test Race",
                "dist": "1600m",
                "going": "Good",
                "class": "BM78",
                "runners": [
                    {
                        "horse": "Test Horse 1",
                        "trainer": "Test Trainer",
                        "jockey": "Test Jockey",
                        "age": 4,
                        "weight": 57.5,
                        "odds": 5.0
                    },
                    {
                        "horse": "Test Horse 2",
                        "trainer": "Test Trainer 2",
                        "jockey": "Test Jockey 2",
                        "age": 5,
                        "weight": 56.0,
                        "odds": 3.5
                    }
                ]
            }
            
            response = requests.post(
                f"{self.base_url}/v1/predict",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "predictions" in data:
                    logger.info(f"✓ Predict endpoint OK (returned {len(data['predictions'])} predictions)")
                    return True
                else:
                    logger.error("✗ Predict endpoint returned invalid data")
                    return False
            else:
                logger.error(f"✗ Predict endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Predict endpoint error: {e}")
            return False
    
    def test_models_endpoint(self) -> bool:
        """Test models endpoint"""
        try:
            logger.info("Testing models endpoint...")
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "models" in data:
                    logger.info(f"✓ Models endpoint OK (found {len(data['models'])} models)")
                    return True
                else:
                    logger.error("✗ Models endpoint returned invalid data")
                    return False
            else:
                logger.error(f"✗ Models endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Models endpoint error: {e}")
            return False
    
    def test_diagnostics_endpoint(self) -> bool:
        """Test diagnostics endpoint"""
        try:
            logger.info("Testing diagnostics endpoint...")
            response = requests.get(f"{self.base_url}/v1/system/diagnostics", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "status" in data and "components" in data:
                    logger.info(f"✓ Diagnostics endpoint OK (status: {data['status']})")
                    return True
                else:
                    logger.error("✗ Diagnostics endpoint returned invalid data")
                    return False
            else:
                logger.error(f"✗ Diagnostics endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Diagnostics endpoint error: {e}")
            return False
    
    def test_features_endpoint(self) -> bool:
        """Test features endpoint"""
        try:
            logger.info("Testing features endpoint...")
            response = requests.get(f"{self.base_url}/v1/system/features", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "features" in data:
                    logger.info(f"✓ Features endpoint OK (found {len(data['features'])} features)")
                    return True
                else:
                    logger.error("✗ Features endpoint returned invalid data")
                    return False
            else:
                logger.error(f"✗ Features endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Features endpoint error: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all smoke tests"""
        logger.info("=" * 60)
        logger.info("VÉLØ Oracle - Smoke Tests")
        logger.info(f"Target: {self.base_url}")
        logger.info("=" * 60)
        
        tests = [
            ("Health Endpoint", self.test_health_endpoint),
            ("Predict Endpoint", self.test_predict_endpoint),
            ("Models Endpoint", self.test_models_endpoint),
            ("Diagnostics Endpoint", self.test_diagnostics_endpoint),
            ("Features Endpoint", self.test_features_endpoint),
        ]
        
        results = []
        for test_name, test_func in tests:
            logger.info(f"\n--- {test_name} ---")
            success = test_func()
            results.append((test_name, success))
        
        logger.info("\n" + "=" * 60)
        logger.info("Smoke Test Results:")
        for test_name, success in results:
            status = "✓ PASS" if success else "✗ FAIL"
            logger.info(f"  {test_name}: {status}")
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        logger.info(f"\nPassed: {passed}/{total}")
        logger.info("=" * 60)
        
        return passed == total


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run VÉLØ Oracle smoke tests")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    runner = SmokeTestRunner(base_url=args.url)
    all_passed = runner.run_all_tests()
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
