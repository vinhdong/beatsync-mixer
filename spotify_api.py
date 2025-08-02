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


# Initialize Spotify OAuth
spotify_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-read-playback-state user-modify-playback-state playlist-read-private user-read-private user-read-email",
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
    """Fetch user profile using optimal method based on environment"""
    
    # In development, use regular spotipy for speed
    if IS_DEVELOPMENT:
        try:
            print("Development mode: Using regular Spotify API for user profile")
            sp = spotipy.Spotify(auth=access_token)
            profile = sp.current_user()
            print("Successfully fetched user profile via regular API")
            return profile
        except Exception as e:
            print(f"Regular API failed: {e}, falling back to manual IP")
    
    # Production or fallback: use manual IP approach
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    for ip in ip_addresses:
        try:
            url = f"https://{ip}/v1/me"
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


def fetch_playlists(access_token, fast_timeout=False):
    """Fetch user playlists using optimal method based on environment"""
    
    # In development, use regular spotipy for speed
    if IS_DEVELOPMENT:
        try:
            print("Development mode: Using regular Spotify API for playlists")
            sp = spotipy.Spotify(auth=access_token)
            data = sp.current_user_playlists(limit=15, offset=0)
            print(f"Successfully fetched {len(data.get('items', []))} playlists via regular API")
            return data
        except Exception as e:
            print(f"Regular API failed: {e}, falling back to manual IP")
    
    # Production: Use manual IP approach with optimized timeouts
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Faster timeouts for production
    timeout_config = (1, 2) if fast_timeout else (2, 3)
    
    print(f"Production: Using manual IP approach with {len(ip_addresses)} IPs (timeout: {timeout_config})")
    
    for i, ip in enumerate(ip_addresses):
        try:
            print(f"Trying IP {i+1}/{len(ip_addresses)}: {ip}")
            url = f"https://{ip}/v1/me/playlists?limit=15&offset=0"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout_config,
                verify=False
            )
            
            print(f"Response from {ip}: Status {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully fetched playlists from {ip}: {len(data.get('items', []))} playlists")
                return data
            elif response.status_code == 401:
                print(f"Authentication failed with {ip} - token may be expired")
                return None
            else:
                print(f"Failed with {ip}: {response.status_code}")
                
        except Exception as e:
            print(f"Error with IP {ip}: {str(e)}")
            continue
    
    # Last resort: try regular DNS (might work sometimes)
    try:
        print("All IPs failed, trying regular DNS as last resort...")
        response = requests.get(
            "https://api.spotify.com/v1/me/playlists?limit=15&offset=0",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            timeout=(1, 2)
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success with regular DNS: {len(data.get('items', []))} playlists")
            return data
            
    except Exception as e:
        print(f"Regular DNS also failed: {e}")
    
    print("All methods failed for playlists fetch")
    return None


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
