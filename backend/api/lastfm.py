"""
Last.fm API integration for BeatSync Mixer.
Optimized for speed with shorter timeouts and efficient error handling.
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_similar_tracks(artist, title, limit=5):
    """Get similar tracks from Last.fm API with optimized performance"""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        print("❌ Last.fm API key not configured")
        print(f"🔍 Available env vars: {[k for k in os.environ.keys() if 'LASTFM' in k]}")
        return []
    
    params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': str(min(limit, 3))  # Reduced limit for faster response
    }
    
    # Optimized: Single HTTP request with shorter timeout for speed
    try:
        print(f"🎵 Getting Last.fm recommendations for: '{artist}' - '{title}'")
        print(f"🔑 Using API key: {api_key[:8]}..." if api_key else "❌ No API key")
        
        response = requests.get(
            "http://ws.audioscrobbler.com/2.0/",
            params=params,
            timeout=(3, 6),  # Slightly increased for reliability
            headers={
                'User-Agent': 'BeatSyncMixer/1.0',
                'Accept': 'application/json'
            }
        )
        
        print(f"📡 Last.fm API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📊 Last.fm response keys: {list(data.keys())}")
            
            if 'error' in data:
                print(f"❌ Last.fm API error {data.get('error', 'Unknown')}: {data.get('message', 'Unknown error')}")
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
            print(f"❌ Last.fm API returned status {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Last.fm API call failed: {e}")
        return []


def get_top_tracks(artist, limit=5):
    """Get top tracks for an artist from Last.fm API"""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []
    
    params = {
        'method': 'artist.gettoptracks',
        'artist': artist,
        'api_key': api_key,
        'format': 'json',
        'limit': str(limit)
    }
    
    try:
        response = requests.get(
            "http://ws.audioscrobbler.com/2.0/",
            params=params,
            timeout=(2, 4),  # Fast timeout
            headers={'User-Agent': 'BeatSyncMixer/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                tracks = data.get('toptracks', {}).get('track', [])
                if isinstance(tracks, dict):
                    tracks = [tracks]
                
                top_tracks = []
                for track in tracks[:limit]:
                    top_tracks.append({
                        'artist': artist,
                        'title': track.get('name', 'Unknown Title'),
                        'url': track.get('url', '#'),
                        'source': 'Last.fm'
                    })
                
                return top_tracks
                
    except Exception as e:
        print(f"Error getting top tracks from Last.fm: {e}")
    
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
            timeout=(2, 3),  # Very fast timeout for track info
            headers={'User-Agent': 'BeatSyncMixer/1.0'}
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                return data.get('track', {})
                
    except Exception as e:
        print(f"Error getting track info from Last.fm: {e}")
    
    return None
