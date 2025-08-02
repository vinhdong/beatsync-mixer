#!/usr/bin/env python3
"""
Test manual Last.fm API implementation
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

def manual_lastfm_get_similar(artist, title, api_key, limit=5):
    """Manual Last.fm API call using hardcoded IPs as DNS fallback"""
    
    # Last.fm API IP addresses (ws.audioscrobbler.com)
    ip_addresses = ["130.211.19.189"]
    
    # Build API parameters
    params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': str(limit)
    }
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Make request directly to IP, use Host header for routing
            url = f"http://{ip}/2.0/"
            headers = {
                'Host': 'ws.audioscrobbler.com',
                'User-Agent': 'BeatSyncMixer/1.0'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                params=params,
                headers=headers,
                timeout=(5, 10)  # 5s connect, 10s read timeout
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text[:500]}...")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for Last.fm API errors
                if 'error' in data:
                    print(f"Last.fm API error: {data.get('message', 'Unknown error')}")
                    return None
                
                # Parse similar tracks
                similar_tracks = []
                tracks = data.get('similartracks', {}).get('track', [])
                
                # Handle case where only one similar track is returned (not a list)
                if isinstance(tracks, dict):
                    tracks = [tracks]
                
                for track in tracks[:limit]:
                    similar_tracks.append({
                        'artist': track.get('artist', {}).get('name', 'Unknown Artist'),
                        'title': track.get('name', 'Unknown Title'),
                        'url': track.get('url', '#')
                    })
                
                return similar_tracks
                
        except Exception as e:
            print(f"Manual Last.fm API call failed for IP {ip}: {e}")
            continue
    
    return None

def test_manual_lastfm():
    """Test the manual Last.fm implementation"""
    print("🎵 Testing manual Last.fm API...")
    
    api_key = os.getenv("LASTFM_API_KEY")
    print(f"API Key: {api_key[:10]}...")
    
    # Test with a well-known track
    artist = "Radiohead"
    title = "Creep"
    
    recommendations = manual_lastfm_get_similar(artist, title, api_key, limit=5)
    
    if recommendations:
        print(f"✅ Found {len(recommendations)} recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec['artist']} - {rec['title']}")
            print(f"      URL: {rec['url']}")
        return True
    else:
        print("❌ No recommendations found")
        return False

if __name__ == "__main__":
    success = test_manual_lastfm()
    if success:
        print("\n✅ Manual Last.fm API is working!")
    else:
        print("\n❌ Manual Last.fm API test failed!")
