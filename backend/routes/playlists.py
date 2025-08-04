"""
Playlist routes for BeatSync Mixer.
Handles playlist and track fetching with optimized caching.
"""

import time
import threading
from flask import Blueprint, session, jsonify, request
from backend.api.spotify import fetch_playlists, fetch_playlist_tracks
from backend.utils.cache import get_cached_playlists, cache_playlists_async, simplify_playlists_data, get_cached_tracks, set_cached_tracks


playlists_bp = Blueprint('playlists', __name__)


@playlists_bp.route("/")
def playlists():
    """Get user playlists with optimized caching"""
    user_role = session.get("role")
    
    # For hosts: use their own Spotify token and cache in background
    if user_role == "host":
        token_info = session.get("spotify_token")
        if not token_info:
            print("Host has no Spotify token in session")
            return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
        
        access_token = token_info.get("access_token")
        if not access_token:
            print("Host has no access token available")
            return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
            
        # ALWAYS ensure host access token is cached for listeners - CRITICAL
        try:
            from flask import current_app
            cache = getattr(current_app, 'cache', None)
            if cache:
                cache.set("host_access_token", access_token, timeout=1800)
            else:
                print("CRITICAL: No cache instance available")
        except Exception as e:
            print(f"CRITICAL: Failed to cache host access token: {e}")
            
        # Try to serve from cache first (much faster for repeated requests)
        try:
            cached_data = get_cached_playlists()
            if cached_data:
                print(f"Serving host playlists from cache: {len(cached_data.get('items', []))} playlists")
                # Return cached playlists with host metadata
                host_response = {
                    "items": cached_data["items"],
                    "total": cached_data["total"],
                    "is_host": True,
                    "cached": True
                }
                return jsonify(host_response)
        except Exception as e:
            print(f"Error reading from cache: {e}")
            
        try:
            # Fetch playlists with fast timeout for speed
            print(f"Host {session.get('display_name', 'Unknown')} requesting fresh playlists with token: {access_token[:10]}...")
            data = fetch_playlists(access_token, fast_timeout=True)
            
            if not data:
                print("Fast playlists fetch failed - likely network issue")
                return jsonify({"error": "Failed to fetch playlists from Spotify. This could be due to network issues or expired token."}), 500
            
            print(f"Successfully fetched {len(data.get('items', []))} playlists for host")
            
            # Prepare simplified response for host
            simplified_playlists = {
                "items": [
                    {
                        "id": playlist["id"],
                        "name": playlist["name"],
                        "description": playlist.get("description", ""),
                        "tracks": {"total": playlist["tracks"]["total"]},
                        "images": playlist.get("images", [])[:1],
                        "owner": {"display_name": playlist["owner"]["display_name"]}
                    }
                    for playlist in data.get("items", [])
                ],
                "total": data.get("total", 0),
                "is_host": True
            }
            
            # Cache asynchronously - don't block the response
            def cache_playlists_background():
                try:
                    # Add metadata for listeners
                    cached_playlists = simplified_playlists.copy()
                    cached_playlists["host_name"] = session.get("display_name", "Host")
                    cached_playlists["cached_at"] = time.time()
                    
                    # Use our optimized caching function
                    cache_playlists_async(access_token, cached_playlists)
                    
                    print(f"Background: Cached {len(simplified_playlists['items'])} playlists for listeners")
                except Exception as e:
                    print(f"Background: Cache update failed: {e}")
            
            # Start background caching
            threading.Thread(target=cache_playlists_background, daemon=True).start()
            
            # Return immediately to host
            return jsonify(simplified_playlists)
            
        except Exception as e:
            print(f"Error fetching host playlists: {e}")
            return jsonify({"error": "Failed to fetch playlists"}), 500
    
    # For listeners: use optimized caching
    elif user_role == "listener":
        try:
            # Use optimized cache lookup (in-memory first, then Redis)
            cached_data = get_cached_playlists()
            
            if cached_data:
                # Return cached playlists with listener metadata
                listener_response = {
                    "items": cached_data["items"],
                    "total": cached_data["total"],
                    "is_listener": True,
                    "message": f"Viewing {cached_data.get('host_name', 'host')}'s playlists"
                }
                return jsonify(listener_response)
            else:
                # No cached playlists available
                return jsonify({
                    "items": [],
                    "total": 0,
                    "is_listener": True,
                    "message": "No playlists available. Host needs to load their playlists first."
                })
                
        except Exception as e:
            print(f"Error serving playlists to listener: {e}")
            return jsonify({
                "items": [],
                "total": 0,
                "is_listener": True,
                "error": "Failed to load playlists"
            })
    
    # For guests and other roles
    else:
        return jsonify({
            "items": [],
            "total": 0,
            "message": "Please log in to view playlists"
        })


@playlists_bp.route("/<playlist_id>/tracks")
def playlist_tracks(playlist_id):
    """Fetch tracks for a given playlist with caching"""
    user_role = session.get("role")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    
    print(f"Fetching tracks for playlist {playlist_id} (role: {user_role}, limit: {limit}, offset: {offset})")
    
    # Check cache first for both hosts and listeners
    cached_tracks = get_cached_tracks(playlist_id, limit, offset)
    if cached_tracks:
        print(f"Serving tracks from cache for {playlist_id}")
        return jsonify(cached_tracks)
    
    # Determine access token based on role
    access_token = None
    if user_role == "host":
        token_info = session.get("spotify_token")
        if token_info:
            access_token = token_info.get("access_token")
    elif user_role == "listener":
        # Listeners use the host's cached access token
        try:
            from flask import current_app
            cache = getattr(current_app, 'cache', None)
            if cache:
                access_token = cache.get("host_access_token")
                print(f"Listener using cached host token available: {access_token is not None}")
            else:
                print("No cache instance available for listener")
        except Exception as e:
            print(f"Failed to get cached host token: {e}")
    
    if not access_token:
        return jsonify({"error": "Host must be online to view playlist tracks"}), 403
    
    try:
        print(f"Fetching tracks from Spotify API for playlist {playlist_id}")
        data = fetch_playlist_tracks(access_token, playlist_id, limit, offset)
        
        if not data:
            print(f"Failed to fetch tracks for playlist {playlist_id}")
            return jsonify({"error": "Failed to fetch playlist tracks"}), 500
        
        # Simplify tracks data for better performance and caching
        simplified_tracks = {
            "items": [
                {
                    "track": {
                        "id": item["track"]["id"] if item["track"] else None,
                        "name": item["track"]["name"] if item["track"] else "Unknown",
                        "artists": [{"name": artist["name"]} for artist in item["track"]["artists"]] if item["track"] and item["track"]["artists"] else [],
                        "album": item["track"]["album"]["name"] if item["track"] and item["track"]["album"] else "Unknown",
                        "images": item["track"]["album"]["images"][:1] if item["track"] and item["track"]["album"] and item["track"]["album"]["images"] else [],
                        "uri": item["track"]["uri"] if item["track"] else None,
                        "duration_ms": item["track"]["duration_ms"] if item["track"] else 0
                    }
                }
                for item in data.get("items", []) if item.get("track")
            ],
            "total": data.get("total", 0),
            "offset": data.get("offset", offset),
            "limit": data.get("limit", limit),
            "is_listener": user_role == "listener"
        }
        
        # Cache the result for future requests
        set_cached_tracks(playlist_id, simplified_tracks, limit, offset)
        
        return jsonify(simplified_tracks)
        
    except Exception as e:
        print(f"Error fetching playlist tracks: {e}")
        return jsonify({"error": "Failed to fetch playlist tracks"}), 500
