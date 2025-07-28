#!/usr/bin/env python3
"""
Test script for BeatSync Mixer
Runs basic functionality tests
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_health_endpoint():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
            return True
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Cannot connect to server - make sure it's running")
        return False

def test_homepage():
    """Test that the homepage loads"""
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200 and "BeatSync Mixer" in response.text:
            print("✅ Homepage loads correctly")
            return True
        else:
            print(f"❌ Homepage failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Cannot connect to server")
        return False

def test_queue_endpoint():
    """Test the queue endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/queue")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Queue endpoint working - {data.get('count', 0)} items in queue")
            return True
        else:
            print(f"❌ Queue endpoint failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Cannot connect to server")
        return False

def main():
    print("🧪 Testing BeatSync Mixer Application\n")
    
    tests = [
        test_health_endpoint,
        test_homepage,
        test_queue_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your BeatSync Mixer is ready to rock!")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
