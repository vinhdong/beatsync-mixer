"""
Caching helpers for BeatSync Mixer.
Handles playlist and track caching with in-memory and Redis storage.
"""

import time
import json
import threading


# In-memory cache for ultra-fast access (per-dyno)
in_memory_cache = {
    'playlists': None,
    'playlists_timestamp': 0
}


def get_in_memory_cache():
    """Get the in-memory cache dictionary"""
    return in_memory_cache


def set_in_memory_cache(key, value):
    """Set a value in the in-memory cache"""
    in_memory_cache[key] = value


def clear_in_memory_cache():
    """Clear all in-memory cache"""
    global in_memory_cache
    in_memory_cache = {
        'playlists': None,
        'playlists_timestamp': 0
    }


def get_cached_playlists():
    """Get playlists from cache (in-memory first, then Redis)"""
    from flask import current_app
    
    # Try in-memory cache first (fastest)
    if in_memory_cache.get('playlists') and in_memory_cache.get('playlists_timestamp'):
        # Check if cache is still fresh (5 minutes)
        if time.time() - in_memory_cache['playlists_timestamp'] < 300:
            print("Serving playlists from in-memory cache")
            return in_memory_cache['playlists']
    
    # Try Redis cache
    try:
        # Get cache instance from app context
        cache = getattr(current_app, 'cache', None)
        if not cache:
            print("No cache instance available")
            return None
            
        cached_data = cache.get("simplified_playlists")
        if cached_data:
            # Parse JSON if it's a string
            if isinstance(cached_data, str):
                cached_data = json.loads(cached_data)
            
            print("Serving playlists from Redis cache")
            
            # Update in-memory cache for next request
            in_memory_cache['playlists'] = cached_data
            in_memory_cache['playlists_timestamp'] = time.time()
            
            return cached_data
    except Exception as e:
        print(f"Redis cache read failed: {e}")
    
    print("No cached playlists available")
    return None


def invalidate_playlist_cache():
    """Clear playlist caches from both in-memory and Redis"""
    from flask import current_app
    
    # Clear in-memory cache
    clear_in_memory_cache()
    
    # Clear Redis cache
    try:
        cache = getattr(current_app, 'cache', None)
        if cache:
            cache.delete("simplified_playlists")
            cache.delete("host_access_token")
            print("Cleared playlist caches from both in-memory and Redis")
        else:
            print("No cache instance available for invalidation")
    except Exception as e:
        print(f"Failed to clear Redis cache: {e}")


def simplify_playlists_data(spotify_data):
    """Convert full Spotify playlists API response to simplified format for caching"""
    if not spotify_data or 'items' not in spotify_data:
        return None
    
    try:
        simplified = {
            "items": [
                {
                    "id": playlist["id"],
                    "name": playlist["name"],
                    "description": playlist.get("description", ""),
                    "tracks": {"total": playlist["tracks"]["total"]},
                    "images": playlist.get("images", [])[:1],  # Only keep first image
                    "owner": {"display_name": playlist["owner"]["display_name"]}
                }
                for playlist in spotify_data.get("items", [])
            ],
            "total": spotify_data.get("total", 0)
        }
        return simplified
    except Exception as e:
        print(f"Error simplifying playlists data: {e}")
        return None


def cache_playlists_async(access_token, simplified_playlists):
    """Cache playlists data in both in-memory and Redis (async)"""
    from flask import current_app
    
    try:
        # Update in-memory cache immediately
        in_memory_cache['playlists'] = simplified_playlists
        in_memory_cache['playlists_timestamp'] = time.time()
        print("Updated in-memory playlists cache")
        
        # Update Redis cache (serialize to JSON)
        cache = getattr(current_app, 'cache', None)
        if cache:
            cache.set("simplified_playlists", json.dumps(simplified_playlists), timeout=1800)  # 30 minutes
            cache.set("host_access_token", access_token, timeout=1800)  # 30 minutes
            print("Updated Redis playlists cache")
        else:
            print("No cache instance available for caching")
        
    except Exception as e:
        print(f"Failed to cache playlists: {e}")


def get_cached_tracks(playlist_id, limit=50, offset=0):
    """Get tracks from in-memory cache first, then Redis if needed"""
    from flask import current_app
    
    cache_key = f"{playlist_id}:{limit}:{offset}"
    
    # Try in-memory cache first (fastest)
    if cache_key in in_memory_cache.get('playlist_tracks', {}):
        timestamp = in_memory_cache.get('playlist_tracks_timestamps', {}).get(cache_key)
        if timestamp and (time.time() - timestamp) < 60:  # 60 second TTL for tracks
            print(f"Serving tracks from in-memory cache for {cache_key}")
            return in_memory_cache['playlist_tracks'][cache_key]
    
    # Try Redis cache
    try:
        cache = getattr(current_app, 'cache', None)
        if cache:
            redis_key = f"playlist_tracks:{cache_key}"
            cached_data = cache.get(redis_key)
            if cached_data:
                print(f"Serving tracks from Redis cache for {cache_key}")
                # Update in-memory cache to avoid Redis on next request
                set_cached_tracks(playlist_id, cached_data, limit, offset)
                return cached_data
    except Exception as e:
        print(f"Redis tracks cache read failed: {e}")
    
    print(f"No cached tracks available for {cache_key}")
    return None


def set_cached_tracks(playlist_id, tracks_data, limit=50, offset=0):
    """Set tracks in both in-memory and Redis cache"""
    from flask import current_app
    
    cache_key = f"{playlist_id}:{limit}:{offset}"
    
    # Update in-memory cache
    if 'playlist_tracks' not in in_memory_cache:
        in_memory_cache['playlist_tracks'] = {}
    if 'playlist_tracks_timestamps' not in in_memory_cache:
        in_memory_cache['playlist_tracks_timestamps'] = {}
        
    in_memory_cache['playlist_tracks'][cache_key] = tracks_data
    in_memory_cache['playlist_tracks_timestamps'][cache_key] = time.time()
    print(f"Updated in-memory tracks cache for {cache_key}")
    
    # Update Redis cache asynchronously
    def cache_tracks_async():
        try:
            cache = getattr(current_app, 'cache', None)
            if cache:
                redis_key = f"playlist_tracks:{cache_key}"
                cache.set(redis_key, tracks_data, timeout=300)  # 5 minutes TTL
                print(f"Updated Redis tracks cache for {cache_key}")
            else:
                print("No cache instance available for track caching")
        except Exception as e:
            print(f"Failed to cache tracks in Redis: {e}")
    
    threading.Thread(target=cache_tracks_async, daemon=True).start()


def get_currently_playing(app=None):
    """Get currently playing track from cache"""
    try:
        if app:
            cache = app.cache
        else:
            from flask import current_app
            cache = getattr(current_app, 'cache', None)
        
        if cache:
            cached_data = cache.get("currently_playing")
            if cached_data:
                if isinstance(cached_data, str):
                    cached_data = json.loads(cached_data)
                return cached_data
    except Exception as e:
        print(f"Failed to get currently playing from cache: {e}")
    
    return None


def set_currently_playing(track_uri, track_name, is_playing=True, device_id=None, app=None):
    """Set currently playing track in cache"""
    data = {
        'track_uri': track_uri,
        'track_name': track_name,
        'is_playing': is_playing,
        'device_id': device_id,
        'timestamp': time.time()
    }
    
    try:
        if app:
            cache = app.cache
        else:
            from flask import current_app
            cache = getattr(current_app, 'cache', None)
        
        if cache:
            cache.set("currently_playing", json.dumps(data), timeout=3600)  # 1 hour
            print(f"Cached currently playing: {track_name} (playing: {is_playing})")
            return True
    except Exception as e:
        print(f"Failed to cache currently playing: {e}")
    
    return False


def clear_currently_playing(app=None):
    """Clear currently playing track from cache"""
    try:
        if app:
            cache = app.cache
        else:
            from flask import current_app
            cache = getattr(current_app, 'cache', None)
        
        if cache:
            cache.delete("currently_playing")
            print("Cleared currently playing from cache")
            return True
    except Exception as e:
        print(f"Failed to clear currently playing from cache: {e}")
    
    return False


def get_queue_snapshot(app=None):
    """Get a snapshot of the current queue from cache"""
    try:
        if app:
            cache = app.cache
        else:
            from flask import current_app
            cache = getattr(current_app, 'cache', None)
        
        if cache:
            cached_data = cache.get("queue_snapshot")
            if cached_data:
                if isinstance(cached_data, str):
                    cached_data = json.loads(cached_data)
                return cached_data
    except Exception as e:
        print(f"Failed to get queue snapshot from cache: {e}")
    
    return []


def update_queue_snapshot(app=None):
    """Update the queue snapshot in cache from database"""
    from db import get_db, QueueItem, Vote
    
    try:
        with get_db() as db:
            # Get all queue items with their vote counts
            items = db.query(QueueItem).order_by(QueueItem.timestamp).all()
            queue_data = []
            
            for item in items:
                # Get vote counts for this track
                up_votes = db.query(Vote).filter(Vote.track_uri == item.track_uri, Vote.vote_type == "up").count()
                down_votes = db.query(Vote).filter(Vote.track_uri == item.track_uri, Vote.vote_type == "down").count()
                
                queue_data.append({
                    'track_uri': item.track_uri,
                    'track_name': item.track_name,
                    'timestamp': item.timestamp.isoformat() if item.timestamp else None,
                    'up_votes': up_votes,
                    'down_votes': down_votes
                })
            
            # Cache the queue snapshot
            if app:
                cache = app.cache
            else:
                from flask import current_app
                cache = getattr(current_app, 'cache', None)
            
            if cache:
                cache.set("queue_snapshot", json.dumps(queue_data), timeout=3600)  # 1 hour
                print(f"Updated queue snapshot with {len(queue_data)} items")
                return queue_data
    except Exception as e:
        print(f"Failed to update queue snapshot: {e}")
    
    return []


def clear_queue_snapshot(app=None):
    """Clear queue snapshot from cache"""
    try:
        if app:
            cache = app.cache
        else:
            from flask import current_app
            cache = getattr(current_app, 'cache', None)
        
        if cache:
            cache.delete("queue_snapshot")
            print("Cleared queue snapshot from cache")
            return True
    except Exception as e:
        print(f"Failed to clear queue snapshot from cache: {e}")
    
    return False
