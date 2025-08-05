"""
Spotify API integration with manual IP fallback for Heroku DNS issues.
Handles authentication, playlists, tracks, and playback control.
"""

import os
import time
import requests
from spotipy.oauth2 import SpotifyOAuth
import spotipy


# Check if we're in development mode
IS_DEVELOPMENT = os.getenv("FLASK_ENV") != "production"


def make_spotify_api_request(endpoint, access_token, method='GET', data=None, params=None, timeout_config=(2, 4)):
    """
    Centralized function for making Spotify API requests with DNS fallback.
    Updated with more robust error handling and better IP addresses.
    """
    if not access_token:
        print("❌ No access token provided")
        return None
    
    # Base URL for Spotify API
    base_url = "https://api.spotify.com/v1"
    full_url = f"{base_url}/{endpoint.lstrip('/')}"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'User-Agent': 'BeatSyncMixer/1.0'
    }
    
    # Development mode: use regular API for speed
    if IS_DEVELOPMENT:
        try:
            print(f"Development: Making {method} request to {endpoint}")
            response = requests.request(
                method=method,
                url=full_url,
                headers=headers,
                json=data if method != 'GET' else None,
                params=params,
                timeout=(5, 10)  # Generous timeout for dev
            )
            
            if response.status_code in [200, 201, 204]:
                return response.json() if response.content else {}
            elif response.status_code == 401:
                print("❌ Unauthorized - token expired")
                return None
            else:
                print(f"❌ Request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Development API request failed: {e}")
            return None
    
    # Production: Use manual IP resolution with updated server IPs
    updated_ips = [
        "35.186.224.24",     # Google Cloud
        "104.154.127.126",   # Google Cloud  
        "34.102.136.180",    # Google Cloud
        "35.232.142.147",    # Additional Google Cloud
        "34.118.98.43",      # Additional Google Cloud
        "35.227.23.12"       # Additional Google Cloud
    ]
    
    print(f"Production: Trying {len(updated_ips)} IP addresses for {endpoint}")
    
    for i, ip in enumerate(updated_ips):
        try:
            # Replace hostname with IP but keep Host header
            ip_url = full_url.replace("api.spotify.com", ip)
            ip_headers = headers.copy()
            ip_headers['Host'] = 'api.spotify.com'
            
            print(f"Attempt {i+1}/{len(updated_ips)}: {ip}")
            
            response = requests.request(
                method=method,
                url=ip_url,
                headers=ip_headers,
                json=data if method != 'GET' else None,
                params=params,
                timeout=timeout_config,
                verify=False  # Skip SSL verification for IP connections
            )
            
            if response.status_code in [200, 201, 204]:
                result = response.json() if response.content else {}
                print(f"✅ Success with IP {ip}")
                return result
            elif response.status_code == 401:
                print(f"❌ Unauthorized with IP {ip} - token expired")
                return None
            elif response.status_code == 429:
                print(f"⚠️ Rate limited with IP {ip}")
                time.sleep(1)  # Brief pause for rate limiting
                continue
            else:
                print(f"❌ Failed with IP {ip}: {response.status_code}")
                continue
                
        except Exception as e:
            print(f"❌ Error with IP {ip}: {e}")
            continue
    
    # Final fallback: try regular DNS (rarely works on Heroku but worth trying)
    try:
        print("🔄 All IPs failed, trying regular DNS as last resort...")
        response = requests.request(
            method=method,
            url=full_url,
            headers=headers,
            json=data if method != 'GET' else None,
            params=params,
            timeout=(6, 12)  # Longer timeout for DNS fallback
        )
        
        if response.status_code in [200, 201, 204]:
            result = response.json() if response.content else {}
            print("✅ Success with regular DNS")
            return result
        else:
            print(f"❌ DNS fallback failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ DNS fallback error: {e}")
        return None





# Initialize Spotify OAuth
spotify_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-read-playback-state user-modify-playback-state playlist-read-private user-read-private user-read-email streaming",
    cache_path=None  # Disable file caching
)


def create_spotify_client(access_token):
    """Create a Spotify client with the given access token for development"""
    if IS_DEVELOPMENT:
        return spotipy.Spotify(auth=access_token)
    return None


def exchange_token(auth_code):
    """Exchange authorization code for access token using optimal method"""
    
    # In development, use regular spotipy OAuth for speed
    if IS_DEVELOPMENT:
        try:
            print("Development mode: Using regular OAuth for token exchange")
            token_info = spotify_oauth.get_access_token(auth_code)
            if token_info:
                print("Successfully exchanged token via regular OAuth")
                return token_info
        except Exception as e:
            print(f"Regular OAuth failed: {e}, falling back to manual IP")
    
    # Production: Use manual IP approach with optimized timeouts
    token_data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': os.getenv("SPOTIFY_REDIRECT_URI"),
        'client_id': os.getenv("SPOTIFY_CLIENT_ID"),
        'client_secret': os.getenv("SPOTIFY_CLIENT_SECRET")
    }
    
    # Manual IP approach first for production
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    for ip in ip_addresses:
        try:
            print(f"Trying token exchange with IP: {ip}")
            url = f"https://{ip}/api/token"
            headers = {
                'Host': 'accounts.spotify.com',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                url,
                data=token_data,
                headers=headers,
                timeout=(2, 3),
                verify=False
            )
            
            if response.status_code == 200:
                token_info = response.json()
                token_info['expires_at'] = int(time.time()) + token_info.get('expires_in', 3600)
                print(f"Successfully exchanged token via IP {ip}")
                return token_info
                
        except Exception as e:
            print(f"IP {ip} failed: {e}")
            continue
    
    # Last resort: try regular DNS
    try:
        print("All IPs failed, trying regular DNS for token exchange...")
        response = requests.post(
            "https://accounts.spotify.com/api/token",
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=(2, 3)
        )
        
        if response.status_code == 200:
            token_info = response.json()
            token_info['expires_at'] = int(time.time()) + token_info.get('expires_in', 3600)
            print("Successfully exchanged token via regular DNS")
            return token_info
            
    except Exception as e:
        print(f"Regular DNS also failed: {e}")
    
    print("All token exchange methods failed")
    return None


def refresh_token(refresh_token):
    """Refresh access token using manual IP fallback"""
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': os.getenv("SPOTIFY_CLIENT_ID"),
        'client_secret': os.getenv("SPOTIFY_CLIENT_SECRET")
    }
    
    for ip in ip_addresses:
        try:
            url = f"https://{ip}/api/token"
            headers = {
                'Host': 'accounts.spotify.com',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            req_session = requests.Session()
            
            response = req_session.post(
                url,
                data=token_data,
                headers=headers,
                timeout=(3, 3),
                verify=False
            )
            
            if response.status_code == 200:
                token_info = response.json()
                token_info['expires_at'] = int(time.time()) + token_info.get('expires_in', 3600)
                return token_info
                
        except Exception as e:
            continue
    
    return None


def fetch_user_profile(access_token):
    """Fetch user profile using centralized API request function"""
    print("🔍 Fetching user profile...")
    return make_spotify_api_request("me", access_token, timeout_config=(3, 6))


def fetch_playlists(access_token, fast_timeout=False):
    """Fetch user playlists using centralized API request function"""
    print("🎵 Fetching user playlists...")
    
    # Set timeout based on fast_timeout parameter
    timeout_config = (1, 2) if fast_timeout else (3, 6)
    
    # Use the centralized function with proper parameters
    params = {'limit': 15, 'offset': 0}
    return make_spotify_api_request("me/playlists", access_token, params=params, timeout_config=timeout_config)


def get_playback_state(access_token):
    """Get current playback state using centralized API request function"""
    print("🎵 Getting playback state...")
    return make_spotify_api_request("me/player", access_token, timeout_config=(2, 4))


def fetch_playlist_tracks(access_token, playlist_id, limit=50, offset=0):
    """Fetch playlist tracks using optimal method based on environment"""
    
    # In development, use regular spotipy for speed
    if IS_DEVELOPMENT:
        try:
            print(f"Development mode: Using regular Spotify API for playlist {playlist_id} tracks")
            sp = spotipy.Spotify(auth=access_token)
            data = sp.playlist_tracks(
                playlist_id, 
                limit=limit, 
                offset=offset,
                fields="items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit"
            )
            print(f"Successfully fetched {len(data.get('items', []))} tracks via regular API")
            return data
        except Exception as e:
            print(f"Regular API failed: {e}, falling back to manual IP")
    
    # Production: Use manual IP approach with optimized timeouts
    print(f"Fetching tracks for playlist {playlist_id}")
    
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    for i, ip in enumerate(ip_addresses):
        try:
            print(f"Trying IP {i+1}/{len(ip_addresses)}: {ip}")
            
            url = f"https://{ip}/v1/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}&fields=items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                url,
                headers=headers,
                timeout=(1, 2),
                verify=False
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully fetched {len(data.get('items', []))} tracks from {ip}")
                return data
            elif response.status_code == 401:
                print(f"Authentication failed (401) - token may be expired")
                return None
            elif response.status_code == 404:
                print(f"Playlist not found (404) - playlist_id may be invalid")
                return None
                
        except Exception as e:
            print(f"Error with IP {ip}: {e}")
            continue
    
    # Last resort: try regular DNS
    try:
        print("All IPs failed, trying regular DNS as last resort...")
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}&fields=items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit"
        
        response = requests.get(
            url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            timeout=(1, 2)
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success with regular DNS: {len(data.get('items', []))} tracks")
            return data
            
    except Exception as e:
        print(f"Regular DNS also failed: {e}")
    
    print("All methods failed for tracks fetch")
    return None
    
    # Fallback: try with regular DNS/hostname as last resort
    try:
        print("Trying fallback with regular DNS...")
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}&fields=items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=(3, 3))
        
        if response.status_code == 200:
            data = response.json()
            print(f"Successfully fetched {len(data.get('items', []))} tracks via DNS fallback")
            return data
        elif response.status_code == 401:
            print(f"Authentication failed (401) via DNS fallback")
            return None
        elif response.status_code == 404:
            print(f"Playlist not found (404) via DNS fallback")
            return None
            
    except Exception as e:
        print(f"DNS fallback also failed: {e}")
    
    print("All methods failed for playlist tracks fetch")
    return None


def start_playback(access_token, device_id=None, uris=None):
    """Start playback using manual IP fallback"""
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    data = {}
    if uris:
        data['uris'] = uris
    
    for ip in ip_addresses:
        try:
            url = f"https://{ip}/v1/me/player/play"
            if device_id:
                url += f"?device_id={device_id}"
                
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.put(
                url,
                json=data,
                headers=headers,
                timeout=(3, 3),
                verify=False
            )
            
            if response.status_code in [200, 204]:
                return True
                
        except Exception as e:
            continue
    
    return False


def pause_playback(access_token, device_id=None):
    """Pause playback using manual IP fallback"""
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    for ip in ip_addresses:
        try:
            url = f"https://{ip}/v1/me/player/pause"
            if device_id:
                url += f"?device_id={device_id}"
                
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.put(
                url,
                headers=headers,
                timeout=(3, 3),
                verify=False
            )
            
            if response.status_code in [200, 204]:
                return True
                
        except Exception as e:
            continue
    
    return False


def get_devices(access_token):
    """Get available devices using manual IP fallback"""
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    for ip in ip_addresses:
        try:
            url = f"https://{ip}/v1/me/player/devices"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                headers=headers,
                timeout=(3, 3),
                verify=False
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            continue
    
    return None


def get_playback_state(access_token):
    """Get current playback state using manual IP fallback"""
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    for ip in ip_addresses:
        try:
            url = f"https://{ip}/v1/me/player"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                headers=headers,
                timeout=(3, 3),
                verify=False
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                return {"is_playing": False, "device": None}
                
        except Exception as e:
            continue
    
    return None


def get_track_info(access_token, track_id):
    """Get track info using manual IP fallback"""
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    for ip in ip_addresses:
        try:
            url = f"https://{ip}/v1/tracks/{track_id}"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                headers=headers,
                timeout=(3, 3),
                verify=False
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            continue
    
    return None


def search_tracks(query, access_token=None, limit=20):
    """
    Search for tracks using Spotify Web API without requiring user authentication.
    Uses client credentials flow or provided access token.
    """
    try:
        if access_token:
            # Use provided access token
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
        else:
            # Get client credentials token (doesn't require user login)
            client_id = os.getenv("SPOTIFY_CLIENT_ID")
            client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
            
            if not client_id or not client_secret:
                print("Missing Spotify client credentials")
                return {"tracks": [], "error": "Spotify credentials not configured"}
            
            # Get client credentials token
            auth_url = "https://accounts.spotify.com/api/token"
            auth_data = {
                "grant_type": "client_credentials"
            }
            auth_headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            auth_response = requests.post(
                auth_url, 
                data=auth_data, 
                headers=auth_headers,
                auth=(client_id, client_secret),
                timeout=10
            )
            
            if auth_response.status_code != 200:
                print(f"Failed to get client credentials token: {auth_response.status_code}")
                return {"tracks": [], "error": "Failed to authenticate with Spotify"}
            
            token_data = auth_response.json()
            access_token = token_data.get("access_token")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
        
        # Search for tracks
        search_url = "https://api.spotify.com/v1/search"
        params = {
            'q': query,
            'type': 'track',
            'limit': limit,
            'market': 'US'  # You can make this configurable
        }
        
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"Search request failed: {response.status_code}")
            return {"tracks": [], "error": "Search request failed"}
        
        data = response.json()
        tracks = data.get('tracks', {}).get('items', [])
        
        # Format tracks for frontend
        formatted_tracks = []
        for track in tracks:
            formatted_track = {
                'id': track['id'],
                'uri': track['uri'],
                'name': track['name'],
                'artists': [artist['name'] for artist in track['artists']],
                'artist_names': ', '.join([artist['name'] for artist in track['artists']]),
                'album': track['album']['name'],
                'duration_ms': track['duration_ms'],
                'duration_text': format_duration(track['duration_ms']),
                'preview_url': track.get('preview_url'),
                'external_url': track['external_urls'].get('spotify'),
                'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None
            }
            formatted_tracks.append(formatted_track)
        
        return {
            "tracks": formatted_tracks,
            "total": data.get('tracks', {}).get('total', 0),
            "query": query
        }
        
    except Exception as e:
        print(f"Error searching tracks: {e}")
        return {"tracks": [], "error": str(e)}


def format_duration(duration_ms):
    """Format duration from milliseconds to MM:SS format"""
    if not duration_ms:
        return "0:00"
    
    total_seconds = duration_ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"



