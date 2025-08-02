#!/usr/bin/env python3
"""
Test Last.fm recommendations directly
"""

import requests
import os

def manual_lastfm_get_similar(artist, title, api_key, limit=5):
    """Manual Last.fm API call using hardcoded IPs as DNS fallback"""
    ip_addresses = ["130.211.19.189"]
    
    params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': str(limit)
    }
    
    print(f"Testing Last.fm API for: {artist} - {title}")
    print(f"API Key: {api_key[:8]}...")
    print(f"Params: {params}")
    
    for ip in ip_addresses:
        try:
            url = f"http://{ip}/2.0/"
            headers = {
                'Host': 'ws.audioscrobbler.com',
                'User-Agent': 'BeatSyncMixer/1.0'
            }
            
            print(f"Trying IP: {ip}")
            print(f"URL: {url}")
            print(f"Headers: {headers}")
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                params=params,
                headers=headers,
                timeout=(5, 10)
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {response.headers}")
            print(f"Response content: {response.text[:500]}...")
            
            if response.status_code == 200:
                data = response.json()
                
                if 'error' in data:
                    print(f"Last.fm API error: {data.get('message', 'Unknown error')}")
                    return None
                
                similar_tracks = []
                tracks = data.get('similartracks', {}).get('track', [])
                
                if isinstance(tracks, dict):
                    tracks = [tracks]
                
                for track in tracks[:limit]:
                    similar_tracks.append({
                        'artist': track.get('artist', {}).get('name', 'Unknown Artist'),
                        'title': track.get('name', 'Unknown Title'),
                        'url': track.get('url', '#')
                    })
                
                print(f"Found {len(similar_tracks)} recommendations")
                return similar_tracks
                
        except Exception as e:
            print(f"Manual Last.fm API call failed for IP {ip}: {e}")
            continue
    
    return None

if __name__ == "__main__":
    # Get API key from env
    api_key = "cd3e4e3e4088908b188604cb82ded903"  # From heroku config
    
    # Test with a known track
    recommendations = manual_lastfm_get_similar("The Beatles", "Hey Jude", api_key, limit=5)
    
    if recommendations:
        print(f"✅ Found {len(recommendations)} recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec['artist']} - {rec['title']} ({rec['url']})")
    else:
        print("❌ No recommendations found")
