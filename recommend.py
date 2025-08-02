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
    """Get similar tracks from Last.fm API with fallback methods"""
    
    params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': str(limit)
    }
    
    # Try direct API call first
    try:
        print(f"🎵 Getting Last.fm recommendations for: {artist} - {title}")
        
        response = requests.get(
            "http://ws.audioscrobbler.com/2.0/",
            params=params,
            timeout=(10, 15),
            headers={'User-Agent': 'BeatSyncMixer/1.0'}
        )
        
        print(f"Last.fm API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Last.fm API response: {data}")
            
            if 'error' in data:
                print(f"❌ Last.fm API error: {data.get('message', 'Unknown error')}")
                return []
            
            similar_tracks = []
            tracks = data.get('similartracks', {}).get('track', [])
            
            if isinstance(tracks, dict):
                tracks = [tracks]
            
            for track in tracks[:limit]:
                artist_name = track.get('artist', {})
                if isinstance(artist_name, dict):
                    artist_name = artist_name.get('name', 'Unknown Artist')
                elif isinstance(artist_name, str):
                    artist_name = artist_name
                else:
                    artist_name = 'Unknown Artist'
                
                similar_tracks.append({
                    'artist': artist_name,
                    'title': track.get('name', 'Unknown Title'),
                    'url': track.get('url', '#'),
                    'source': 'Last.fm'
                })
            
            print(f"✅ Found {len(similar_tracks)} recommendations")
            return similar_tracks
        else:
            print(f"❌ Last.fm API returned status {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ Last.fm API call failed: {e}")
    
    # If we get here, the API call failed
    print("🔄 Falling back to manual IP lookup...")
    
    # Fallback to IP-based call
    ip_addresses = ["130.211.19.189", "64.34.119.12"]  # Updated IP addresses for Last.fm
    
    for ip in ip_addresses:
        try:
            url = f"http://{ip}/2.0/"
            headers = {
                'Host': 'ws.audioscrobbler.com',
                'User-Agent': 'BeatSyncMixer/1.0'
            }
            
            print(f"Trying IP fallback: {ip}")
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=(5, 10)
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'error' in data:
                    print(f"Last.fm API error (IP {ip}): {data.get('message', 'Unknown error')}")
                    continue
                
                similar_tracks = []
                tracks = data.get('similartracks', {}).get('track', [])
                
                if isinstance(tracks, dict):
                    tracks = [tracks]
                
                for track in tracks[:limit]:
                    artist_name = track.get('artist', {})
                    if isinstance(artist_name, dict):
                        artist_name = artist_name.get('name', 'Unknown Artist')
                    elif isinstance(artist_name, str):
                        artist_name = artist_name
                    else:
                        artist_name = 'Unknown Artist'
                    
                    similar_tracks.append({
                        'artist': artist_name,
                        'title': track.get('name', 'Unknown Title'),
                        'url': track.get('url', '#'),
                        'source': 'Last.fm'
                    })
                
                print(f"✅ Found {len(similar_tracks)} recommendations via IP {ip}")
                return similar_tracks
                
        except Exception as e:
            print(f"IP fallback failed for {ip}: {e}")
            continue
    
    print("❌ All Last.fm API attempts failed")
    return []


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
        
        # Get Last.fm recommendations using manual IP-based client
        api_key = os.getenv("LASTFM_API_KEY")
        if not api_key:
            return jsonify({"error": "Last.fm API key not configured"}), 500
        
        recommendations = manual_lastfm_get_similar(artist, title, api_key, limit=5)
        
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
