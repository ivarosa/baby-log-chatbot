#!/usr/bin/env python3
"""
Simple test script to verify the MPASI-milk endpoints work correctly
"""

import requests
import time
import subprocess
import signal
import os
from contextlib import contextmanager

@contextmanager
def run_server():
    """Context manager to run the FastAPI server temporarily for testing"""
    print("Starting FastAPI server...")
    process = subprocess.Popen([
        "python", "-m", "uvicorn", "main:app", 
        "--host", "127.0.0.1", "--port", "8000"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        yield "http://127.0.0.1:8000"
    finally:
        print("Stopping FastAPI server...")
        process.terminate()
        process.wait(timeout=5)

def test_endpoints():
    """Test both MPASI-milk endpoints"""
    with run_server() as base_url:
        test_user = "testuser"
        
        # Test chart endpoint
        print(f"Testing chart endpoint: {base_url}/mpasi-milk-graph/{test_user}")
        response = requests.get(f"{base_url}/mpasi-milk-graph/{test_user}")
        
        if response.status_code == 200:
            print(f"✓ Chart endpoint working: {len(response.content)} bytes received")
            assert response.headers['content-type'] == 'image/png'
            assert len(response.content) > 1000  # Should be a reasonable size image
        else:
            print(f"✗ Chart endpoint failed: {response.status_code}")
            print(response.text)
            return False
        
        # Test report endpoint  
        print(f"Testing report endpoint: {base_url}/report-mpasi-milk/{test_user}")
        response = requests.get(f"{base_url}/report-mpasi-milk/{test_user}")
        
        if response.status_code == 200:
            print(f"✓ Report endpoint working: {len(response.content)} bytes received")
            assert response.headers['content-type'] == 'application/pdf'
            assert len(response.content) > 5000  # Should be a reasonable size PDF
        else:
            print(f"✗ Report endpoint failed: {response.status_code}")
            print(response.text)
            return False
            
        print("✓ All endpoint tests passed!")
        return True

if __name__ == "__main__":
    print("Testing MPASI-milk endpoints...")
    if test_endpoints():
        print("🎉 All tests passed!")
        exit(0)
    else:
        print("❌ Tests failed!")
        exit(1)