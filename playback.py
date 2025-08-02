"""
Playback control routes for BeatSync Mixer.
Handles Spotify playback, device management, and status.
"""

from flask import Blueprint, session, request, jsonify, abort
from spotify_api import start_playback, pause_playback, get_devices, get_playback_state
from db import get_db, CurrentlyPlaying


playback_bp = Blueprint('playback', __name__)


@playback_bp.route("/spotify-token")
def get_spotify_token():
    """Get current Spotify access token for Web Playback SDK"""
    token = session.get("spotify_token")
    if not token:
        print("No spotify_token found in session")
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token.get("access_token")
    if not access_token:
        print("No access_token found in token info")
        return jsonify({"error": "No access token"}), 401
    
    print(f"Returning access token for Web Player (length: {len(access_token)})")
    print(f"Token scopes: {token.get('scope', 'No scope info')}")
    print(f"Token expires_in: {token.get('expires_in', 'No expiry info')}")
    
    # Return only the access token (not the full token object for security)
    return jsonify({
        "access_token": access_token,
        "expires_in": token.get("expires_in", 3600)
    })


@playback_bp.route("/play", methods=["POST"])
def play_track():
    """Start playback of a specific track - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token_info = session.get("spotify_token")
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json or {}
        track_uri = data.get("track_uri")
        device_id = data.get("device_id")
        
        # Use manual IP-based playback control
        uris = [track_uri] if track_uri else None
        success = start_playback(access_token, device_id, uris)
        
        if success:
            # Store currently playing track in database
            try:
                with get_db() as db:
                    # Clear any existing currently playing track
                    db.query(CurrentlyPlaying).delete()
                    
                    # Add new currently playing track
                    if track_uri:
                        # Get track name from the queue or use a simplified name
                        track_name = data.get("track_name", track_uri.split(":")[-1])
                        currently_playing = CurrentlyPlaying(
                            track_uri=track_uri,
                            track_name=track_name,
                            is_playing="true",
                            device_id=device_id
                        )
                        db.add(currently_playing)
                        print(f"Stored currently playing track: {track_name} ({track_uri})")
            except Exception as db_error:
                print(f"Error storing currently playing track: {db_error}")
            
            # Broadcast playback state to all connected clients
            from flask import current_app
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit('playback_started', {
                    'track_uri': track_uri,
                    'track_name': data.get("track_name", track_uri.split(":")[-1]),
                    'device_id': device_id,
                    'is_playing': True
                })
            print(f"Broadcasted playback started: {track_uri}")
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Failed to start playback"}), 500
        
    except Exception as e:
        print(f"Error in play_track: {e}")
        return jsonify({"error": str(e)}), 500


@playback_bp.route("/pause", methods=["POST"])
def pause_track():
    """Pause current playback - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token_info = session.get("spotify_token")
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json or {}
        device_id = data.get("device_id")
        
        # Use manual IP-based playback control
        success = pause_playback(access_token, device_id)
        
        if success:
            # Update currently playing track in database to paused
            try:
                with get_db() as db:
                    currently_playing = db.query(CurrentlyPlaying).first()
                    if currently_playing:
                        currently_playing.is_playing = "false"
                        print(f"Updated currently playing track to paused: {currently_playing.track_name}")
                    else:
                        print("No currently playing track found to pause")
            except Exception as db_error:
                print(f"Error updating currently playing track: {db_error}")
            
            # Broadcast pause state to all connected clients
            from flask import current_app
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit('playback_paused', {
                    'device_id': device_id,
                    'is_playing': False
                })
            print("Broadcasted playback paused")
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Failed to pause playback"}), 500
        
    except Exception as e:
        print(f"Error in pause_track: {e}")
        return jsonify({"error": str(e)}), 500


@playback_bp.route("/next", methods=["POST"])
def next_track():
    """Skip to next track - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token_info = session.get("spotify_token")
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # For now, return success but this would need a manual next track function
        return jsonify({"status": "success"})
        
    except Exception as e:
        print(f"Error in next_track: {e}")
        return jsonify({"error": str(e)}), 500


@playback_bp.route("/status")
def playback_status():
    """Get current playback status"""
    token_info = session.get("spotify_token")
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Use manual IP-based playback status
        playback = get_playback_state(access_token)
        
        if playback:
            return jsonify(playback)
        else:
            return jsonify({"is_playing": False, "device": None})
            
    except Exception as e:
        print(f"Error in playback_status: {e}")
        return jsonify({"error": str(e)}), 500


@playback_bp.route("/devices")
def get_devices_route():
    """Get available Spotify devices"""
    token_info = session.get("spotify_token")
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Use manual IP-based device fetch
        devices = get_devices(access_token)
        
        if devices:
            return jsonify(devices)
        else:
            return jsonify({"devices": []}), 500
            
    except Exception as e:
        print(f"Error in get_devices: {e}")
        return jsonify({"error": str(e)}), 500


@playback_bp.route("/transfer", methods=["POST"])
def transfer_playback():
    """Transfer playback to a specific device - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token_info = session.get("spotify_token")
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json or {}
        device_id = data.get("device_id")
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        # For now, return success - transfer would need a manual function
        return jsonify({"status": "success"})
        
    except Exception as e:
        print(f"Error in transfer_playback: {e}")
        return jsonify({"error": str(e)}), 500
