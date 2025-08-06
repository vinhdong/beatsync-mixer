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
    
    # Check if we're in development mode for faster local testing
    is_development = os.getenv("FLASK_ENV") != "production"
    
    # Optimized: Handle DNS issues on Heroku with IP fallback
    try:
        print(f"🎵 Getting Last.fm recommendations for: '{artist}' - '{title}'")
        print(f"🔑 Using API key: {api_key[:8]}..." if api_key else "❌ No API key")
        
        # Development: Use regular DNS for speed
        if is_development:
            response = requests.get(
                "http://ws.audioscrobbler.com/2.0/",
                params=params,
                timeout=(5, 10),  # Generous timeout for dev
                headers={
                    'User-Agent': 'BeatSyncMixer/1.0',
                    'Accept': 'application/json'
                }
            )
        else:
            # Production: Use manual IP resolution for Last.fm
            # Last.fm server IPs (ws.audioscrobbler.com)
            lastfm_ips = [
                "130.211.19.189",    # Current primary Last.fm API server (verified working)
                "35.186.224.25",     # Google Cloud backup
                "34.102.136.181",    # Google Cloud secondary
                "104.154.127.127"    # Google Cloud tertiary
            ]
            
            response = None
            for i, ip in enumerate(lastfm_ips):
                try:
                    # Replace hostname with IP but keep Host header
                    api_url = f"http://{ip}/2.0/"
                    headers = {
                        'Host': 'ws.audioscrobbler.com',
                        'User-Agent': 'BeatSyncMixer/1.0',
                        'Accept': 'application/json'
                    }
                    
                    print(f"Trying Last.fm IP {i+1}/{len(lastfm_ips)}: {ip}")
                    
                    response = requests.get(
                        api_url,
                        params=params,
                        timeout=(2, 4),  # Fast timeout for production
                        headers=headers,
                        verify=False  # Skip SSL for IP connections
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Success with Last.fm IP {ip}")
                        break
                    else:
                        print(f"❌ Failed with IP {ip}: {response.status_code}")
                        continue
                        
                except Exception as e:
                    print(f"❌ Error with Last.fm IP {ip}: {e}")
                    continue
            
            # If all IPs failed, try regular DNS as last resort
            if not response or response.status_code != 200:
                try:
                    print("🔄 All IPs failed, trying Last.fm DNS as last resort...")
                    response = requests.get(
                        "http://ws.audioscrobbler.com/2.0/",
                        params=params,
                        timeout=(6, 12),  # Longer timeout for DNS fallback
                        headers={
                            'User-Agent': 'BeatSyncMixer/1.0',
                            'Accept': 'application/json'
                        }
                    )
                except Exception as e:
                    print(f"❌ DNS fallback also failed: {e}")
                    return []
        
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
    """Get top tracks for an artist from Last.fm API with DNS fallback"""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return []
    
    is_development = os.getenv("FLASK_ENV") != "production"
    
    params = {
        'method': 'artist.gettoptracks',
        'artist': artist,
        'api_key': api_key,
        'format': 'json',
        'limit': str(limit)
    }
    
    try:
        if is_development:
            response = requests.get(
                "http://ws.audioscrobbler.com/2.0/",
                params=params,
                timeout=(5, 10),
                headers={'User-Agent': 'BeatSyncMixer/1.0'}
            )
        else:
            # Production: Use IP fallback for Last.fm
            lastfm_ips = ["130.211.19.189", "35.186.224.25", "34.102.136.181"]
            response = None
            
            for ip in lastfm_ips:
                try:
                    response = requests.get(
                        f"http://{ip}/2.0/",
                        params=params,
                        timeout=(2, 4),
                        headers={
                            'Host': 'ws.audioscrobbler.com',
                            'User-Agent': 'BeatSyncMixer/1.0'
                        },
                        verify=False
                    )
                    if response.status_code == 200:
                        break
                except:
                    continue
        
        if response and response.status_code == 200:
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
    """Get track information from Last.fm API with DNS fallback"""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return None
    
    is_development = os.getenv("FLASK_ENV") != "production"
    
    params = {
        'method': 'track.getInfo',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json'
    }
    
    try:
        if is_development:
            response = requests.get(
                "http://ws.audioscrobbler.com/2.0/",
                params=params,
                timeout=(5, 8),
                headers={'User-Agent': 'BeatSyncMixer/1.0'}
            )
        else:
            # Production: Use IP fallback for Last.fm
            lastfm_ips = ["130.211.19.189", "35.186.224.25", "34.102.136.181"]
            response = None
            
            for ip in lastfm_ips:
                try:
                    response = requests.get(
                        f"http://{ip}/2.0/",
                        params=params,
                        timeout=(2, 3),
                        headers={
                            'Host': 'ws.audioscrobbler.com',
                            'User-Agent': 'BeatSyncMixer/1.0'
                        },
                        verify=False
                    )
                    if response.status_code == 200:
                        break
                except:
                    continue
        
        if response and response.status_code == 200:
            data = response.json()
            if 'error' not in data:
                return data.get('track', {})
                
    except Exception as e:
        print(f"Error getting track info from Last.fm: {e}")
    
    return None
