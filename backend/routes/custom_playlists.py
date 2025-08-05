"""
Custom Playlist routes for BeatSync Mixer.
Handles CRUD operations for user-created playlists.
"""

from flask import Blueprint, session, jsonify, request
from sqlalchemy.orm import joinedload
from backend.models import get_db, CustomPlaylist, PlaylistTrack, User
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

custom_playlists_bp = Blueprint('custom_playlists', __name__)


@custom_playlists_bp.route("/", methods=["GET"])
def get_user_playlists():
    """Get all custom playlists for the current user"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        with get_db() as db:
            playlists = db.query(CustomPlaylist).filter(
                CustomPlaylist.user_id == user_id
            ).order_by(CustomPlaylist.created_at.desc()).all()
            
            playlist_data = []
            for playlist in playlists:
                track_count = db.query(PlaylistTrack).filter(
                    PlaylistTrack.playlist_id == playlist.id
                ).count()
                
                playlist_data.append({
                    "id": playlist.id,
                    "name": playlist.name,
                    "description": playlist.description,
                    "track_count": track_count,
                    "created_at": playlist.created_at.isoformat(),
                    "updated_at": playlist.updated_at.isoformat()
                })
        
        return jsonify({"playlists": playlist_data})
    
    except Exception as e:
        logger.error(f"Error getting user playlists: {e}")
        return jsonify({"error": "Failed to load playlists"}), 500


@custom_playlists_bp.route("/", methods=["POST"])
def create_playlist():
    """Create a new custom playlist"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"error": "Playlist name is required"}), 400
        
        with get_db() as db:
            # Check if playlist name already exists for this user
            existing = db.query(CustomPlaylist).filter(
                CustomPlaylist.user_id == user_id,
                CustomPlaylist.name == data["name"]
            ).first()
            
            if existing:
                return jsonify({"error": "Playlist name already exists"}), 400
            
            # Create new playlist
            playlist = CustomPlaylist(
                name=data["name"],
                description=data.get("description", ""),
                user_id=user_id
            )
            
            db.add(playlist)
            db.flush()  # Flush to get the ID before commit
            
            playlist_data = {
                "id": playlist.id,
                "name": playlist.name,
                "description": playlist.description,
                "track_count": 0,
                "created_at": playlist.created_at.isoformat()
            }
        
        return jsonify({
            "message": "Playlist created successfully",
            "playlist": playlist_data
        })
    
    except Exception as e:
        logger.error(f"Error creating playlist: {e}")
        return jsonify({"error": "Failed to create playlist"}), 500


@custom_playlists_bp.route("/<int:playlist_id>", methods=["GET"])
def get_playlist_tracks(playlist_id):
    """Get all tracks in a specific playlist"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        with get_db() as db:
            # Verify playlist belongs to user
            playlist = db.query(CustomPlaylist).filter(
                CustomPlaylist.id == playlist_id,
                CustomPlaylist.user_id == user_id
            ).first()
            
            if not playlist:
                return jsonify({"error": "Playlist not found"}), 404
            
            # Get tracks
            tracks = db.query(PlaylistTrack).filter(
                PlaylistTrack.playlist_id == playlist_id
            ).order_by(PlaylistTrack.position.asc()).all()
            
            track_data = []
            for track in tracks:
                track_data.append({
                    "id": track.id,
                    "track_uri": track.track_uri,
                    "track_name": track.track_name,
                    "track_artist": track.track_artist,
                    "track_album": track.track_album,
                    "track_duration": track.track_duration,
                    "position": track.position,
                    "added_at": track.added_at.isoformat()
                })
            
            playlist_info = {
                "id": playlist.id,
                "name": playlist.name,
                "description": playlist.description,
                "created_at": playlist.created_at.isoformat()
            }
        
        return jsonify({
            "playlist": playlist_info,
            "tracks": track_data
        })
    
    except Exception as e:
        logger.error(f"Error getting playlist tracks: {e}")
        return jsonify({"error": "Failed to load playlist tracks"}), 500


@custom_playlists_bp.route("/<int:playlist_id>/tracks", methods=["POST"])
def add_track_to_playlist(playlist_id):
    """Add a track to a playlist"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.get_json()
        if not data or not data.get("track_uri"):
            return jsonify({"error": "Track URI is required"}), 400
        
        with get_db() as db:
            # Verify playlist belongs to user
            playlist = db.query(CustomPlaylist).filter(
                CustomPlaylist.id == playlist_id,
                CustomPlaylist.user_id == user_id
            ).first()
            
            if not playlist:
                return jsonify({"error": "Playlist not found"}), 404
            
            # Check if track already exists in playlist
            existing_track = db.query(PlaylistTrack).filter(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_uri == data["track_uri"]
            ).first()
            
            if existing_track:
                return jsonify({"error": "Track already in playlist"}), 400
            
            # Get next position
            max_position = db.query(PlaylistTrack.position).filter(
                PlaylistTrack.playlist_id == playlist_id
            ).order_by(PlaylistTrack.position.desc()).first()
            
            next_position = (max_position[0] + 1) if max_position and max_position[0] is not None else 0
            
            # Add track
            track = PlaylistTrack(
                playlist_id=playlist_id,
                track_uri=data["track_uri"],
                track_name=data.get("track_name", "Unknown Track"),
                track_artist=data.get("track_artist", "Unknown Artist"),
                track_album=data.get("track_album", ""),
                track_duration=data.get("track_duration", 0),
                position=next_position
            )
            
            db.add(track)
        
        return jsonify({"message": "Track added to playlist successfully"})
    
    except Exception as e:
        logger.error(f"Error adding track to playlist: {e}")
        return jsonify({"error": "Failed to add track to playlist"}), 500


@custom_playlists_bp.route("/<int:playlist_id>/tracks/<int:track_id>", methods=["DELETE"])
def remove_track_from_playlist(playlist_id, track_id):
    """Remove a track from a playlist"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        with get_db() as db:
            # Verify playlist belongs to user
            playlist = db.query(CustomPlaylist).filter(
                CustomPlaylist.id == playlist_id,
                CustomPlaylist.user_id == user_id
            ).first()
            
            if not playlist:
                return jsonify({"error": "Playlist not found"}), 404
            
            # Find and remove track
            track = db.query(PlaylistTrack).filter(
                PlaylistTrack.id == track_id,
                PlaylistTrack.playlist_id == playlist_id
            ).first()
            
            if not track:
                return jsonify({"error": "Track not found"}), 404
            
            db.delete(track)
        
        return jsonify({"message": "Track removed from playlist successfully"})
    
    except Exception as e:
        logger.error(f"Error removing track from playlist: {e}")
        return jsonify({"error": "Failed to remove track from playlist"}), 500


@custom_playlists_bp.route("/<int:playlist_id>", methods=["PUT"])
def update_playlist(playlist_id):
    """Update playlist name and description"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        with get_db() as db:
            # Verify playlist belongs to user
            playlist = db.query(CustomPlaylist).filter(
                CustomPlaylist.id == playlist_id,
                CustomPlaylist.user_id == user_id
            ).first()
            
            if not playlist:
                return jsonify({"error": "Playlist not found"}), 404
            
            # Update fields
            if "name" in data:
                # Check if new name already exists for this user (excluding current playlist)
                existing = db.query(CustomPlaylist).filter(
                    CustomPlaylist.user_id == user_id,
                    CustomPlaylist.name == data["name"],
                    CustomPlaylist.id != playlist_id
                ).first()
                
                if existing:
                    return jsonify({"error": "Playlist name already exists"}), 400
                
                playlist.name = data["name"]
            
            if "description" in data:
                playlist.description = data["description"]
        
        return jsonify({"message": "Playlist updated successfully"})
    
    except Exception as e:
        logger.error(f"Error updating playlist: {e}")
        return jsonify({"error": "Failed to update playlist"}), 500


@custom_playlists_bp.route("/<int:playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id):
    """Delete a playlist and all its tracks"""
    try:
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Not authenticated"}), 401
        
        with get_db() as db:
            # Verify playlist belongs to user
            playlist = db.query(CustomPlaylist).filter(
                CustomPlaylist.id == playlist_id,
                CustomPlaylist.user_id == user_id
            ).first()
            
            if not playlist:
                return jsonify({"error": "Playlist not found"}), 404
            
            # Delete all tracks first
            db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist_id).delete()
            
            # Delete playlist
            db.delete(playlist)
        
        return jsonify({"message": "Playlist deleted successfully"})
    
    except Exception as e:
        logger.error(f"Error deleting playlist: {e}")
        return jsonify({"error": "Failed to delete playlist"}), 500
