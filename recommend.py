"""
Recommendation routes for BeatSync Mixer.
Handles Last.fm integration for music recommendations.
"""

import os
import requests
from flask import Blueprint, request, jsonify
from db import get_db, QueueItem


recommend_bp = Blueprint('recommend', __name__)


def manual_lastfm_get_similar(artist, title, api_key, limit=5):
    """Manual Last.fm API call using hardcoded IPs as DNS fallback"""
    ip_addresses = ["130.211.19.189"]
    
    params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': str(limit)
    }
    
    for ip in ip_addresses:
        try:
            url = f"http://{ip}/2.0/"
            headers = {
                'Host': 'ws.audioscrobbler.com',
                'User-Agent': 'BeatSyncMixer/1.0'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                params=params,
                headers=headers,
                timeout=(5, 10)
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'error' in data:
                    print(f"Last.fm API error: {data.get('message', 'Unknown error')}")
                    return None
                
                similar_tracks = []
                tracks = data.get('similartracks', {}).get('track', [])
                
                if isinstance(tracks, dict):
                    tracks = [tracks]
                
                for track in tracks[:limit]:
                    similar_tracks.append({
                        'artist': track.get('artist', {}).get('name', 'Unknown Artist'),
                        'title': track.get('name', 'Unknown Title'),
                        'url': track.get('url', '#')
                    })
                
                return similar_tracks
                
        except Exception as e:
            print(f"Manual Last.fm API call failed for IP {ip}: {e}")
            continue
    
    return None


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
            
            # Try to parse "Artist - Title" format
            if " - " in track_name:
                parts = track_name.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            else:
                # Fallback: use track name as title, no artist
                artist = ""
                title = track_name.strip()
            
            if not artist or not title:
                return jsonify({"error": "Could not parse artist and title from track name"}), 400
            
            # Get Last.fm recommendations using manual IP-based client
            api_key = os.getenv("LASTFM_API_KEY")
            if not api_key:
                return jsonify({"error": "Last.fm API key not configured"}), 500
            
            recommendations = manual_lastfm_get_similar(artist, title, api_key, limit=5)
            
            if recommendations is None:
                return jsonify({"error": "Failed to get recommendations from Last.fm"}), 500
            
            print(f"Got {len(recommendations)} recommendations for {artist} - {title}")
            
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


@recommend_bp.route("-direct")
def recommend_direct():
    """Test endpoint for Last.fm recommendations (accepts artist and title directly)"""
    try:
        artist = request.args.get('artist')
        title = request.args.get('title')
        
        if not artist or not title:
            return jsonify({"error": "Missing artist or title parameter"}), 400
        
        # Get Last.fm recommendations using manual IP-based client
        api_key = os.getenv("LASTFM_API_KEY")
        if not api_key:
            return jsonify({"error": "Last.fm API key not configured"}), 500
        
        recommendations = manual_lastfm_get_similar(artist, title, api_key, limit=5)
        
        if recommendations is None:
            return jsonify({"error": "Failed to get recommendations from Last.fm"}), 500
        
        print(f"Got {len(recommendations)} recommendations for {artist} - {title}")
        
        return jsonify({
            "recommendations": recommendations,
            "source": "Last.fm"
        })
        
    except Exception as e:
        print(f"Direct recommendation API error for {artist} - {title}: {str(e)}")
        return jsonify({"error": "Failed to get recommendations"}), 500
