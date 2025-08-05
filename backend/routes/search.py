"""
Music search routes for BeatSync Mixer.
Handles music search functionality without requiring Spotify user authentication.
"""

from flask import Blueprint, request, jsonify, session
from backend.api.spotify import search_tracks
from backend.models.models import get_db, QueueItem


search_bp = Blueprint('search', __name__)


@search_bp.route("/tracks")
def search_music():
    """Search for tracks using Spotify API"""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)
    
    if not query:
        return jsonify({"error": "Search query is required"}), 400
    
    if limit > 50:  # Limit to prevent abuse
        limit = 50
    
    try:
        # Search using client credentials (no user auth required)
        results = search_tracks(query, limit=limit)
        return jsonify(results)
        
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({"error": "Search failed", "tracks": []}), 500


@search_bp.route("/add-to-queue", methods=["POST"])
def add_to_queue():
    """Add a track to the queue"""
    try:
        data = request.get_json()
        track_uri = data.get('track_uri')
        track_name = data.get('track_name')
        
        print(f"=== ADD TO QUEUE DEBUG ===")
        print(f"Received data: {data}")
        print(f"Track URI: {track_uri}")
        print(f"Track name: {track_name}")
        print(f"Session: {dict(session)}")
        
        if not track_uri or not track_name:
            print("ERROR: Missing track URI or name")
            return jsonify({"error": "Track URI and name are required"}), 400
        
        # Check if this is a playlist track or recommendation that needs to be searched
        if track_uri.startswith('playlist:') or track_uri.startswith('recommendation:'):
            uri_type = 'playlist' if track_uri.startswith('playlist:') else 'recommendation'
            print(f"INFO: {uri_type.title()} track detected, searching Spotify for actual track")
            
            # Extract search query from track_name (format: "Song Title - Artist Name")
            search_query = track_name
            
            # Search for the track using Spotify API
            search_results = search_tracks(search_query, limit=1)
            
            if not search_results.get('tracks') or len(search_results['tracks']) == 0:
                print(f"ERROR: No Spotify tracks found for query: {search_query}")
                return jsonify({"error": f"Could not find '{track_name}' on Spotify"}), 404
            
            # Use the first search result
            spotify_track = search_results['tracks'][0]
            track_uri = spotify_track['uri']
            track_name = f"{spotify_track['name']} - {spotify_track['artist_names']}"
            
            print(f"SUCCESS: Found Spotify track: {track_uri} - {track_name}")
        else:
            print(f"INFO: Regular track (not playlist/recommendation), using as-is")
        
        # Check if track is already in queue
        with get_db() as db:
            existing = db.query(QueueItem).filter_by(track_uri=track_uri).first()
            if existing:
                print(f"ERROR: Track already exists in queue: {existing.track_name}")
                return jsonify({"error": "Track is already in the queue"}), 400
            
            # Add to queue
            queue_item = QueueItem(track_uri=track_uri, track_name=track_name)
            db.add(queue_item)
            print(f"SUCCESS: Added track to database: {track_name}")
            
            # Emit event to all clients
            from backend.websockets.handlers import socketio
            socketio.emit('track_added', {
                'track_uri': track_uri,
                'track_name': track_name,
                'added_by': session.get('username', 'Anonymous')
            })
            print(f"SUCCESS: Emitted track_added event")
            
            return jsonify({
                "message": f"'{track_name}' added to queue",
                "track_uri": track_uri,
                "track_name": track_name
            }), 200
            
    except Exception as e:
        print(f"ERROR in add_to_queue: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to add track to queue"}), 500
