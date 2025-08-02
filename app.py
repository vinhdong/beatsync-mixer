import os
import json
from datetime import datetime, timezone, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
# Force rebuild - using Spotipy OAuth
import requests
import pylast
import time
import traceback
from dotenv import load_dotenv
from flask import Flask, jsonify, session, redirect, url_for, send_from_directory, abort, request, request
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from flask_socketio import SocketIO, emit
from flask_caching import Cache
from flask_session import Session
import tempfile

load_dotenv()

# Initialize Flask app with static folder
app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET")

# Configure server-side session storage for better persistence
if os.getenv('FLASK_ENV') == 'production':
    # In production (Heroku), use filesystem storage in /tmp
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_sessions'
    app.config['SESSION_FILE_THRESHOLD'] = 100  # Maximum number of sessions
else:
    # Local development can use Redis or filesystem
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = tempfile.mkdtemp(prefix='beatsync_sessions_')

app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'beatsync:'

# Configure session for production with OAuth compatibility
app.config['SESSION_COOKIE_SECURE'] = True if os.getenv('FLASK_ENV') == 'production' else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow cross-site requests for OAuth callbacks
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # 24 hour sessions
app.config['SESSION_REFRESH_EACH_REQUEST'] = False  # Don't refresh during OAuth flow to preserve state
app.config['SESSION_COOKIE_NAME'] = 'beatsync_session'  # Custom session name
app.config['SESSION_COOKIE_DOMAIN'] = None  # Let Flask handle domain automatically

# Initialize server-side session storage
Session(app)

# Configure caching
app.config['CACHE_TYPE'] = 'SimpleCache'  # In-memory cache for development
app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
cache = Cache(app)

# Spotipy OAuth setup with ultra-aggressive timeout settings for Heroku
spotify_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-read-playback-state user-modify-playback-state streaming playlist-read-private user-read-private user-read-email",
    show_dialog=False,
    cache_path=None,  # Don't use file-based cache, we'll handle tokens manually
    requests_timeout=2,  # Ultra-short timeout - fail in 2s, not 10s
    open_browser=False
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
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True, index=True)
    track_uri = Column(String, nullable=False)
    vote_type = Column(String, nullable=False)  # 'up' or 'down'
    user_id = Column(String, nullable=True)  # For future user identification
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, nullable=False)
    message = Column(String, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Create tables if they don't exist
Base.metadata.create_all(engine)


# Session management middleware
@app.before_request
def ensure_session():
    """Ensure session is valid and handle session persistence issues"""
    try:
        # Skip session modification during OAuth flow to preserve state
        if request.path in ['/login', '/callback']:
            return
            
        # Make session permanent to extend lifetime
        session.permanent = True
        
        # Initialize session for new users if needed
        if not session.get('initialized'):
            session['initialized'] = True
            session['created_at'] = datetime.now(timezone.utc).isoformat()
            
        # Handle Socket.IO requests differently
        if request.path.startswith('/socket.io/'):
            return
            
        # Ensure all users have a role (fallback for lost sessions)
        if not session.get('role') and request.endpoint not in ['health', 'select_role']:
            session['role'] = 'guest'
            session['user_id'] = f"guest_{datetime.now().timestamp()}"
            session['display_name'] = 'Guest'
            
    except Exception as e:
        print(f"Session initialization error: {e}")
        # Only reset session if not in OAuth flow
        if request.path not in ['/login', '/callback']:
            session.clear()
            session['role'] = 'guest'
            session['user_id'] = f"guest_{datetime.now().timestamp()}"
            session['display_name'] = 'Guest'
            session['initialized'] = True


# Health check
@app.route("/health")
def health():
    return jsonify(status="ok")


# Login route
@app.route("/login")
def login():
    try:
        # Store the requested role in session
        requested_role = request.args.get('role', 'listener')
        session['requested_role'] = requested_role
        
        # Ensure session is properly initialized before OAuth
        if not session.get('initialized'):
            session['initialized'] = True
            session['created_at'] = datetime.now(timezone.utc).isoformat()
        
        # Make session permanent to ensure it persists through OAuth flow
        session.permanent = True
        
        # Use Spotipy's OAuth to get authorization URL
        auth_url = spotify_oauth.get_authorize_url()
        return redirect(auth_url)
        
    except Exception as e:
        print(f"Login route error: {e}")
        return redirect("/select-role?error=oauth_failed")


# Callback route
@app.route("/callback")
def callback():
    try:
        # Get authorization code from callback
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            print(f"OAuth error: {error}")
            return redirect("/select-role?error=oauth_failed")
        
        if not code:
            print("No authorization code received")
            return redirect("/select-role?error=oauth_failed")
        
        # Use ONLY fast IP-based token exchange - no DNS/Spotipy fallback to avoid 20s delays
        token_info = manual_token_exchange(code)
        
        if not token_info:
            print("Fast IP exchange failed - network/Heroku issue")
            error_msg = "network_timeout"
            return redirect(f"/select-role?error=oauth_failed&details={error_msg}")
        
        # Store token in session
        session["spotify_token"] = token_info
        
        # Fetch real user profile using IP-based approach to avoid DNS timeouts
        access_token = token_info.get("access_token")
        user_profile = manual_user_profile_fetch(access_token) if access_token else None
        
        if user_profile:
            user_id = user_profile.get("id", f"user_{int(time.time())}")
            display_name = user_profile.get("display_name") or user_profile.get("id", "Spotify User")
        else:
            # Fallback if profile fetch fails
            user_id = f"user_{int(time.time())}"
            display_name = "Spotify User"
        
        # Get the requested role from session
        requested_role = session.get('requested_role', 'listener')
        
        # Handle role assignment
        if requested_role == 'host':
            # Check if someone is already hosting
            host_file = 'current_host.txt'
            
            if os.path.exists(host_file):
                return redirect("/select-role?error=host_taken")
            
            # Set as host and create host file
            session["role"] = "host"
            session["user_id"] = user_id
            session["display_name"] = display_name
            
            # Create host file to track current host
            with open(host_file, 'w') as f:
                f.write(f"{user_id}|{display_name}")
            
        else:
            # Set as listener
            session["role"] = "listener"
            session["user_id"] = user_id
            session["display_name"] = display_name
        
        # Clear the requested role from session
        session.pop('requested_role', None)
        
        # Ensure session is properly saved
        session.permanent = True
        
        return redirect("/")
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        session.clear()
        return redirect("/select-role?error=oauth_failed")


# Fetch playlists
@app.route("/playlists")
def playlists():
    token_info = session.get("spotify_token")
    if not token_info:
        print("No Spotify token in session - redirecting to login")
        return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        print("No access token available - redirecting to login")
        return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
    
    try:
        # Use manual IP-based fetch to avoid DNS timeouts
        data = manual_playlists_fetch(access_token)
        
        if not data:
            print("Manual playlists fetch failed - likely network issue")
            return jsonify({"error": "Failed to fetch playlists"}), 500
        
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
    except Exception as e:
        print(f"Error fetching playlists: {e}")
        return jsonify({"error": "Failed to fetch playlists"}), 500


# Fetch tracks for a given playlist
@app.route("/playlists/<playlist_id>/tracks")
def playlist_tracks(playlist_id):
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for("login"))
    
    try:
        # Get pagination parameters
        limit = min(int(request.args.get('limit', 50)), 50)  # Max 50 per request
        offset = int(request.args.get('offset', 0))
        
        # Fetch tracks with Spotipy
        data = sp.playlist_tracks(
            playlist_id, 
            limit=limit, 
            offset=offset,
            fields='items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit'
        )
        
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
    except Exception as e:
        print(f"Error fetching playlist tracks: {e}")
        return jsonify({"error": "Failed to fetch tracks"}), 500


# Get Last.fm recommendations for a queued track
@app.route("/recommend/<track_uri>")
def recommend(track_uri):
    """Get similar tracks from Last.fm for a queued track"""
    # First, try to get track info from Spotify API
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Extract track ID from URI (spotify:track:XXXXX)
        if not track_uri.startswith("spotify:track:"):
            return jsonify({"error": "Invalid Spotify track URI"}), 400
        
        track_id = track_uri.split(":")[-1]
        
        # Get track info from Spotify using Spotipy
        track_data = sp.track(track_id)
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
    # Check if user is authenticated - allow guest, host, and listener roles
    user_role = session.get("role")
    if not user_role or user_role not in ['guest', 'host', 'listener']:
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


# Socket.IO setup with production optimizations for Heroku
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    ping_timeout=120,  # Increased timeout for slower connections
    ping_interval=30,  # More frequent pings
    max_http_buffer_size=16384,
    allow_upgrades=False,  # Disable websocket upgrades for Heroku stability
    transports=['polling'],  # Use only polling transport for better reliability
    manage_session=False,  # Let Flask handle sessions
    cookie=False,  # Disable Socket.IO's own cookies to rely on Flask session
    engineio_logger=False,  # Disable verbose logging
    logger=False,  # Disable verbose logging
    async_mode='threading'  # Use threading mode for better Heroku compatibility
)


@socketio.on("connect")
def handle_connect(auth):
    # Check if session is valid
    try:
        # If no role in session, set as guest
        if not session.get('role'):
            session['role'] = 'guest'
            session['user_id'] = f"guest_{request.sid[:8]}"
            session['display_name'] = 'Guest'
            
    except Exception as e:
        print(f"Session error on connect: {e}")
        # Fallback session setup
        session['role'] = 'guest'
        session['user_id'] = f"guest_{request.sid[:8]}"
        session['display_name'] = 'Guest'
    
    # Send initial data in smaller chunks to avoid timeouts
    try:
        emit("connection_established", {"status": "connected", "sid": request.sid})
        
        # Send data asynchronously to avoid blocking
        socketio.start_background_task(send_initial_data_async, request.sid)
        
    except Exception as e:
        print(f"Error in connect handler: {e}")
        emit("error", {"message": "Connection error occurred"})

def send_initial_data_async(client_sid):
    """Send initial data asynchronously to avoid blocking the connection"""
    try:
        db = SessionLocal()
        try:
            # Send existing queued items (limit to prevent timeout)
            items = db.query(QueueItem).order_by(QueueItem.timestamp).limit(20).all()
            for item in items:
                socketio.emit(
                    "queue_updated",
                    {
                        "track_uri": item.track_uri,
                        "track_name": item.track_name,
                        "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                    },
                    room=client_sid
                )

            # Send existing votes (limit to prevent timeout)
            votes = db.query(Vote).limit(50).all()
            vote_counts = {}
            for vote in votes:
                if vote.track_uri not in vote_counts:
                    vote_counts[vote.track_uri] = {"up": 0, "down": 0}
                vote_counts[vote.track_uri][vote.vote_type] += 1

            for track_uri, counts in vote_counts.items():
                socketio.emit(
                    "vote_updated",
                    {"track_uri": track_uri, "up_votes": counts["up"], "down_votes": counts["down"]},
                    room=client_sid
                )

            # Send recent chat messages (limit to 20 to prevent timeout)
            messages = db.query(ChatMessage).order_by(ChatMessage.timestamp.desc()).limit(20).all()
            for msg in reversed(messages):  # Reverse to show in chronological order
                socketio.emit(
                    "chat_message",
                    {
                        "user": msg.user,
                        "message": msg.message,
                        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    },
                    room=client_sid
                )
                
            socketio.emit("initial_data_complete", {"status": "complete"}, room=client_sid)
                
        finally:
            db.close()
    except Exception as e:
        print(f"Error sending initial data: {e}")
        socketio.emit("error", {"message": "Error loading initial data"}, room=client_sid)


@socketio.on("disconnect")
def handle_disconnect(reason=None):
    pass


@socketio.on_error_default
def default_error_handler(e):
    print(f"Socket.IO error: {e}")
    return False


@socketio.on("queue_add")
def handle_queue_add(data):
    """Add track to queue - Host only"""
    try:
        # Check if session exists and has role
        user_role = session.get("role")
        user_id = session.get("user_id") 
        
        if not user_role:
            emit("error", {"message": "Authentication expired. Please refresh the page and log in again."})
            return
            
        if user_role != "host":
            emit("error", {"message": "Only hosts can add tracks to the queue"})
            return
        
        # Validate data
        track_uri = data.get("track_uri") if data else None
        track_name = data.get("track_name") if data else None
        
        if not track_uri or not track_name:
            emit("error", {"message": "Missing track information"})
            return
        
        # Persist the new queue item
        db = SessionLocal()
        try:
            qi = QueueItem(track_uri=track_uri, track_name=track_name)
            db.add(qi)
            db.commit()
            
            # Broadcast to all clients with timestamp
            socketio.emit(
                "queue_updated",
                {
                    "track_uri": qi.track_uri,
                    "track_name": qi.track_name,
                    "timestamp": qi.timestamp.isoformat() if qi.timestamp else None,
                }
            )
            
            # Send success confirmation back to the sender
            emit("queue_add_success", {
                "message": f"Added '{track_name}' to queue",
                "track_uri": track_uri
            })
            
        except Exception as db_error:
            print(f"Database error: {db_error}")
            db.rollback()
            emit("error", {"message": "Database error while adding track"})
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
                {"track_uri": track_uri, "up_votes": up_votes, "down_votes": down_votes}
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
                }
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
        socketio.emit("queue_cleared")
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
    
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json or {}
        track_uri = data.get("track_uri")
        device_id = data.get("device_id")
        
        if track_uri:
            # Play specific track
            sp.start_playback(device_id=device_id, uris=[track_uri])
        else:
            # Resume playback
            sp.start_playback(device_id=device_id)
        
        return jsonify({"status": "success"})
        
    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 404:
            return jsonify({"error": "No active device found. Please start Spotify on a device or use the web player."}), 404
        else:
            return jsonify({"error": str(e)}), e.http_status
    except Exception as e:
        return jsonify({"error": str(e)}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/pause", methods=["POST"])
def pause_track():
    """Pause current playback - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        sp.pause_playback()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/next", methods=["POST"])
def next_track():
    """Skip to next track - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        sp.next_track()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/status")
def playback_status():
    """Get current playback status"""
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        playback = sp.current_playback()
        if playback:
            return jsonify(playback)
        else:
            return jsonify({"is_playing": False, "device": None})
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
    elif error == 'csrf_error':
        error_message = """
        <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
            <strong>⚠️ Session Security Error</strong><br>
            Your session expired during authentication. This commonly happens after restarting the session.<br><br>
            <strong>Please try:</strong><br>
            1. Click "Clear Session & Try Again" below<br>
            2. If it keeps failing, clear your browser cookies and try again
        </div>
        <div style="text-align: center; margin-bottom: 20px;">
            <a href="/clear-session-and-login?role=host" style="background-color: #e74c3c; color: white; padding: 12px 24px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin: 5px;">
                🔄 Clear Session & Try Host Again
            </a>
            <a href="/clear-session-and-login?role=listener" style="background-color: #666; color: white; padding: 12px 24px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block; margin: 5px;">
                🔄 Clear Session & Try Listener
            </a>
        </div>
        """
    elif error == 'oauth_failed':
        details = request.args.get('details', '')
        if details == 'dns_timeout':
            error_message = """
            <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
                <strong>🌐 Network Connection Issue</strong><br>
                Unable to connect to Spotify's servers due to DNS/network timeout.<br>
                This is a known issue with Heroku's network to Spotify.<br><br>
                <strong>Please try:</strong><br>
                1. Wait 1-2 minutes and try again<br>
                2. Try multiple times - it sometimes works on retry<br>
                3. Check <a href="https://status.heroku.com" target="_blank">Heroku status</a> for network issues<br>
                4. Contact support if this persists for over 15 minutes
            </div>
            """
        elif details == 'network_timeout':
            error_message = """
            <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
                <strong>⏱️ Connection Timeout</strong><br>
                Connection to Spotify timed out. This may be temporary.<br><br>
                <strong>Please try:</strong><br>
                1. Wait 30 seconds and try again<br>
                2. Try multiple times - network issues can be intermittent<br>
                3. Clear browser cache and try again
            </div>
            """
        else:
            error_message = """
            <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
                <strong>⚠️ Authentication Failed</strong><br>
                There was an issue connecting to Spotify. This might be due to:<br>
                • Network timeout (Heroku → Spotify)<br>
                • Temporary Spotify API issues<br>
                • Browser cache/cookie issues<br><br>
                <strong>Please try:</strong><br>
                1. Wait 30 seconds and try again<br>
                2. Clear browser cache and cookies<br>
                3. Try a different browser or incognito mode
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
                            alert('✅ ' + data.message + '\\n\\nSession has been restarted. You can now host or join.\\n\\nNote: If you get a session security error when trying to login, use the "Clear Session & Try Again" buttons.');
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
    host_file = 'current_host.txt'
    if os.path.exists(host_file):
        os.remove(host_file)
    
    # Clear session
    session.clear()
    
    return jsonify({"status": "success", "message": "Signed out as host"})
    host_file = 'current_host.txt'
    if os.path.exists(host_file):
        os.remove(host_file)
    
    # Clear session
    session.clear()
    
    return jsonify({"status": "success", "message": "Signed out as host"})


@app.route("/logout")
def logout():
    """Clear session and redirect to role selection"""
    session.clear()
    return redirect("/select-role")


@app.route("/reset-session")
def reset_session():
    """Reset user session and redirect to role selection"""
    session.clear()
    return redirect("/select-role")


@app.route("/clear-session-and-login")
def clear_session_and_login():
    """Clear session completely and redirect to login with role"""
    requested_role = request.args.get('role', 'host')
    
    # Clear all session data
    session.clear()
    
    return redirect(f"/login?role={requested_role}")



@app.route("/restart-session", methods=["POST"])
def restart_session():
    """Restart the entire session - clears all session data, host state, queue, votes, and chat"""
    try:
        # Remove host file
        host_file = 'current_host.txt'
        if os.path.exists(host_file):
            os.remove(host_file)
        
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
            socketio.emit('queue_cleared')
            socketio.emit('votes_cleared')
            socketio.emit('chat_cleared')
            socketio.emit('session_restarted')
            
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
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        devices = sp.devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/playback/transfer", methods=["POST"])
def transfer_playback():
    """Transfer playback to a specific device - Host only"""
    if session.get("role") != "host":
        return abort(403)
    
    sp = get_spotify_client()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        data = request.json or {}
        device_id = data.get("device_id")
        
        if not device_id:
            return jsonify({"error": "Device ID is required"}), 400
        
        sp.transfer_playback(device_id=device_id, force_play=False)
        return jsonify({"status": "success"})
        
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
        if best_track:
            return jsonify(best_track)
        else:
            return jsonify({"error": "No suitable track found (all tracks have negative votes)"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
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
        track_uri = next_track["track_uri"];
        
        # Play the track using Spotipy
        sp = get_spotify_client()
        if not sp:
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.json or {}
        device_id = data.get("device_id")
        
        sp.start_playback(device_id=device_id, uris=[track_uri])
        
        return jsonify({
            "status": "success", 
            "track": next_track,
            "message": f"Now playing: {next_track['track_name']} (Score: +{next_track['net_score']})"
        })
        
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
            })
            
            return jsonify({"status": "success", "message": "Track removed from queue"})
        else:
            return jsonify({"error": "Track not found in queue"}), 404
            
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# Manual token exchange fallback for Heroku DNS issues
def manual_token_exchange(auth_code):
    """Manual token exchange using hardcoded Spotify IPs as DNS fallback"""
    import requests
    
    # Spotify IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    token_data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': os.getenv("SPOTIFY_REDIRECT_URI"),
        'client_id': os.getenv("SPOTIFY_CLIENT_ID"),
        'client_secret': os.getenv("SPOTIFY_CLIENT_SECRET")
    }
    
    # Try each IP directly - bypass DNS completely by not using hostname
    for ip in ip_addresses:
        try:
            # Post directly to the IP, use Host header for TLS
            url = f"https://{ip}/api/token"
            headers = {
                'Host': 'accounts.spotify.com',  # For TLS certificate validation
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Create a custom requests session to avoid DNS caching
            req_session = requests.Session()
            
            response = req_session.post(
                url,
                data=token_data,
                headers=headers,
                timeout=(3, 3),  # Very short timeout to fail fast
                verify=False  # Skip SSL verification since we're using IP
            )
            
            if response.status_code == 200:
                token_info = response.json()
                # Add expiry time for Spotipy compatibility
                import time
                token_info['expires_at'] = int(time.time()) + token_info.get('expires_in', 3600)
                return token_info
                
        except Exception as e:
            continue
    
    return None


# Manual token refresh fallback for Heroku DNS issues
def manual_token_refresh(refresh_token):
    """Manual token refresh using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': os.getenv("SPOTIFY_CLIENT_ID"),
        'client_secret': os.getenv("SPOTIFY_CLIENT_SECRET")
    }
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Post directly to the IP, use Host header for TLS
            url = f"https://{ip}/api/token"
            headers = {
                'Host': 'accounts.spotify.com',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            req_session = requests.Session()
            
            response = req_session.post(
                url,
                data=token_data,
                headers=headers,
                timeout=(3, 3),
                verify=False  # Skip SSL verification since we're using IP
            )
            
            if response.status_code == 200:
                token_info = response.json()
                # Add expiry time for Spotipy compatibility
                import time
                token_info['expires_at'] = int(time.time()) + token_info.get('expires_in', 3600)
                return token_info
                
        except Exception as e:
            continue
    
    return None


# Manual user profile fetch fallback for Heroku DNS issues
def manual_user_profile_fetch(access_token):
    """Manual user profile fetch using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify API IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Get user profile directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/me"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                headers=headers,
                timeout=(3, 3),
                verify=False  # Skip SSL verification since we're using IP
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            continue
    
    return None


# Manual playlists fetch fallback for Heroku DNS issues
def manual_playlists_fetch(access_token):
    """Manual playlists fetch using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify API IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Get user playlists directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/me/playlists?limit=50&offset=0"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                headers=headers,
                timeout=(3, 3),
                verify=False  # Skip SSL verification since we're using IP
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            continue
    
    return None


# Helper function to create Spotipy client from session
def get_spotify_client():
    """Get a Spotipy client using the token from session"""
    token_info = session.get("spotify_token")
    if not token_info:
        return None
    
    # Check if token needs refresh
    if spotify_oauth.is_token_expired(token_info):
        try:
            # Use ONLY fast IP-based refresh - no Spotipy fallback to avoid delays
            refreshed_token = manual_token_refresh(token_info['refresh_token'])
            if refreshed_token:
                session["spotify_token"] = refreshed_token
                token_info = refreshed_token
            else:
                return None
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return None
    
    return spotipy.Spotify(auth=token_info['access_token'])

# Run the Flask app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)


@app.route("/fetch-user-profile", methods=["POST"])
def fetch_user_profile():
    """Fetch user profile asynchronously after login"""
    if not session.get("spotify_token"):
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Use IP-based approach to fetch user profile, avoiding DNS timeouts
        token_info = session.get("spotify_token")
        access_token = token_info.get("access_token")
        
        if not access_token:
            return jsonify({"error": "No access token"}), 401
        
        # Try to get user profile using direct IP requests to avoid DNS issues
        user_profile = manual_user_profile_fetch(access_token)
        
        if user_profile:
            # Update session with real user info
            session["user_id"] = user_profile.get("id", session.get("user_id"))
            session["display_name"] = user_profile.get("display_name") or user_profile.get("id", "Spotify User")
            
            # Update host file if user is host
            if session.get("role") == "host":
                host_file = 'current_host.txt'
                if os.path.exists(host_file):
                    with open(host_file, 'w') as f:
                        f.write(f"{session['user_id']}|{session['display_name']}")
            
            return jsonify({
                "success": True,
                "user_id": session["user_id"],
                "display_name": session["display_name"]
            })
        
        return jsonify({"error": "Could not fetch user profile"}), 500
            
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        return jsonify({"error": "Failed to fetch user profile"}), 500
