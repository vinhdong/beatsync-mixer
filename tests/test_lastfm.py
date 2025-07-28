#!/usr/bin/env python3
"""
Test script for Last.fm recommendations feature
"""

import requests
import socketio
import time

BASE_URL = "http://127.0.0.1:8000"

def test_lastfm_recommendations():
    print("🎵 Testing Last.fm Recommendations Feature")
    print("=" * 50)
    
    # First, add a test track to the queue using Socket.IO
    print("📝 Adding test track to queue...")
    sio = socketio.SimpleClient()
    
    try:
        sio.connect(BASE_URL)
        
        # Add a well-known track with proper format
        test_track = {
            'track_uri': 'spotify:track:testradiohead',
            'track_name': 'Radiohead — Creep'  # Famous song that should have similar tracks
        }
        
        sio.emit('queue_add', test_track)
        time.sleep(1)  # Wait for the track to be added
        
        print(f"✅ Added track: {test_track['track_name']}")
        sio.disconnect()
        
        # Now test the recommendation endpoint
        print("🔍 Testing recommendations endpoint...")
        
        response = requests.get(f"{BASE_URL}/recommend/{test_track['track_uri']}")
        
        if response.status_code == 200:
            data = response.json()
            recommendations = data.get('recommendations', [])
            
            print(f"✅ Got {len(recommendations)} recommendations:")
            for i, rec in enumerate(recommendations, 1):
                print(f"   {i}. {rec['artist']} — {rec['title']}")
                print(f"      URL: {rec['url']}")
            
            return True
        else:
            print(f"❌ Recommendation endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

def test_error_cases():
    print("\n🧪 Testing error cases...")
    
    # Test with non-existent track
    response = requests.get(f"{BASE_URL}/recommend/spotify:track:nonexistent")
    if response.status_code == 404:
        print("✅ Non-existent track returns 404 as expected")
    else:
        print(f"❌ Expected 404, got {response.status_code}")
    
    # Test current queue state
    response = requests.get(f"{BASE_URL}/queue")
    if response.status_code == 200:
        data = response.json()
        print(f"📊 Current queue has {data['count']} tracks")

if __name__ == "__main__":
    success = test_lastfm_recommendations()
    test_error_cases()
    
    if success:
        print("\n🎉 Last.fm recommendations feature is working!")
    else:
        print("\n⚠️ Last.fm recommendations feature needs debugging.")
