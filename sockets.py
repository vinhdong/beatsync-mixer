"""
Socket.IO event handlers for BeatSync Mixer.
Handles real-time communication for queue, voting, and chat.
"""

from flask import session
from flask_socketio import SocketIO, emit
from db import get_db, QueueItem, Vote, ChatMessage


# SocketIO instance will be imported from app factory
socketio = None


def init_socketio(app):
    """Initialize Socket.IO with the Flask app"""
    global socketio
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
    
    # Register event handlers
    register_handlers()
    
    return socketio


def register_handlers():
    """Register all Socket.IO event handlers"""
    
    @socketio.on("connect")
    def handle_connect(auth):
        """Handle client connection"""
        try:
            user_role = session.get("role")
            if not user_role or user_role not in ["host", "listener"]:
                emit("error", {"message": "Authentication required"})
                return
            
            print(f"User connected: {session.get('display_name', 'Unknown')} ({user_role})")
            emit("connected", {"role": user_role, "message": "Connected successfully"})
            
        except Exception as e:
            print(f"Connection error: {e}")
            emit("error", {"message": "Connection failed"})
        
        # Send initial data in smaller chunks to avoid timeouts
        try:
            import threading
            threading.Thread(target=send_initial_data_async, args=(session.sid,), daemon=True).start()
            
        except Exception as e:
            print(f"Error starting initial data thread: {e}")
            emit("error", {"message": "Error loading initial data"})


    @socketio.on("disconnect")
    def handle_disconnect(reason=None):
        """Handle client disconnection"""
        user_name = session.get("display_name", "Unknown")
        print(f"User disconnected: {user_name} (reason: {reason})")


    @socketio.on_error_default
    def default_error_handler(e):
        """Handle Socket.IO errors"""
        print(f"Socket.IO error: {e}")
        return False


    @socketio.on("queue_add")
    def handle_queue_add(data):
        """Add track to queue - Host and Listener allowed"""
        try:
            # Check if user is authenticated (has any role)
            if not session.get("role"):
                emit("error", {"message": "You must be logged in to add tracks"})
                return
            
            track_uri = data.get("track_uri")
            track_name = data.get("track_name") if data else None
            
            if not track_uri or not track_name:
                emit("error", {"message": "Missing track information"})
                return
            
            with get_db() as db:
                # Add track to queue
                queue_item = QueueItem(track_uri=track_uri, track_name=track_name.strip())
                db.add(queue_item)
                
                # Broadcast to all connected users
                socketio.emit(
                    "queue_updated",
                    {
                        "track_uri": track_uri,
                        "track_name": track_name.strip(),
                        "timestamp": queue_item.timestamp.isoformat() if queue_item.timestamp else None
                    }
                )
                
                emit("queue_add_success", {
                    "message": f"Added '{track_name}' to queue",
                    "track_uri": track_uri
                })
                
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

            with get_db() as db:
                # First, remove any existing votes from this user for this track
                existing_votes = db.query(Vote).filter(
                    Vote.track_uri == track_uri,
                    Vote.user_id == user_id
                ).all()
                
                for vote in existing_votes:
                    db.delete(vote)
                
                # Add the new vote
                vote = Vote(track_uri=track_uri, vote_type=vote_type, user_id=user_id)
                db.add(vote)
                
                # Calculate updated vote counts for this track
                up_votes = (
                    db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "up").count()
                )
                down_votes = (
                    db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "down").count()
                )
                
                print(f"Vote processed: {user_id} voted {vote_type} on {track_uri}. New counts: {up_votes} up, {down_votes} down")
                
                # Broadcast updated vote counts
                socketio.emit(
                    "vote_updated", 
                    {"track_uri": track_uri, "up_votes": up_votes, "down_votes": down_votes}
                )
                
        except Exception as e:
            print(f"Error in vote_add: {e}")
            emit("error", {"message": "Failed to process vote"})


    @socketio.on("chat_message")
    def handle_chat_message(data):
        """Handle chat messages - Available to all authenticated users"""
        try:
            if not session.get("role"):
                emit("error", {"message": "You must be logged in to chat"})
                return
            
            user = session.get("display_name", "Anonymous")
            message = data.get("message", "")
            
            if not message.strip():
                emit("error", {"message": "Message cannot be empty"})
                return
            
            with get_db() as db:
                chat_msg = ChatMessage(user=user, message=message.strip())
                db.add(chat_msg)
                
                socketio.emit(
                    "chat_message",
                    {
                        "user": chat_msg.user,
                        "message": chat_msg.message,
                        "timestamp": chat_msg.timestamp.isoformat() if chat_msg.timestamp else None,
                    }
                )
                
        except Exception as e:
            print(f"Error in chat_message: {e}")
            emit("error", {"message": "Failed to send message"})


def send_initial_data_async(client_sid):
    """Send initial data asynchronously to avoid blocking the connection"""
    try:
        with get_db() as db:
            # Send queue items
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
                
    except Exception as e:
        print(f"Error sending initial data: {e}")
        socketio.emit("error", {"message": "Error loading initial data"}, room=client_sid)
