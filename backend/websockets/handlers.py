"""
Socket.IO event handlers for BeatSync Mixer.
Handles real-time communication for queue, voting, and chat.
"""

from datetime import datetime, timezone
from flask import session, request
from flask_socketio import SocketIO, emit
from backend.models.models import get_db, QueueItem, Vote, ChatMessage
from backend.utils.cache import get_currently_playing, get_queue_snapshot, update_queue_snapshot


# SocketIO instance will be imported from app factory
socketio = None

# Track active listeners for numbering
active_listeners = {}  # {session_id: listener_number}
next_listener_number = 1


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


def assign_listener_number(session_id):
    """Assign a listener number to a new listener"""
    global next_listener_number, active_listeners
    
    # Find the smallest available number
    used_numbers = set(active_listeners.values())
    listener_number = 1
    while listener_number in used_numbers:
        listener_number += 1
    
    active_listeners[session_id] = listener_number
    print(f"Assigned listener number {listener_number} to session {session_id}")
    return listener_number


def release_listener_number(session_id):
    """Release a listener number when a listener disconnects"""
    global active_listeners
    
    if session_id in active_listeners:
        listener_number = active_listeners.pop(session_id)
        print(f"Released listener number {listener_number} from session {session_id}")
        return listener_number
    return None


def get_listener_display_name(listener_number):
    """Generate display name for a listener"""
    return f"Listener {listener_number}"


def register_handlers():
    """Register all Socket.IO event handlers"""
    
    @socketio.on("connect")
    def handle_connect(auth):
        """Handle client connection"""
        try:
            user_role = session.get("role")
            user_id = session.get("user_id", "unknown")
            display_name = session.get("display_name", "Unknown")
            
            if not user_role or user_role not in ["host", "listener", "guest"]:
                emit("error", {"message": "Authentication required"})
                return
            
            print(f"[CONNECTION] User connected: {display_name} (role: {user_role}, user_id: {user_id}, sid: {request.sid})")
            
            # For listeners that don't have a number yet, assign one now
            if user_role == "listener" and not session.get("listener_number"):
                listener_number = assign_listener_number(request.sid)
                display_name = get_listener_display_name(listener_number)
                session["listener_number"] = listener_number
                session["display_name"] = display_name
                print(f"[CONNECTION] Assigned listener number {listener_number} to sid {request.sid}")
                
                # Notify the client of their new display name
                emit("display_name_updated", {"display_name": display_name})
            
            emit("connected", {"role": user_role, "message": "Connected successfully"})
            
        except Exception as e:
            print(f"Connection error: {e}")
            emit("error", {"message": "Connection failed"})
        
        # Send initial data in smaller chunks to avoid timeouts
        try:
            import threading
            from flask import current_app
            # Pass the app context and user role to the background thread
            app = current_app._get_current_object()
            threading.Thread(target=send_initial_data_async, args=(request.sid, app, user_role), daemon=True).start()
            
        except Exception as e:
            print(f"Error starting initial data thread: {e}")
            emit("error", {"message": "Error loading initial data"})


    @socketio.on("disconnect")
    def handle_disconnect(reason=None):
        """Handle client disconnection"""
        user_name = session.get("display_name", "Unknown")
        user_id = session.get("user_id", "unknown")
        user_role = session.get("role", "unknown")
        print(f"[DISCONNECTION] User disconnected: {user_name} (user_id: {user_id}, role: {user_role}, sid: {request.sid}, reason: {reason})")
        
        # Release listener number on disconnect for listeners
        if user_role == "listener":
            released_number = release_listener_number(request.sid)
            if released_number:
                print(f"[DISCONNECTION] Released listener number {released_number}")


    @socketio.on_error_default
    def default_error_handler(e):
        """Default error handler for all events"""
        print(f"[SOCKET ERROR] Error occurred: {e}")
        print(f"[SOCKET ERROR] Event: {request.event}")
        print(f"[SOCKET ERROR] Namespace: {request.namespace}")
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
                emit("error", {
                    "message": "You must be logged in to vote",
                    "client_vote_id": client_vote_id
                })
                return
            
            track_uri = data.get("track_uri")
            vote_type = data.get("vote")  # 'up' or 'down'
            user_id = session.get("user_id", "anonymous")  # Use session user_id
            role = session.get("role", "unknown")
            
            if vote_type not in ["up", "down"]:
                emit("error", {
                    "message": "Invalid vote type",
                    "client_vote_id": client_vote_id
                })
                return

            if not track_uri:
                emit("error", {
                    "message": "Invalid track URI",
                    "client_vote_id": client_vote_id
                })
                return

            print(f"[VOTE {vote_event_id}] START: client_id={client_vote_id}, user_id={user_id}, role={role}, track_uri={track_uri}, vote_type={vote_type}")
            print(f"[VOTE {vote_event_id}] Session ID: {session.get('_permanent', 'no-session')}")
            print(f"[VOTE {vote_event_id}] Request SID: {request.sid}")

            with get_db() as db:
                # Use a single transaction to add the vote
                try:
                    # Always add a new vote (allow multiple votes from same user)
                    print(f"[VOTE {vote_event_id}] ADDING: User {user_id} voting {vote_type}")
                    vote = Vote(track_uri=track_uri, vote_type=vote_type, user_id=user_id)
                    db.add(vote)
                    
                    # Flush to apply changes before counting
                    db.flush()
                    
                    # Calculate updated vote counts for this track (single query per type)
                    up_votes_after = (
                        db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "up").count()
                    )
                    down_votes_after = (
                        db.query(Vote).filter(Vote.track_uri == track_uri, Vote.vote_type == "down").count()
                    )
                    
                    print(f"[VOTE {vote_event_id}] FINAL: {up_votes_after} up, {down_votes_after} down")
                    print(f"[VOTE {vote_event_id}] SENDING: track_uri={track_uri}, up_votes={up_votes_after}, down_votes={down_votes_after}")
                    
                    # Update queue snapshot in cache after vote changes
                    update_queue_snapshot()
                    
                    print(f"[VOTE {vote_event_id}] SUCCESS: Added {vote_type} vote from {user_id}")
                    
                    # Broadcast updated vote counts to all connected clients
                    socketio.emit(
                        "vote_updated", 
                        {"track_uri": track_uri, "up_votes": up_votes_after, "down_votes": down_votes_after}
                    )
                    
                    # Send success response to the voting client
                    emit("vote_success", {"client_vote_id": client_vote_id})

                except Exception as db_error:
                    print(f"[VOTE {vote_event_id}] DB ERROR: {db_error}")
                    raise db_error
                
        except Exception as e:
            print(f"[VOTE {vote_event_id}] ERROR: {e}")
            import traceback
            traceback.print_exc()
            emit("error", {
                "message": "Failed to process vote",
                "client_vote_id": client_vote_id
            })


    @socketio.on("chat_message")
    def handle_chat_message(data):
        """Handle chat messages - Available to all authenticated users"""
        try:
            if not session.get("role"):
                emit("error", {"message": "You must be logged in to chat"})
                return
            
            # Try session first, then frontend data, then fallback
            user = session.get("display_name") or data.get("user", "Anonymous")
            message = data.get("message", "")
            
            if not message.strip():
                emit("error", {"message": "Message cannot be empty"})
                return
            
            with get_db() as db:
                chat_msg = ChatMessage(user=user, message=message.strip())
                db.add(chat_msg)
                
                response_data = {
                    "user": chat_msg.user,
                    "message": chat_msg.message,
                    "timestamp": chat_msg.timestamp.replace(tzinfo=timezone.utc).isoformat() if chat_msg.timestamp else None,
                }
                
                socketio.emit("chat_message", response_data)
                
        except Exception as e:
            print(f"Error in chat_message: {e}")
            emit("error", {"message": "Failed to send message"})


    @socketio.on("load_chat_history")
    def handle_load_chat_history():
        """Load recent chat messages for a user"""
        try:
            with get_db() as db:
                # Get last 50 messages
                recent_messages = db.query(ChatMessage).order_by(ChatMessage.timestamp.desc()).limit(50).all()
                
                # Reverse to show oldest first
                recent_messages.reverse()
                
                messages_data = [
                    {
                        "user": msg.user,
                        "message": msg.message,
                        "timestamp": msg.timestamp.replace(tzinfo=timezone.utc).isoformat() if msg.timestamp else None,
                    }
                    for msg in recent_messages
                ]
                
                emit("chat_history", {"messages": messages_data})
                
        except Exception as e:
            print(f"Error loading chat history: {e}")
            emit("error", {"message": "Failed to load chat history"})


def send_initial_data_async(client_sid, app, user_role):
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
            
            # For listeners, filter out the currently playing track from the queue
            if user_role == "listener" and currently_playing:
                currently_playing_uri = currently_playing['track_uri']
                queue_data = [item for item in queue_data if item['track_uri'] != currently_playing_uri]
                print(f"Filtered out currently playing track for listener. Queue has {len(queue_data)} remaining items")
            
            print(f"Sending {len(queue_data)} queue items to {client_sid} (role: {user_role})")
            
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


    @socketio.on("restart_session")
    def handle_restart_session():
        """Handle restart session request via socket - Only available to hosts"""
        try:
            if session.get("role") != "host":
                emit("error", {"message": "Only hosts can restart sessions"})
                return
                
            import os
            from backend.models.models import Vote, QueueItem, ChatMessage
            
            # Remove host file
            host_file = 'current_host.txt'
            if os.path.exists(host_file):
                os.remove(host_file)
            
            # Clear the queue, votes, chat, and currently playing
            with get_db() as db:
                # Clear all votes
                votes_deleted = db.query(Vote).delete()
                
                # Clear all queue items
                queue_deleted = db.query(QueueItem).delete()
                
                # Clear all chat messages
                chat_deleted = db.query(ChatMessage).delete()
                
                db.commit()
            
            # Clear all cached data
            try:
                from flask import current_app
                cache = current_app.cache
                cache.clear()
                
                # Also clear in-memory cache
                from backend.utils.cache import clear_in_memory_cache
                clear_in_memory_cache()
                
            except Exception as e:
                pass  # Silently handle cache clearing errors
            
            # Emit session restart to all clients
            socketio.emit("session_restarted", {
                "message": "Session has been restarted. Please refresh your page.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            emit("error", {"message": "Failed to restart session"})
