import os
import datetime
import requests
import pylast
from dotenv import load_dotenv
from flask import Flask, jsonify, session, redirect, url_for, send_from_directory, abort, request, request
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from authlib.integrations.flask_client import OAuth
from flask_socketio import SocketIO, emit
from flask_caching import Cache

load_dotenv()

# Initialize Flask app with static folder
app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET")

# Configure caching
app.config['CACHE_TYPE'] = 'SimpleCache'  # In-memory cache for development
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
cache = Cache(app)


# OAuth setup for Spotify
oauth = OAuth(app)
oauth.register(
    name="spotify",
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    access_token_url="https://accounts.spotify.com/api/token",
    authorize_url="https://accounts.spotify.com/authorize",
    client_kwargs={"scope": "user-read-playback-state user-modify-playback-state streaming playlist-read-private user-read-private user-read-email"},
)


# Last.fm API setup
lastfm = pylast.LastFMNetwork(
    api_key=os.getenv("LASTFM_API_KEY"),
    api_secret=os.getenv("LASTFM_SHARED_SECRET")
)


# Database setup for persistent queue
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/beatsync.db")
# Fix Heroku Postgres URL for SQLAlchemy 2.0 compatibility
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure engine with connection pooling for better performance
engine = create_engine(
    DATABASE_URL, 
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class QueueItem(Base):
    __tablename__ = "queue_items"
    id = Column(Integer, primary_key=True, index=True)
    track_uri = Column(String, nullable=False)
    track_name = Column(String, nullable=True)  # Store track name for better display
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True, index=True)
    track_uri = Column(String, nullable=False)
    vote_type = Column(String, nullable=False)  # 'up' or 'down'
    user_id = Column(String, nullable=True)  # For future user identification
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


# Create tables if they don't exist
Base.metadata.create_all(engine)


# Health check
@app.route("/health")
def health():
    return jsonify(status="ok")


# Login route
@app.route("/login")
def login():
    # Store the requested role in session
    requested_role = request.args.get('role', 'listener')
    session['requested_role'] = requested_role
    return oauth.spotify.authorize_redirect(os.getenv("SPOTIFY_REDIRECT_URI"))


# Callback route
@app.route("/callback")
def callback():
    try:
        token = oauth.spotify.authorize_access_token()
        session["spotify_token"] = token
        oauth.spotify.token = token
        
        # Fetch user profile
        try:
            user_response = oauth.spotify.get("https://api.spotify.com/v1/me", token=token)
            user_data = user_response.json()
            user_id = user_data.get("id")
            display_name = user_data.get("display_name", user_id)
            
            # Get the requested role from session
            requested_role = session.get('requested_role', 'listener')
            
            # Handle role assignment
            if requested_role == 'host':
                # Check if someone is already hosting
                import os
                host_file = 'current_host.txt'
                
                if os.path.exists(host_file):
                    # Someone is already hosting
                    return redirect("/?error=host_taken")
                
                # Set as host and create host file
                session["role"] = "host"
                session["user_id"] = user_id
                session["display_name"] = display_name
                
                # Create host file to track current host
                with open(host_file, 'w') as f:
                    f.write(f"{user_id}|{display_name}")
                
                print(f"User {user_id} is now hosting")
                
            else:
                # Set as listener
                session["role"] = "listener"
                session["user_id"] = user_id
                session["display_name"] = display_name
                
                print(f"User {user_id} joined as listener")
            
        except Exception as e:
            print(f"Error fetching user profile: {e}")
            # Default to listener role if we can't fetch user info
            session["role"] = "listener"
            session["user_id"] = "unknown"
            session["display_name"] = "Unknown User"
        
        # Clear the requested role from session
        session.pop('requested_role', None)
        
        return redirect("/")
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        # Log the specific error type for debugging
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        
        # Redirect back to role selection with an error
        return redirect("/select-role?error=oauth_failed")


# Fetch playlists
@app.route("/playlists")
@cache.cached(timeout=300, key_prefix='playlists')  # Cache for 5 minutes
def playlists():
    token = session.get("spotify_token")
    if not token:
        return redirect(url_for("login"))
    
    # Fetch playlists with pagination and limit to improve performance
    params = {
        'limit': 50,  # Max allowed by Spotify API
        'offset': 0
    }
    resp = oauth.spotify.get("https://api.spotify.com/v1/me/playlists", token=token, params=params)
    
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch playlists"}), resp.status_code
    
    data = resp.json()
    
    # Return only essential data to reduce response size
    simplified_playlists = {
        "items": [
            {
                "id": playlist["id"],
                "name": playlist["name"],
                "description": playlist.get("description", ""),
                "tracks": {"total": playlist["tracks"]["total"]},
                "images": playlist.get("images", [])[:1],  # Only first image
                "owner": {"display_name": playlist["owner"]["display_name"]}
            }
            for playlist in data.get("items", [])
        ],
        "total": data.get("total", 0)
    }
    
    return jsonify(simplified_playlists)


# Fetch tracks for a given playlist
@app.route("/playlists/<playlist_id>/tracks")
def playlist_tracks(playlist_id):
    token = session.get("spotify_token")
    if not token:
        return redirect(url_for("login"))
    
    # Get pagination parameters
    limit = min(int(request.args.get('limit', 50)), 50)  # Max 50 per request
    offset = int(request.args.get('offset', 0))
    
    params = {
        'limit': limit,
        'offset': offset,
        'fields': 'items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit'
    }
    
    resp = oauth.spotify.get(
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", 
        token=token, 
        params=params
    )
    
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch tracks"}), resp.status_code
    
    data = resp.json()
    
    # Return simplified track data for better performance
    simplified_tracks = {
        "items": [
            {
                "track": {
                    "id": item["track"]["id"] if item["track"] else None,
                    "name": item["track"]["name"] if item["track"] else "Unknown",
                    "artists": [{"name": artist["name"]} for artist in item["track"]["artists"]] if item["track"] and item["track"]["artists"] else [],
                    "album": {
                        "name": item["track"]["album"]["name"] if item["track"] and item["track"]["album"] else "Unknown",
                        "images": item["track"]["album"]["images"][:1] if item["track"] and item["track"]["album"] and item["track"]["album"]["images"] else []
                    },
                    "uri": item["track"]["uri"] if item["track"] else None,
                    "duration_ms": item["track"]["duration_ms"] if item["track"] else 0
                }
            }
            for item in data.get("items", []) if item.get("track")
        ],
        "total": data.get("total", 0),
        "offset": data.get("offset", 0),
        "limit": data.get("limit", limit)
    }
    
    return jsonify(simplified_tracks)


# Get Last.fm recommendations for a queued track
@app.route("/recommend/<track_uri>")
def recommend(track_uri):
    """Get similar tracks from Last.fm for a queued track"""
    # First, try to get track info from Spotify API
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Extract track ID from URI (spotify:track:XXXXX)
        if not track_uri.startswith("spotify:track:"):
            return jsonify({"error": "Invalid Spotify track URI"}), 400
        
        track_id = track_uri.split(":")[-1]
        
        # Get track info from Spotify
        resp = oauth.spotify.get(f"https://api.spotify.com/v1/tracks/{track_id}", token=token)
        
        if resp.status_code != 200:
            return jsonify({"error": "Failed to get track info from Spotify"}), 500
        
        track_data = resp.json()
        artist = track_data["artists"][0]["name"]
        title = track_data["name"]
        
        try:
            # Get similar tracks from Last.fm
            track = lastfm.get_track(artist, title)
            similar_tracks = track.get_similar(limit=5)
            
            recommendations = []
            for similar in similar_tracks:
                recommendations.append({
                    "artist": similar.item.artist.name,
                    "title": similar.item.title,
                    "url": similar.item.get_url()
                })
            
            return jsonify({"recommendations": recommendations})
            
        except pylast.PyLastError as e:
            print(f"Last.fm API error for {artist} - {title}: {str(e)}")
            return jsonify({"error": f"Last.fm API error: {str(e)}"}), 500
        except Exception as e:
            print(f"Unexpected error for {artist} - {title}: {str(e)}")
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
            
    except Exception as e:
        print(f"Error in recommend route: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# Serve front-end
@app.route("/")
def index():
    # Check if user is authenticated
    if not session.get("role"):
        # Check for error messages
        error = request.args.get('error')
        if error == 'host_taken':
            return redirect("/select-role?error=host_taken")
        return redirect("/select-role")
    
    # Read the HTML file and inject role information
    html_path = os.path.join(app.static_folder, "index.html")
    with open(html_path, 'r') as f:
        html_content = f.read()
    
    # Inject user role and info into the HTML
    role = session.get("role", "guest")
    user_id = session.get("user_id", "")
    display_name = session.get("display_name", "Guest")
    
    # Inject JavaScript variables
    role_script = f"""
    <script>
        window.userRole = '{role}';
        window.userId = '{user_id}';
        window.displayName = '{display_name}';
        console.log('User role:', window.userRole);
    </script>
    """
    
    # Insert the script before the closing head tag
    html_content = html_content.replace('</head>', role_script + '</head>')
    
    return html_content


# Socket.IO setup with production optimizations
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=16384,
    allow_upgrades=True,
    transports=['polling', 'websocket']
)


@socketio.on("connect")
def handle_connect(auth):
    print(f"Client connected: {request.sid}")
    try:
        db = SessionLocal()
        try:
            # Send existing queued items
            items = db.query(QueueItem).order_by(QueueItem.timestamp).all()
            for item in items:
                emit(
                    "queue_updated",
                    {
                        "track_uri": item.track_uri,
                        "track_name": item.track_name,
                        "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                    },
                )

            # Send existing votes
            votes = db.query(Vote).all()
            vote_counts = {}
            for vote in votes:
                if vote.track_uri not in vote_counts:
                    vote_counts[vote.track_uri] = {"up": 0, "down": 0}
                vote_counts[vote.track_uri][vote.vote_type] += 1

            for track_uri, counts in vote_counts.items():
                emit(
                    "vote_updated",
                    {"track_uri": track_uri, "up_votes": counts["up"], "down_votes": counts["down"]},
                )

            # Send existing chat messages
            messages = db.query(ChatMessage).order_by(ChatMessage.timestamp).limit(50).all()
            for msg in messages:
                emit(
                    "chat_message",
                    {
                        "user": msg.user,
                        "message": msg.message,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    },
                )
        finally:
            db.close()
    except Exception as e:
        print(f"Error in connect handler: {e}")
        emit("error", {"message": "Connection error occurred"})


@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on_error_default
def default_error_handler(e):
    print(f"Socket.IO error: {e}")
    return False


@socketio.on("queue_add")
def handle_queue_add(data):
    """Add track to queue - Host only"""
    try:
        # Check if user has host role
        if session.get("role") != "host":
            emit("error", {"message": "Only hosts can add tracks to the queue"})
            return
        
        # Persist the new queue item
        db = SessionLocal()
        try:
            qi = QueueItem(track_uri=data.get("track_uri"), track_name=data.get("track_name"))
            db.add(qi)
            db.commit()
            # Broadcast to all clients with timestamp
            socketio.emit(
                "queue_updated",
                {
                    "track_uri": qi.track_uri,
                    "track_name": qi.track_name,
                    "timestamp": qi.timestamp.isoformat() if qi.timestamp else None,
                },
                broadcast=True
            )
        finally:
            db.close()
    except Exception as e:
        print(f"Error in queue_add: {e}")
        emit("error", {"message": "Failed to add track to queue"})


@socketio.on("vote_add")
def handle_vote_add(data):
    """Handle voting on tracks - Available to all authenticated users"""
    try:
        # Check if user is authenticated (has any role)
        if not session.get("role"):
            emit("error", {"message": "You must be logged in to vote"})
            return
        
        track_uri = data.get("track_uri")
        vote_type = data.get("vote")  # 'up' or 'down'
        user_id = session.get("user_id", "anonymous")  # Use session user_id

        if vote_type not in ["up", "down"]:
            emit("error", {"message": "Invalid vote type"})
            return

        db = SessionLocal()
        try:
            # Add the vote
            vote = Vote(track_uri=track_uri, vote_type=vote_type, user_id=user_id)
            db.add(vote)
            db.commit()

            # Calculate updated vote counts for this track
            up_votes = (
                db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "up").count()
            )

            down_votes = (
                db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "down").count()
            )

            # Broadcast updated vote counts
            socketio.emit(
                "vote_updated", 
                {"track_uri": track_uri, "up_votes": up_votes, "down_votes": down_votes},
                broadcast=True
            )

        finally:
            db.close()
    except Exception as e:
        print(f"Error in vote_add: {e}")
        emit("error", {"message": "Failed to process vote"})


@socketio.on("chat_message")
def handle_chat_message(data):
    """Handle chat messages - Available to all authenticated users"""
    try:
        # Check if user is authenticated (has any role)
        if not session.get("role"):
            emit("error", {"message": "You must be logged in to chat"})
            return
        
        # Use session data for user identification
        user = session.get("display_name", "Anonymous")
        message = data.get("message", "")

        if not message.strip():
            emit("error", {"message": "Message cannot be empty"})
            return

        db = SessionLocal()
        try:
            # Persist the chat message
            chat_msg = ChatMessage(user=user, message=message.strip())
            db.add(chat_msg)
            db.commit()

            # Broadcast to all clients
            socketio.emit(
                "chat_message",
                {
                    "user": chat_msg.user,
                    "message": chat_msg.message,
                    "timestamp": chat_msg.timestamp.isoformat() if chat_msg.timestamp else None,
                },
                broadcast=True
            )

        finally:
            db.close()
    except Exception as e:
        print(f"Error in chat_message: {e}")
        emit("error", {"message": "Failed to send message"})


# Queue management routes
@app.route("/queue/clear", methods=["POST"])
def clear_queue():
    """Clear all items from the queue - Host only"""
    # Check if user is authenticated and has host role
    if session.get("role") != "host":
        return abort(403)
    
    db = SessionLocal()
    try:
        db.query(QueueItem).delete()
        db.commit()
        # Broadcast queue clear to all clients
        socketio.emit("queue_cleared", room=None)
        return jsonify({"status": "success", "message": "Queue cleared"})
    finally:
        db.close()


@app.route("/queue")
def get_queue():
    """Get current queue items"""
    db = SessionLocal()
    try:
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
    finally:
        db.close()


# Get access token for Web Playback SDK
@app.route("/spotify-token")
def get_spotify_token():
    """Get current Spotify access token for Web Playback SDK"""
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Return only the access token (not the full token object for security)
    return jsonify({
        "access_token": token.get("access_token"),
        "expires_in": token.get("expires_in", 3600)
    })


# Playback control routes
@app.route("/playback/play", methods=["POST"])
def play_track():
    """Start playback of a specific track - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json or {}
        track_uri = data.get("track_uri")
        device_id = data.get("device_id")
        
        # Prepare the request payload
        payload = {}
        if track_uri:
            payload["uris"] = [track_uri]
        
        # If device_id is provided, include it in the query parameters
        url = "https://api.spotify.com/v1/me/player/play"
        if device_id:
            url += f"?device_id={device_id}"
        
        if track_uri:
            # Play specific track
            resp = oauth.spotify.put(url, json=payload, token=token)
        else:
            # Resume playback
            resp = oauth.spotify.put(url, token=token)
        
        if resp.status_code == 204:
            return jsonify({"status": "success"})
        elif resp.status_code == 404:
            return jsonify({"error": "No active device found. Please start Spotify on a device or use the web player."}), 404
        else:
            error_msg = f"Playback failed (HTTP {resp.status_code})"
            try:
                error_data = resp.json()
                if "error" in error_data and "message" in error_data["error"]:
                    error_msg = error_data["error"]["message"]
            except:
                pass
            return jsonify({"error": error_msg}), resp.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/pause", methods=["POST"])
def pause_track():
    """Pause current playback - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        resp = oauth.spotify.put(
            "https://api.spotify.com/v1/me/player/pause",
            token=token
        )
        
        if resp.status_code == 204:
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Pause failed"}), resp.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/next", methods=["POST"])
def next_track():
    """Skip to next track - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        resp = oauth.spotify.post(
            "https://api.spotify.com/v1/me/player/next",
            token=token
        )
        
        if resp.status_code == 204:
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Next track failed"}), resp.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/status")
def playback_status():
    """Get current playback status"""
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        resp = oauth.spotify.get(
            "https://api.spotify.com/v1/me/player",
            token=token
        )
        
        if resp.status_code == 200:
            return jsonify(resp.json())
        elif resp.status_code == 204:
            return jsonify({"is_playing": False, "device": None})
        else:
            return jsonify({"error": "Failed to get playback status"}), resp.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Role management routes
@app.route("/select-role")
def select_role():
    """Role selection page"""
    error = request.args.get('error')
    error_message = ""
    
    if error == 'host_taken':
        error_message = """
        <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
            <strong>⚠️ Host Position Taken</strong><br>
            Someone is already hosting a session. You can join as a listener or wait for the current host to sign out.
        </div>
        """
    elif error == 'oauth_failed':
        error_message = """
        <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
            <strong>⚠️ Authentication Failed</strong><br>
            There was an issue connecting to Spotify. Please try again. If the problem persists, clear your browser cache and cookies.
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>BeatSync Mixer - Choose Your Role</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
                text-align: center;
            }}
            h1 {{
                color: #1db954;
                margin-bottom: 30px;
            }}
            .role-card {{
                background: white;
                margin: 20px 0;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                transition: transform 0.2s;
            }}
            .role-card:hover {{
                transform: translateY(-2px);
                box-shadow: 0 8px 12px rgba(0,0,0,0.15);
            }}
            .role-btn {{
                background-color: #1db954;
                color: white;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 50px;
                font-weight: bold;
                font-size: 1.1em;
                display: inline-block;
                margin-top: 15px;
                transition: background-color 0.3s;
            }}
            .role-btn:hover {{
                background-color: #1ed760;
            }}
            .listener-btn {{
                background-color: #666;
            }}
            .listener-btn:hover {{
                background-color: #777;
            }}
            .role-description {{
                color: #666;
                margin: 15px 0;
                line-height: 1.5;
            }}
            .emoji {{
                font-size: 3em;
                margin-bottom: 10px;
            }}
            .status-info {{
                background: #e8f5e8;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border-left: 4px solid #1db954;
            }}
            .disabled {{
                opacity: 0.6;
                pointer-events: none;
            }}
            .restart-section {{
                margin-top: 40px;
                padding: 20px;
                background: #ffe6e6;
                border-radius: 8px;
                border-left: 4px solid #e74c3c;
                text-align: center;
            }}
            .restart-btn {{
                background-color: #e74c3c;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 25px;
                font-size: 1em;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s;
                text-decoration: none;
                display: inline-block;
                margin-top: 10px;
            }}
            .restart-btn:hover {{
                background-color: #c0392b;
                transform: scale(1.05);
            }}
        </style>
    </head>
    <body>
        <h1>🎵 BeatSync Mixer</h1>
        
        {error_message}
        <div id="host-status"></div>
        
        <div class="role-card" id="host-card">
            <div class="emoji">🎛️</div>
            <h2>Host a Session</h2>
            <div class="role-description">
                Control the music, manage the queue, and lead the listening session.
                <br><strong>Requires:</strong> Spotify Premium account
            </div>
            <a href="/login?role=host" class="role-btn" id="host-btn">🎵 Host Session</a>
        </div>
        
        <div class="role-card">
            <div class="emoji">🎧</div>
            <h2>Join as Listener</h2>
            <div class="role-description">
                Vote on tracks, chat with others, and enjoy the collaborative experience.
                <br><strong>Note:</strong> Limited control over playback
            </div>
            <a href="/login?role=listener" class="role-btn listener-btn">👥 Join Session</a>
        </div>
        
        <div class="restart-section">
            <h3 style="color: #e74c3c; margin-bottom: 10px;">⚠️ Session Management</h3>
            <p style="color: #666; margin-bottom: 15px;">
                Need to reset everything? This will clear all sessions, votes, queue, and chat for everyone.
            </p>
            <button onclick="restartSession()" class="restart-btn">
                🔄 Restart Entire Session
            </button>
        </div>
        
        <script>
            // Check if someone is already hosting
            fetch('/host-status')
                .then(response => response.json())
                .then(data => {{
                    const statusDiv = document.getElementById('host-status');
                    const hostCard = document.getElementById('host-card');
                    const hostBtn = document.getElementById('host-btn');
                    
                    if (data.has_host) {{
                        statusDiv.innerHTML = `
                            <div class="status-info">
                                <strong>🎛️ Session Active!</strong><br>
                                ${{data.host_name}} is currently hosting.<br>
                                You can join as a listener or wait for them to sign out.
                            </div>
                        `;
                        hostCard.classList.add('disabled');
                        hostBtn.style.backgroundColor = '#ccc';
                        hostBtn.onclick = function(e) {{ 
                            e.preventDefault(); 
                            alert('Someone is already hosting. Please wait for them to sign out.');
                        }};
                    }}
                }})
                .catch(err => console.log('Could not check host status'));
            
            // Restart session function
            async function restartSession() {{
                if (confirm('⚠️ RESTART ENTIRE SESSION\\n\\nThis will:\\n• Clear all sessions for everyone\\n• Remove current host\\n• Clear the entire queue\\n• Reset all votes\\n• Clear all chat messages\\n• Force all users to reconnect\\n\\nAre you sure you want to restart the entire session?')) {{
                    try {{
                        const response = await fetch('/restart-session', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }}
                        }});
                        
                        if (response.ok) {{
                            const data = await response.json();
                            alert('✅ ' + data.message + '\\n\\nRefreshing page...');
                            window.location.reload();
                        }} else {{
                            const error = await response.json();
                            alert('❌ Error restarting session: ' + (error.error || 'Unknown error'));
                        }}
                    }} catch (error) {{
                        console.error('Error restarting session:', error);
                        alert('❌ Network error while restarting session. Please try again.');
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """


@app.route("/host-status")
def host_status():
    """Check if someone is currently hosting"""
    # Check if there's an active host session
    # For simplicity, we'll use a simple file-based approach
    import os
    host_file = 'current_host.txt'
    
    if os.path.exists(host_file):
        try:
            with open(host_file, 'r') as f:
                host_info = f.read().strip().split('|')
                if len(host_info) >= 2:
                    return jsonify({
                        "has_host": True,
                        "host_id": host_info[0],
                        "host_name": host_info[1]
                    })
        except:
            pass
    
    return jsonify({"has_host": False})


@app.route("/sign-out-host", methods=["POST"])
def sign_out_host():
    """Sign out as host"""
    if session.get("role") != "host":
        return jsonify({"error": "Only hosts can sign out"}), 403
    
    # Remove host file
    import os
    host_file = 'current_host.txt'
    if os.path.exists(host_file):
        os.remove(host_file)
    
    # Clear session
    session.clear()
    
    return jsonify({"status": "success", "message": "Signed out as host"})


@app.route("/restart-session", methods=["POST"])
def restart_session():
    """Restart the entire session - clears all session data, host state, queue, votes, and chat"""
    try:
        # Remove host file
        import os
        host_file = 'current_host.txt'
        if os.path.exists(host_file):
            os.remove(host_file)
        
        # Clear all user sessions (note: this only clears the current user's session)
        session.clear()
        
        # Clear the queue, votes, and chat
        db = SessionLocal()
        try:
            # Clear all votes
            db.query(Vote).delete()
            
            # Clear all queue items
            db.query(QueueItem).delete()
            
            # Clear all chat messages
            db.query(ChatMessage).delete()
            
            db.commit()
            
            # Emit events to all connected clients
            socketio.emit('queue_cleared', broadcast=True)
            socketio.emit('votes_cleared', broadcast=True)
            socketio.emit('chat_cleared', broadcast=True)
            socketio.emit('session_restarted', broadcast=True)
            
        except Exception as e:
            db.rollback()
            print(f"Error clearing data during session restart: {e}")
        finally:
            db.close()
        
        return jsonify({
            "status": "success", 
            "message": "Session restarted successfully. All data cleared. All users should refresh their browsers."
        })
        
    except Exception as e:
        print(f"Error restarting session: {e}")
        return jsonify({"error": "Failed to restart session"}), 500


@app.route("/playback/devices")
def get_devices():
    """Get available Spotify devices"""
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        resp = oauth.spotify.get(
            "https://api.spotify.com/v1/me/player/devices",
            token=token
        )
        
        if resp.status_code == 200:
            return jsonify(resp.json())
        else:
            return jsonify({"error": "Failed to get devices"}), resp.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/transfer", methods=["POST"])
def transfer_playback():
    """Transfer playback to a specific device - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    token = session.get("spotify_token")
    if not token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json or {}
        device_id = data.get("device_id")
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        resp = oauth.spotify.put(
            "https://api.spotify.com/v1/me/player",
            json={"device_ids": [device_id], "play": False},
            token=token
        )
        
        if resp.status_code == 204:
            return jsonify({"status": "success"})
        else:
            error_msg = f"Transfer failed (HTTP {resp.status_code})"
            try:
                error_data = resp.json()
                if "error" in error_data and "message" in error_data["error"]:
                    error_msg = error_data["error"]["message"]
            except:
                pass
            return jsonify({"error": error_msg}), resp.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/queue/next-track")
def get_next_track():
    """Get the next track to play based on voting system"""
    db = SessionLocal()
    try:
        # Get all queue items with their votes
        queue_items = db.query(QueueItem).order_by(QueueItem.timestamp).all()
        
        if not queue_items:
            return jsonify({"error": "Queue is empty"}), 404
        
        best_track = None
        best_score = -999  # Start with very low score
        
        for item in queue_items:
            # Get vote counts for this track
            votes = db.query(Vote).filter_by(track_uri=item.track_uri).all()
            up_votes = len([v for v in votes if v.vote_type == 'up'])
            down_votes = len([v for v in votes if v.vote_type == 'down'])
            
            # Calculate net score (likes - dislikes)
            net_score = up_votes - down_votes
            
            # Skip tracks with more dislikes than likes
            if down_votes > up_votes:
                continue
            
            # Find the track with the highest net score
            if net_score > best_score:
                best_score = net_score
                best_track = {
                    "track_uri": item.track_uri,
                    "track_name": item.track_name,
                    "up_votes": up_votes,
                    "down_votes": down_votes,
                    "net_score": net_score
                }
        
        if not best_track:
            # No suitable track found (all have more dislikes than likes)
            return jsonify({"error": "No playable tracks in queue"}), 404
        
        return jsonify(best_track)
        
    finally:
        db.close()


@app.route("/queue/auto-play", methods=["POST"])
def auto_play_next():
    """Automatically play the next track based on voting - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    try:
        # Get the next track based on voting
        next_track_response = get_next_track()
        
        if next_track_response.status_code != 200:
            return next_track_response
        
        next_track = next_track_response.get_json()
        track_uri = next_track["track_uri"]
        
        # Play the track
        token = session.get("spotify_token")
        if not token:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.json or {}
        device_id = data.get("device_id")
        
        url = "https://api.spotify.com/v1/me/player/play"
        if device_id:
            url += f"?device_id={device_id}"
        
        resp = oauth.spotify.put(url, json={"uris": [track_uri]}, token=token)
        
        if resp.status_code == 204:
            return jsonify({
                "status": "success", 
                "track": next_track,
                "message": f"Now playing: {next_track['track_name']} (Score: +{next_track['net_score']})"
            })
        else:
            return jsonify({"error": "Failed to play track"}), resp.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/queue/remove/<track_uri>", methods=["POST"])
def remove_from_queue(track_uri):
    """Remove a specific track from the queue after it's played"""
    db = SessionLocal()
    try:
        # Find and remove the track
        item = db.query(QueueItem).filter_by(track_uri=track_uri).first()
        if item:
            db.delete(item)
            
            # Also remove associated votes
            db.query(Vote).filter_by(track_uri=track_uri).delete()
            
            db.commit()
            
            # Emit removal event to all clients
            socketio.emit('track_removed', {
                'track_uri': track_uri,
                'track_name': item.track_name
            }, broadcast=True)
            
            return jsonify({"status": "success", "message": "Track removed from queue"})
        else:
            return jsonify({"error": "Track not found in queue"}), 404
            
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
