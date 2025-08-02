"""
Socket.IO event handlers for BeatSync Mixer.
Handles real-time communication for queue, voting, and chat.
"""

from flask import session, request
from flask_socketio import SocketIO, emit
from db import get_db, QueueItem, Vote, ChatMessage
from cache import get_currently_playing, get_queue_snapshot, update_queue_snapshot


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
            user_id = session.get("user_id", "unknown")
            display_name = session.get("display_name", "Unknown")
            
            if not user_role or user_role not in ["host", "listener"]:
                emit("error", {"message": "Authentication required"})
                return
            
            print(f"[CONNECTION] User connected: {display_name} (role: {user_role}, user_id: {user_id}, sid: {request.sid})")
            emit("connected", {"role": user_role, "message": "Connected successfully"})
            
        except Exception as e:
            print(f"Connection error: {e}")
            emit("error", {"message": "Connection failed"})
        
        # Send initial data in smaller chunks to avoid timeouts
        try:
            import threading
            from flask import current_app
            # Pass the app context to the background thread
            app = current_app._get_current_object()
            threading.Thread(target=send_initial_data_async, args=(request.sid, app), daemon=True).start()
            
        except Exception as e:
            print(f"Error starting initial data thread: {e}")
            emit("error", {"message": "Error loading initial data"})


    @socketio.on("disconnect")
    def handle_disconnect(reason=None):
        """Handle client disconnection"""
        user_name = session.get("display_name", "Unknown")
        user_id = session.get("user_id", "unknown")
        print(f"[DISCONNECTION] User disconnected: {user_name} (user_id: {user_id}, sid: {request.sid}, reason: {reason})")


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
                
                # Update queue snapshot in cache after adding new item
                update_queue_snapshot()
                
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
        import uuid
        vote_event_id = str(uuid.uuid4())[:8]  # Short unique ID for this vote event
        client_vote_id = data.get("client_vote_id", "unknown")
        
        try:
            # Check if user is authenticated (has any role)
            if not session.get("role"):
                emit("error", {"message": "You must be logged in to vote"})
                return
            
            track_uri = data.get("track_uri")
            vote_type = data.get("vote")  # 'up' or 'down'
            user_id = session.get("user_id", "anonymous")  # Use session user_id
            role = session.get("role", "unknown")
            
            if vote_type not in ["up", "down"]:
                emit("error", {"message": "Invalid vote type"})
                return

            if not track_uri:
                emit("error", {"message": "Invalid track URI"})
                return

            print(f"[VOTE {vote_event_id}] START: client_id={client_vote_id}, user_id={user_id}, role={role}, track_uri={track_uri}, vote_type={vote_type}")
            print(f"[VOTE {vote_event_id}] Session ID: {session.get('_permanent', 'no-session')}")
            print(f"[VOTE {vote_event_id}] Request SID: {request.sid}")

            with get_db() as db:
                # Use a single transaction to get current counts and add the new vote atomically
                try:
                    # Get vote counts BEFORE adding the new vote using a single query per type
                    up_votes_before = (
                        db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "up").count()
                    )
                    down_votes_before = (
                        db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "down").count()
                    )
                    
                    print(f"[VOTE {vote_event_id}] BEFORE: {up_votes_before} up, {down_votes_before} down")
                    
                    # Add the new vote
                    vote = Vote(track_uri=track_uri, vote_type=vote_type, user_id=user_id)
                    db.add(vote)
                    db.flush()  # Flush to assign ID but don't commit yet
                    
                    # Calculate updated vote counts for this track AFTER adding (single query per type)
                    up_votes_after = (
                        db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "up").count()
                    )
                    down_votes_after = (
                        db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "down").count()
                    )
                    
                    print(f"[VOTE {vote_event_id}] AFTER: {up_votes_after} up, {down_votes_after} down")
                    
                    # Verify the vote was actually added (sanity check)
                    expected_increase = 1 if vote_type == "up" else 0
                    actual_increase = up_votes_after - up_votes_before
                    
                    if vote_type == "up" and actual_increase != 1:
                        print(f"[VOTE {vote_event_id}] WARNING: Expected up vote increase of 1, got {actual_increase}")
                    elif vote_type == "down" and (down_votes_after - down_votes_before) != 1:
                        print(f"[VOTE {vote_event_id}] WARNING: Expected down vote increase of 1, got {down_votes_after - down_votes_before}")
                    
                    # Commit the transaction
                    db.commit()
                    
                    # Update queue snapshot in cache after vote changes
                    update_queue_snapshot()
                    
                    print(f"[VOTE {vote_event_id}] SUCCESS: Added {vote_type} vote from {user_id}")
                    
                    # Broadcast updated vote counts to all connected clients
                    socketio.emit(
                        "vote_updated", 
                        {"track_uri": track_uri, "up_votes": up_votes_after, "down_votes": down_votes_after}
                    )
                    
                except Exception as db_error:
                    print(f"[VOTE {vote_event_id}] DB ERROR: {db_error}")
                    db.rollback()
                    raise db_error
                
        except Exception as e:
            print(f"[VOTE {vote_event_id}] ERROR: {e}")
            import traceback
            traceback.print_exc()
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


def send_initial_data_async(client_sid, app):
    """Send initial data asynchronously to avoid blocking the connection"""
    with app.app_context():
        try:
            # Send currently playing track first if exists
            currently_playing = get_currently_playing(app)
            if currently_playing:
                print(f"Sending currently playing track to {client_sid}: {currently_playing['track_name']}")
                if currently_playing.get('is_playing', False):
                    socketio.emit(
                        "playback_started",
                        {
                            "track_uri": currently_playing['track_uri'],
                            "track_name": currently_playing['track_name'],
                            "device_id": currently_playing.get('device_id'),
                            "is_playing": True
                        },
                        room=client_sid
                    )
                else:
                    socketio.emit(
                        "playback_paused",
                        {
                            "track_uri": currently_playing['track_uri'],
                            "track_name": currently_playing['track_name'],
                            "device_id": currently_playing.get('device_id'),
                            "is_playing": False
                        },
                        room=client_sid
                    )
            
            # Try to get queue from cache first, if not available, build it from database
            queue_data = get_queue_snapshot(app)
            if not queue_data:
                print(f"No queue snapshot in cache, building from database for {client_sid}")
                queue_data = update_queue_snapshot(app)
            
            print(f"Sending {len(queue_data)} queue items to {client_sid}")
            
            # Send queue items and vote counts
            for item in queue_data:
                # Send queue item
                socketio.emit(
                    "queue_updated",
                    {
                        "track_uri": item['track_uri'],
                        "track_name": item['track_name'],
                        "timestamp": item['timestamp'],
                    },
                    room=client_sid
                )
                
                # Send vote counts if there are any votes
                up_votes = item.get('up_votes', 0)
                down_votes = item.get('down_votes', 0)
                if up_votes > 0 or down_votes > 0:
                    socketio.emit(
                        "vote_updated",
                        {
                            "track_uri": item['track_uri'],
                            "up_votes": up_votes,
                            "down_votes": down_votes
                        },
                        room=client_sid
                    )
                    
        except Exception as e:
            print(f"Error sending initial data: {e}")
            socketio.emit("error", {"message": "Error loading initial data"}, room=client_sid)
