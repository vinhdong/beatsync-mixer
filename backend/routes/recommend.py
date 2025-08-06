"""
Recommendation routes for BeatSync Mixer.
Handles Last.fm integration for music recommendations with caching.
"""

import hashlib
from flask import Blueprint, request, jsonify, current_app
from backend.models.models import get_db, QueueItem
from backend.api.lastfm import get_similar_tracks


recommend_bp = Blueprint('recommend', __name__)


def get_cache_key(artist, title):
    """Generate a cache key for recommendations"""
    # Create a hash of the artist and title for consistent caching
    key_string = f"rec:{artist.lower()}:{title.lower()}"
    return hashlib.md5(key_string.encode()).hexdigest()[:16]


@recommend_bp.route("/<track_uri>")
def recommend(track_uri):
    """Get Last.fm recommendations for a queued track with caching"""
    try:
        with get_db() as db:
            # Find the track in the queue
            queue_item = db.query(QueueItem).filter_by(track_uri=track_uri).first()
            
            if not queue_item:
                return jsonify({"error": "Track not found in queue"}), 404
            
            # Extract artist and title from track name (improved parsing)
            track_name = queue_item.track_name
            
            print(f"🎵 Parsing track: '{track_name}'")
            
            # Try different parsing strategies
            if " - " in track_name:
                # Parse track name format - could be "Artist - Title" or "Title - Artist"
                parts = track_name.split(" - ", 1)
                part1 = parts[0].strip()
                part2 = parts[1].strip()
                
                # If the second part contains multiple artists (has commas), it's likely artists
                if ", " in part2:
                    title = part1
                    artist = part2.split(", ")[0].strip()  # Take first artist
                else:
                    # Default to first part as title, second as artist
                    title = part1
                    artist = part2
            elif " by " in track_name.lower():
                # Handle "Title by Artist" format
                parts = track_name.split(" by ", 1)
                title = parts[0].strip()
                artist = parts[1].strip()
            else:
                # Fallback: use entire track name as title
                title = track_name.strip()
                artist = "Unknown Artist"
            
            print(f"🎵 Parsed track: Title='{title}', Artist='{artist}' from '{track_name}'")
            
            if not title:
                return jsonify({"error": "Could not parse title from track name"}), 400
            
            # Check cache first (30 minute expiration for recommendations)
            cache_key = get_cache_key(artist, title)
            if hasattr(current_app, 'cache'):
                cached_recommendations = current_app.cache.get(cache_key)
                if cached_recommendations:
                    print(f"✅ Returning cached recommendations for {artist} - {title}")
                    return jsonify({
                        "recommendations": cached_recommendations,
                        "track_uri": track_uri,
                        "cached": True
                    })
            
            # Get Last.fm recommendations using the API module
            recommendations = get_similar_tracks(artist, title, limit=3)
            
            # Cache the recommendations for 30 minutes (1800 seconds)
            if hasattr(current_app, 'cache') and recommendations:
                current_app.cache.set(cache_key, recommendations, timeout=1800)
                print(f"💾 Cached recommendations for {artist} - {title}")
            
            if not recommendations:
                return jsonify({
                    "recommendations": [],
                    "message": "No similar tracks found for this song.",
                    "source": "Last.fm",
                    "original_track": {
                        "artist": artist,
                        "title": title,
                        "uri": track_uri
                    }
                })
            
            print(f"✅ Returning {len(recommendations)} fresh recommendations for {artist} - {title}")
            
            return jsonify({
                "recommendations": recommendations,
                "source": "Last.fm",
                "original_track": {
                    "artist": artist,
                    "title": title,
                    "uri": track_uri
                }
            })
            
    except Exception as e:
        print(f"Recommendation API error for {track_uri}: {str(e)}")
        return jsonify({"error": "Failed to get recommendations"}), 500


@recommend_bp.route("/direct")
def recommend_direct():
    """Test endpoint for Last.fm recommendations (accepts artist and title directly)"""
    try:
        artist = request.args.get('artist')
        title = request.args.get('title')
        
        if not artist or not title:
            return jsonify({"error": "Missing artist or title parameter"}), 400
        
        # Get Last.fm recommendations using the API module
        recommendations = get_similar_tracks(artist, title, limit=3)
        
        if not recommendations:
            return jsonify({
                "recommendations": [],
                "message": "No similar tracks found for this song.",
                "source": "Last.fm"
            })
        
        print(f"✅ Returning {len(recommendations)} recommendations for {artist} - {title}")
        
        return jsonify({
            "recommendations": recommendations,
            "source": "Last.fm"
        })
        
    except Exception as e:
        print(f"Direct recommendation API error for {artist} - {title}: {str(e)}")
        return jsonify({"error": "Failed to get recommendations"}), 500
