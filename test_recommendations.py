#!/usr/bin/env python3
"""
Test Last.fm recommendations endpoint directly
"""

import requests
import json

# Test with a known track that should have recommendations
def test_recommendations_endpoint():
    """Test the Last.fm recommendations without authentication"""
    print("🎵 Testing Last.fm recommendations endpoint...")
    
    # We'll need to modify the endpoint to accept artist/title directly for testing
    # Or create a test endpoint that bypasses Spotify auth
    
    # For now, let's test what happens when we call the existing endpoint
    base_url = "https://beatsync-mixer-5715861af181.herokuapp.com"
    
    # Try with a fake track URI
    test_uri = "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"  # This is "Mr. Brightside" by The Killers
    
    response = requests.get(f"{base_url}/recommend/{test_uri}")
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 401:
        print("❌ Authentication required - this is expected")
        return False
    elif response.status_code == 200:
        data = response.json()
        print(f"✅ Got recommendations: {data}")
        return True
    else:
        print(f"❌ Unexpected response: {response.status_code}")
        return False

if __name__ == "__main__":
    test_recommendations_endpoint()
