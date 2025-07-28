import os
import datetime
import requests
import pylast
from dotenv import load_dotenv
from flask import Flask, jsonify, session, redirect, url_for, send_from_directory, abort
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from authlib.integrations.flask_client import OAuth
from flask_socketio import SocketIO, emit

load_dotenv()

# Initialize Flask app with static folder
app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET")


# OAuth setup for Spotify
oauth = OAuth(app)
oauth.register(
    name="spotify",
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    access_token_url="https://accounts.spotify.com/api/token",
    authorize_url="https://accounts.spotify.com/authorize",
    client_kwargs={"scope": "user-read-playback-state streaming playlist-read-private"},
)


# Last.fm API setup
lastfm = pylast.LastFMNetwork(
    api_key=os.getenv("LASTFM_API_KEY"),
    api_secret=os.getenv("LASTFM_SHARED_SECRET")
)


# Database setup for persistent queue
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///beatsync.db")
engine = create_engine(DATABASE_URL, echo=False)
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
    return oauth.spotify.authorize_redirect(os.getenv("SPOTIFY_REDIRECT_URI"))


# Callback route
@app.route("/callback")
def callback():
    token = oauth.spotify.authorize_access_token()
    session["spotify_token"] = token
    oauth.spotify.token = token
    
    # Fetch user profile to assign role
    try:
        user_response = oauth.spotify.get("https://api.spotify.com/v1/me", token=token)
        user_data = user_response.json()
        user_id = user_data.get("id")
        
        # Hard-code host role for specific Spotify account (replace with your Spotify ID)
        # You can find your Spotify ID by visiting: https://open.spotify.com/user/YOUR_USER_ID
        HOST_SPOTIFY_ID = os.getenv("HOST_SPOTIFY_ID", "victordao")  # Default fallback
        
        if user_id == HOST_SPOTIFY_ID:
            session["role"] = "host"
            session["user_id"] = user_id
            session["display_name"] = user_data.get("display_name", user_id)
        else:
            session["role"] = "listener"
            session["user_id"] = user_id
            session["display_name"] = user_data.get("display_name", user_id)
        
        print(f"User {user_id} logged in as {session['role']}")
        
    except Exception as e:
        print(f"Error fetching user profile: {e}")
        # Default to listener role if we can't fetch user info
        session["role"] = "listener"
        session["user_id"] = "unknown"
        session["display_name"] = "Unknown User"
    
    return redirect("/")


# Fetch playlists
@app.route("/playlists")
def playlists():
    token = session.get("spotify_token")
    if not token:
        return redirect(url_for("login"))
    resp = oauth.spotify.get("https://api.spotify.com/v1/me/playlists", token=token)
    return jsonify(resp.json())


# Fetch tracks for a given playlist
@app.route("/playlists/<playlist_id>/tracks")
def playlist_tracks(playlist_id):
    token = session.get("spotify_token")
    if not token:
        return redirect(url_for("login"))
    resp = oauth.spotify.get(
        f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", token=token
    )
    return jsonify(resp.json())


# Get Last.fm recommendations for a queued track
@app.route("/recommend/<track_uri>")
def recommend(track_uri):
    """Get similar tracks from Last.fm for a queued track"""
    # Lookup stored track_name
    db = SessionLocal()
    try:
        item = db.query(QueueItem).filter_by(track_uri=track_uri).first()
        if not item:
            return jsonify({"error": "Track not found"}), 404
        
        # Parse artist and title from track_name (expected format: "Artist — Title")
        if " — " not in item.track_name:
            return jsonify({"error": "Invalid track name format"}), 400
        
        artist, title = item.track_name.split(" — ", 1)
        
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
            return jsonify({"error": f"Last.fm API error: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
            
    finally:
        db.close()


# Serve front-end
@app.route("/")
def index():
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


# Socket.IO setup
async_mode = os.getenv("FLASK_SOCKETIO_ASYNC_MODE", "eventlet")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode)


@socketio.on("connect")
def handle_connect(auth):
    print("Client connected")
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


@socketio.on("queue_add")
def handle_queue_add(data):
    """Add track to queue - Host only"""
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
        emit(
            "queue_updated",
            {
                "track_uri": qi.track_uri,
                "track_name": qi.track_name,
                "timestamp": qi.timestamp.isoformat() if qi.timestamp else None,
            },
        )
    finally:
        db.close()


@socketio.on("vote_add")
def handle_vote_add(data):
    """Handle voting on tracks - Available to all authenticated users"""
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
        emit(
            "vote_updated", {"track_uri": track_uri, "up_votes": up_votes, "down_votes": down_votes}
        )

    finally:
        db.close()


@socketio.on("chat_message")
def handle_chat_message(data):
    """Handle chat messages - Available to all authenticated users"""
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
        emit(
            "chat_message",
            {
                "user": chat_msg.user,
                "message": chat_msg.message,
                "timestamp": chat_msg.timestamp.isoformat() if chat_msg.timestamp else None,
            },
        )

    finally:
        db.close()


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


if __name__ == "__main__":
    # TODO: In production, use a proper WSGI server like Gunicorn
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
