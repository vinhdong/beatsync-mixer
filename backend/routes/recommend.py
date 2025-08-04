"""
Recommendation routes for BeatSync Mixer.
Handles Last.fm integration for music recommendations.
"""

from flask import Blueprint, request, jsonify
from backend.models.models import get_db, QueueItem
from backend.api.lastfm import get_similar_tracks


recommend_bp = Blueprint('recommend', __name__)


@recommend_bp.route("/<track_uri>")
def recommend(track_uri):
    """Get Last.fm recommendations for a queued track"""
    try:
        with get_db() as db:
            # Find the track in the queue
            queue_item = db.query(QueueItem).filter_by(track_uri=track_uri).first()
            
            if not queue_item:
                return jsonify({"error": "Track not found in queue"}), 404
            
            # Extract artist and title from track name (basic parsing)
            track_name = queue_item.track_name
            
            # Parse track name format - it appears to be "Title - Artist1, Artist2, etc."
            if " - " in track_name:
                parts = track_name.split(" - ", 1)
                title = parts[0].strip()
                artists_part = parts[1].strip()
                
                # Take the first artist from the list
                if ", " in artists_part:
                    artist = artists_part.split(", ")[0].strip()
                else:
                    artist = artists_part.strip()
            else:
                # Fallback: use track name as title, no artist
                title = track_name.strip()
                artist = "Unknown Artist"
            
            print(f"🎵 Parsed track: Title='{title}', Artist='{artist}' from '{track_name}'")
            
            if not title:
                return jsonify({"error": "Could not parse title from track name"}), 400
            
            # Get Last.fm recommendations using the API module
            recommendations = get_similar_tracks(artist, title, limit=3)
            
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
            
            print(f"✅ Returning {len(recommendations)} recommendations for {artist} - {title}")
            
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
