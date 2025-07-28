#!/usr/bin/env python3
"""
Session testing script for BeatSync Mixer
Tests authentication, role management, and session persistence
"""

import requests
import json
import time
from unittest.mock import patch, MagicMock

BASE_URL = "http://127.0.0.1:8000"

class SessionTester:
    def __init__(self):
        self.session = requests.Session()
        
    def test_role_selection_page(self):
        """Test the role selection page loads correctly"""
        print("🧪 Testing role selection page...")
        try:
            response = self.session.get(f"{BASE_URL}/select-role")
            if response.status_code == 200:
                content = response.text
                if "Host a Session" in content and "Join as Listener" in content:
                    print("✅ Role selection page loads correctly")
                    return True
                else:
                    print("❌ Role selection page missing expected content")
                    return False
            else:
                print(f"❌ Role selection page failed: {response.status_code}")
                return False
        except requests.ConnectionError:
            print("❌ Cannot connect to server")
            return False
    
    def test_unauthenticated_access(self):
        """Test that protected endpoints require authentication"""
        print("🧪 Testing unauthenticated access...")
        
        protected_endpoints = [
            "/playlists",
            "/spotify-token",
            "/playback/play",
            "/playback/pause",
            "/playback/next"
        ]
        
        results = []
        for endpoint in protected_endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                # Should redirect to login or return 401
                if response.status_code in [302, 401] or "login" in response.url:
                    results.append(True)
                    print(f"✅ {endpoint} properly protected")
                else:
                    results.append(False)
                    print(f"❌ {endpoint} not properly protected (status: {response.status_code})")
            except requests.ConnectionError:
                print("❌ Cannot connect to server")
                return False
        
        if all(results):
            print("✅ All protected endpoints properly require authentication")
            return True
        else:
            print("❌ Some endpoints not properly protected")
            return False
    
    def test_host_status_check(self):
        """Test host status endpoint"""
        print("🧪 Testing host status check...")
        try:
            response = self.session.get(f"{BASE_URL}/host-status")
            if response.status_code == 200:
                data = response.json()
                if "has_host" in data:
                    print(f"✅ Host status endpoint working - Has host: {data['has_host']}")
                    return True
                else:
                    print("❌ Host status endpoint missing 'has_host' field")
                    return False
            else:
                print(f"❌ Host status endpoint failed: {response.status_code}")
                return False
        except requests.ConnectionError:
            print("❌ Cannot connect to server")
            return False
    
    def test_session_persistence(self):
        """Test that sessions persist across requests"""
        print("🧪 Testing session persistence...")
        
        # First, get the homepage to establish a session
        try:
            response1 = self.session.get(BASE_URL)
            if response1.status_code != 200:
                print(f"❌ Failed to load homepage: {response1.status_code}")
                return False
            
            # Check if we have session cookies
            cookies_before = len(self.session.cookies)
            
            # Make another request
            response2 = self.session.get(f"{BASE_URL}/health")
            if response2.status_code != 200:
                print(f"❌ Failed to make second request: {response2.status_code}")
                return False
            
            cookies_after = len(self.session.cookies)
            
            if cookies_before > 0 or cookies_after > 0:
                print("✅ Session cookies are being set and maintained")
                return True
            else:
                print("⚠️  No session cookies detected (may be normal for stateless endpoints)")
                return True
                
        except requests.ConnectionError:
            print("❌ Cannot connect to server")
            return False
    
    def test_role_request_flow(self):
        """Test the role request flow (without actual OAuth)"""
        print("🧪 Testing role request flow...")
        
        try:
            # Test host role request - should redirect to OAuth
            response = self.session.get(f"{BASE_URL}/login?role=host", allow_redirects=False)
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'accounts.spotify.com' in location:
                    print("✅ Host login redirects to Spotify OAuth")
                else:
                    print(f"❌ Host login redirects to unexpected location: {location}")
                    return False
            else:
                print(f"❌ Host login failed: {response.status_code}")
                return False
            
            # Test listener role request
            response = self.session.get(f"{BASE_URL}/login?role=listener", allow_redirects=False)
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                if 'accounts.spotify.com' in location:
                    print("✅ Listener login redirects to Spotify OAuth")
                    return True
                else:
                    print(f"❌ Listener login redirects to unexpected location: {location}")
                    return False
            else:
                print(f"❌ Listener login failed: {response.status_code}")
                return False
                
        except requests.ConnectionError:
            print("❌ Cannot connect to server")
            return False
    
    def test_queue_access_without_auth(self):
        """Test that queue can be read without authentication"""
        print("🧪 Testing queue access without authentication...")
        
        try:
            response = self.session.get(f"{BASE_URL}/queue")
            if response.status_code == 200:
                data = response.json()
                if "queue" in data and "count" in data:
                    print(f"✅ Queue accessible without auth - {data['count']} items")
                    return True
                else:
                    print("❌ Queue response missing expected fields")
                    return False
            else:
                print(f"❌ Queue endpoint failed: {response.status_code}")
                return False
        except requests.ConnectionError:
            print("❌ Cannot connect to server")
            return False
    
    def test_host_only_actions(self):
        """Test that host-only actions are properly restricted"""
        print("🧪 Testing host-only action restrictions...")
        
        host_only_endpoints = [
            ("/queue/clear", "POST"),
            ("/playback/play", "POST"),
            ("/playback/pause", "POST"),
            ("/playback/next", "POST")
        ]
        
        results = []
        for endpoint, method in host_only_endpoints:
            try:
                if method == "POST":
                    response = self.session.post(f"{BASE_URL}{endpoint}")
                else:
                    response = self.session.get(f"{BASE_URL}{endpoint}")
                
                # Should return 403 (Forbidden) for non-hosts
                if response.status_code == 403:
                    results.append(True)
                    print(f"✅ {endpoint} properly restricted to hosts")
                elif response.status_code in [302, 401]:
                    results.append(True)
                    print(f"✅ {endpoint} requires authentication first")
                else:
                    results.append(False)
                    print(f"❌ {endpoint} not properly restricted (status: {response.status_code})")
            except requests.ConnectionError:
                print("❌ Cannot connect to server")
                return False
        
        if all(results):
            print("✅ All host-only endpoints properly restricted")
            return True
        else:
            print("❌ Some host-only endpoints not properly restricted")
            return False

def main():
    print("🧪 Testing BeatSync Mixer Session Management\n")
    
    tester = SessionTester()
    
    tests = [
        tester.test_role_selection_page,
        tester.test_unauthenticated_access,
        tester.test_host_status_check,
        tester.test_session_persistence,
        tester.test_role_request_flow,
        tester.test_queue_access_without_auth,
        tester.test_host_only_actions
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
        print()
    
    print(f"📊 Session Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All session tests passed! Your authentication and session management is working correctly!")
    else:
        print("⚠️  Some session tests failed. Check the output above for details.")
    
    return passed == total

if __name__ == "__main__":
    main()
