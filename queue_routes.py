"""
Queue management routes for BeatSync Mixer.
Handles queue operations, voting, and auto-play functionality.
"""

import time
import threading
from flask import Blueprint, session, request, jsonify
from db import get_db, QueueItem, Vote
from spotify_api import start_playback
from cache import clear_queue_snapshot


queue_bp = Blueprint('queue', __name__)

# Auto-play locking to prevent concurrent requests
auto_play_lock = threading.Lock()
last_auto_play_time = 0


@queue_bp.route("/")
def get_queue():
    """Get current queue items"""
    with get_db() as db:
        items = db.query(QueueItem).order_by(QueueItem.timestamp).all()
        queue_data = [
            {
                "id": item.id,
                "track_uri": item.track_uri,
                "track_name": item.track_name,
                "timestamp": item.timestamp.isoformat() if item.timestamp else None,
            }
            for item in items
        ]
        return jsonify({"queue": queue_data, "count": len(queue_data)})


@queue_bp.route("/clear", methods=["POST"])
def clear_queue():
    """Clear all items from the queue - Host only"""
    if session.get("role") != "host":
        return jsonify({"error": "Only hosts can clear the queue", "required_role": "host", "current_role": session.get("role")}), 403
    
    try:
        with get_db() as db:
            # Count items before deletion for feedback
            item_count = db.query(QueueItem).count()
            
            # Clear queue items
            db.query(QueueItem).delete()
            
            # Also clear votes for queue items
            db.query(Vote).delete()
            
            # Clear queue snapshot cache
            clear_queue_snapshot()
            
            # Broadcast queue clear to all clients
            from flask import current_app
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit("queue_cleared")
                current_app.socketio.emit("votes_cleared")
            
            return jsonify({
                "status": "success", 
                "message": f"Queue cleared successfully. Removed {item_count} items.",
                "items_removed": item_count
            })
    except Exception as e:
        print(f"Error clearing queue: {e}")
        return jsonify({"error": "Database error while clearing queue"}), 500


@queue_bp.route("/next-track")
def get_next_track():
    """Get the next track to play - ALL tracks in queue are eligible regardless of votes"""
    try:
        with get_db() as db:
            # Get all queue items ordered by timestamp (FIFO - first in, first out)
            # But we'll still consider votes for ordering among tracks added around the same time
            queue_items = db.query(QueueItem).order_by(QueueItem.timestamp).all()
            
            if not queue_items:
                return jsonify({"error": "Queue is empty"}), 404
            
            # NEW LOGIC: All tracks are eligible, but votes affect order preference
            # We'll still prioritize higher voted tracks, but never skip any track
            
            best_track = None
            best_score = -999  # Start with very low score
            fallback_track = None  # Always have a fallback (oldest track)
            
            for item in queue_items:
                # Get vote counts for this track
                votes = db.query(Vote).filter_by(track_uri=item.track_uri).all()
                up_votes = len([v for v in votes if v.vote_type == 'up'])
                down_votes = len([v for v in votes if v.vote_type == 'down'])
                
                # Calculate net score (likes - dislikes)
                net_score = up_votes - down_votes
                
                track_data = {
                    "track_uri": item.track_uri,
                    "track_name": item.track_name,
                    "up_votes": up_votes,
                    "down_votes": down_votes,
                    "net_score": net_score
                }
                
                # Set fallback to the first (oldest) track if not set
                if fallback_track is None:
                    fallback_track = track_data
                
                # Find the track with the highest net score, but don't exclude any
                if net_score > best_score:
                    best_score = net_score
                    best_track = track_data
            
            # Return the best voted track, or fallback to oldest if all have same/negative scores
            result_track = best_track if best_track else fallback_track
            
            if result_track:
                print(f"Next track selected: {result_track['track_name']} (Score: {result_track['net_score']}, Up: {result_track['up_votes']}, Down: {result_track['down_votes']})")
                return jsonify(result_track)
            else:
                return jsonify({"error": "No tracks in queue"}), 404
                
    except Exception as e:
        print(f"Error in get_next_track: {e}")
        return jsonify({"error": str(e)}), 500


@queue_bp.route("/auto-play", methods=["POST"])
def auto_play_next():
    """Automatically play the next track based on voting - Host only"""
    global last_auto_play_time
    
    if session.get("role") != "host":
        print("Auto-play denied: User is not host")
        return jsonify({"error": "Host only"}), 403
    
    # Server-side debounce: prevent multiple auto-play requests within 2 seconds
    current_time = time.time()
    with auto_play_lock:
        if current_time - last_auto_play_time < 2:
            print(f"Auto-play request blocked by server debounce (last call: {current_time - last_auto_play_time:.2f}s ago)")
            return jsonify({"error": "Auto-play request too soon"}), 429
        last_auto_play_time = current_time

    print("Auto-play request received from host")
    
    try:
        # Get the next track based on voting
        next_track_response = get_next_track()
        
        if next_track_response.status_code != 200:
            print(f"No next track available: {next_track_response.status_code}")
            return next_track_response
        
        next_track = next_track_response.get_json()
        track_uri = next_track["track_uri"]
        print(f"Next track to play: {next_track['track_name']} ({track_uri})")
        
        # Get access token from the spotify_token object
        token_info = session.get("spotify_token")
        if not token_info:
            print("No spotify_token in session")
            return jsonify({"error": "Not authenticated"}), 401
            
        access_token = token_info.get("access_token")
        if not access_token:
            print("No access_token in spotify_token")
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.json or {}
        device_id = data.get("device_id")
        print(f"Playing on device: {device_id}")
        
        # Play the track using manual IP-based request
        success = start_playback(access_token, device_id, [track_uri])
        if not success:
            print("start_playback failed")
            return jsonify({"error": "Failed to start playback"}), 500
        
        # SUCCESS! Track is now playing - update currently playing cache
        from cache import set_currently_playing
        set_currently_playing(track_uri, next_track['track_name'], is_playing=True, device_id=device_id)
        print(f"Updated currently playing cache: {next_track['track_name']}")
        
        # Broadcast the currently playing track to all clients
        from flask import current_app
        if hasattr(current_app, 'socketio'):
            current_app.socketio.emit('playback_started', {
                'track_uri': track_uri,
                'track_name': next_track['track_name'],
                'device_id': device_id,
                'is_playing': True
            })
            print(f"Broadcasted playback started: {next_track['track_name']}")
        
        # Remove ONLY this specific track from the queue
        print(f"Successfully started playback of {next_track['track_name']}, removing from queue...")
        
        # Remove the track from the queue and its votes with additional safety checks
        try:
            with get_db() as db:
                # Count queue items before removal for debugging
                total_before = db.query(QueueItem).count()
                print(f"Queue count before removal: {total_before}")
                
                # Find and remove ONLY the specific track that was just played
                item = db.query(QueueItem).filter(
                    QueueItem.track_uri == track_uri
                ).first()
                
                if item:
                    track_name = item.track_name  # Store name before deletion
                    track_id = item.id  # Store ID for verification
                    
                    # Double-check this is the track we expect
                    if item.track_uri != track_uri:
                        print(f"ERROR: Track URI mismatch! Expected {track_uri}, got {item.track_uri}")
                        return jsonify({"error": "Track URI mismatch"}), 500
                    
                    # Remove the specific queue item
                    db.delete(item)
                    print(f"Marked '{track_name}' (ID: {track_id}) for deletion from queue")
                    
                    # Also remove associated votes for this specific track
                    votes_to_delete = db.query(Vote).filter(Vote.track_uri == track_uri).all()
                    votes_count = len(votes_to_delete)
                    for vote in votes_to_delete:
                        db.delete(vote)
                    print(f"Marked {votes_count} votes for '{track_name}' for deletion")
                    
                    # Count queue items after removal for debugging
                    total_after = db.query(QueueItem).count()
                    items_removed = total_before - total_after
                    print(f"Queue count after removal: {total_after} (removed {items_removed} items)")
                    
                    if items_removed != 1:
                        print(f"WARNING: Expected to remove 1 item, but removed {items_removed} items!")
                    
                    # Emit removal event to all clients
                    from flask import current_app
                    if hasattr(current_app, 'socketio'):
                        current_app.socketio.emit('track_removed', {
                            'track_uri': track_uri,
                            'track_name': track_name
                        })
                    print(f"Broadcasted track removal: '{track_name}'")
                else:
                    print(f"Warning: Track {track_uri} not found in queue to remove")
                    
        except Exception as db_error:
            print(f"Error removing track from queue: {db_error}")
            raise db_error
        
        print(f"Auto-play complete: {next_track['track_name']} is playing and removed from queue")
        return jsonify({
            "status": "success", 
            "track": next_track,
            "message": f"Now playing: {next_track['track_name']} (Score: {next_track['net_score']})"
        })
        
    except Exception as e:
        print(f"Error in auto_play_next: {e}")
        return jsonify({"error": str(e)}), 500


@queue_bp.route("/remove/<track_uri>", methods=["POST"])
def remove_from_queue(track_uri):
    """Remove a specific track from the queue after it's played"""
    try:
        with get_db() as db:
            # Find and remove the track
            item = db.query(QueueItem).filter_by(track_uri=track_uri).first()
            if item:
                db.delete(item)
                
                # Also remove associated votes
                db.query(Vote).filter_by(track_uri=track_uri).delete()
                
                # Emit removal event to all clients
                from flask import current_app
                if hasattr(current_app, 'socketio'):
                    current_app.socketio.emit('track_removed', {
                        'track_uri': track_uri,
                        'track_name': item.track_name
                    })
                
                return jsonify({"status": "success", "message": "Track removed from queue"})
            else:
                return jsonify({"error": "Track not found in queue"}), 404
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500
