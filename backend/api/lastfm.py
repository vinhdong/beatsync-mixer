"""
Last.fm API integration for BeatSync Mixer.
Handles music recommendations and track similarity.
"""

import os
import requests


def get_similar_tracks(artist, title, limit=5):
    """Get similar tracks from Last.fm API with fallback methods"""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        print("❌ Last.fm API key not configured")
        return []
    
    params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': str(min(limit, 3))  # Request fewer tracks for faster response
    }
    
    # Try direct API call first with shorter timeout
    try:
        print(f"🎵 Getting Last.fm recommendations for: {artist} - {title}")
        
        response = requests.get(
            "http://ws.audioscrobbler.com/2.0/",
            params=params,
            timeout=(3, 5),  # Much shorter timeout: 3s connect, 5s read
            headers={'User-Agent': 'BeatSyncMixer/1.0'}
        )
        
        print(f"Last.fm API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'error' in data:
                print(f"❌ Last.fm API error: {data.get('message', 'Unknown error')}")
                return []
            
            similar_tracks = []
            tracks = data.get('similartracks', {}).get('track', [])
            
            if isinstance(tracks, dict):
                tracks = [tracks]
            
            for track in tracks[:limit]:
                artist_name = track.get('artist', {})
                if isinstance(artist_name, dict):
                    artist_name = artist_name.get('name', 'Unknown Artist')
                elif isinstance(artist_name, str):
                    artist_name = artist_name
                else:
                    artist_name = 'Unknown Artist'
                
                similar_tracks.append({
                    'artist': artist_name,
                    'title': track.get('name', 'Unknown Title'),
                    'url': track.get('url', '#'),
                    'source': 'Last.fm'
                })
            
            print(f"✅ Found {len(similar_tracks)} recommendations")
            return similar_tracks
        else:
            print(f"❌ Last.fm API returned status {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Last.fm API call failed: {e}")
    
    # If we get here, the API call failed - try faster IP fallback
    print("🔄 Trying IP fallback...")
    
    # Fallback to IP-based call with even shorter timeout
    ip_addresses = ["130.211.19.189", "64.34.119.12"]  # Updated IP addresses for Last.fm
    
    for ip in ip_addresses:
        try:
            url = f"http://{ip}/2.0/"
            headers = {
                'Host': 'ws.audioscrobbler.com',
                'User-Agent': 'BeatSyncMixer/1.0'
            }
            
            print(f"Trying IP fallback: {ip}")
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=(2, 3)  # Very short timeout for IP fallback
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'error' in data:
                    print(f"Last.fm API error (IP {ip}): {data.get('message', 'Unknown error')}")
                    continue
                
                similar_tracks = []
                tracks = data.get('similartracks', {}).get('track', [])
                
                if isinstance(tracks, dict):
                    tracks = [tracks]
                
                for track in tracks[:limit]:
                    artist_name = track.get('artist', {})
                    if isinstance(artist_name, dict):
                        artist_name = artist_name.get('name', 'Unknown Artist')
                    elif isinstance(artist_name, str):
                        artist_name = artist_name
                    else:
                        artist_name = 'Unknown Artist'
                    
                    similar_tracks.append({
                        'artist': artist_name,
                        'title': track.get('name', 'Unknown Title'),
                        'url': track.get('url', '#'),
                        'source': 'Last.fm'
                    })
                
                print(f"✅ Found {len(similar_tracks)} recommendations via IP {ip}")
                return similar_tracks
                
        except Exception as e:
            print(f"IP fallback failed for {ip}: {e}")
            continue
    
    # Final fallback: try HTTPS quickly
    try:
        print("🔄 Trying HTTPS as final fallback...")
        response = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params=params,
            timeout=(2, 3),
            headers={'User-Agent': 'BeatSyncMixer/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                similar_tracks = []
                tracks = data.get('similartracks', {}).get('track', [])
                
                if isinstance(tracks, dict):
                    tracks = [tracks]
                
                for track in tracks[:limit]:
                    artist_name = track.get('artist', {})
                    if isinstance(artist_name, dict):
                        artist_name = artist_name.get('name', 'Unknown Artist')
                    elif isinstance(artist_name, str):
                        artist_name = artist_name
                    else:
                        artist_name = 'Unknown Artist'
                    
                    similar_tracks.append({
                        'artist': artist_name,
                        'title': track.get('name', 'Unknown Title'),
                        'url': track.get('url', '#'),
                        'source': 'Last.fm'
                    })
                
                print(f"✅ Found {len(similar_tracks)} recommendations via HTTPS")
                return similar_tracks
    except Exception as e:
        print(f"HTTPS fallback failed: {e}")
    
    print("❌ All Last.fm API attempts failed")
    return []


def get_track_info(artist, title):
    """Get track information from Last.fm API"""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return None
    
    params = {
        'method': 'track.getInfo',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json'
    }
    
    try:
        response = requests.get(
            "http://ws.audioscrobbler.com/2.0/",
            params=params,
            timeout=(3, 5),
            headers={'User-Agent': 'BeatSyncMixer/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                return data.get('track', {})
                
    except Exception as e:
        print(f"Error getting track info from Last.fm: {e}")
    
    return None
