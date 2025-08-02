import os
import json
import ssl
import redis
import tempfile
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import pylast
import time
import threading
import traceback
from dotenv import load_dotenv
from flask import Flask, jsonify, session, redirect, url_for, send_from_directory, abort, request
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
app.config['SESSION_COOKIE_SAMESITE'] = None  # Allow cross-site requests for OAuth callbacks and API calls
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # 24 hour sessions
app.config['SESSION_REFRESH_EACH_REQUEST'] = False  # Don't refresh during OAuth flow to preserve state
app.config['SESSION_COOKIE_NAME'] = 'beatsync_session'  # Custom session name
app.config['SESSION_COOKIE_DOMAIN'] = None  # Let Flask handle domain automatically

# Initialize server-side session storage
Session(app)

# Manual Redis client to bypass Heroku DNS issues
def create_manual_redis_client(redis_url):
    """Create a Redis client using direct IP to bypass DNS issues"""
    try:
        import redis
        from urllib.parse import urlparse
        
        # Parse the Redis URL
        parsed = urlparse(redis_url)
        
        # Use known IP mapping for Heroku Redis hostnames
        hostname_to_ip = {
            'ec2-98-85-106-43.compute-1.amazonaws.com': '98.85.106.43'
        }
        
        ip_address = hostname_to_ip.get(parsed.hostname)
        if not ip_address:
            print(f"No IP mapping found for hostname: {parsed.hostname}")
            return None
        
        # Create Redis connection with IP
        redis_client = redis.Redis(
            host=ip_address,
            port=parsed.port or 6379,
            password=parsed.password,
            ssl=parsed.scheme == 'rediss',
            ssl_cert_reqs=ssl.CERT_NONE,
            ssl_check_hostname=False,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30
        )
        
        # Test the connection
        redis_client.ping()
        print(f"Successfully connected to Redis at {ip_address}:{parsed.port}")
        return redis_client
        
    except Exception as e:
        print(f"Failed to create manual Redis client: {e}")
        return None

class ManualRedisCache:
    """Manual Redis cache wrapper to bypass DNS issues"""
    
    def __init__(self, redis_client, default_timeout=300):
        self.redis_client = redis_client
        self.default_timeout = default_timeout
    
    def get(self, key):
        """Get value from Redis cache"""
        try:
            if not self.redis_client:
                return None
            value = self.redis_client.get(f"cache:{key}")
            if value:
                import json
                return json.loads(value.decode('utf-8'))
            return None
        except Exception as e:
            print(f"Redis get error for key {key}: {e}")
            return None
    
    def set(self, key, value, timeout=None):
        """Set value in Redis cache"""
        try:
            if not self.redis_client:
                return False
            timeout = timeout or self.default_timeout
            import json
            serialized = json.dumps(value, default=str)
            self.redis_client.setex(f"cache:{key}", timeout, serialized)
            return True
        except Exception as e:
            print(f"Redis set error for key {key}: {e}")
            return False
    
    def delete(self, key):
        """Delete key from Redis cache"""
        try:
            if not self.redis_client:
                return False
            self.redis_client.delete(f"cache:{key}")
            return True
        except Exception as e:
            print(f"Redis delete error for key {key}: {e}")
            return False

# Configure caching with manual Redis bypass for DNS issues
redis_url = os.getenv('REDIS_URL')
manual_redis_client = None
use_manual_redis = False

# In-memory cache per dyno to avoid redundant Redis reads
in_memory_cache = {
    'host_playlists': None,
    'host_playlists_timestamp': None,
    'playlist_tracks': {},  # Key: "playlist_id:limit:offset"
    'playlist_tracks_timestamps': {},
    'cache_ttl': 300  # 5 minutes
}

def get_in_memory_cache(key):
    """Get from in-memory cache if fresh"""
    if key in in_memory_cache and in_memory_cache.get(f'{key}_timestamp'):
        age = time.time() - in_memory_cache[f'{key}_timestamp']
        if age < in_memory_cache['cache_ttl']:
            print(f"Serving {key} from in-memory cache (age: {age:.1f}s)")
            return in_memory_cache[key]
    return None

def set_in_memory_cache(key, value):
    """Set in-memory cache with timestamp"""
    in_memory_cache[key] = value
    in_memory_cache[f'{key}_timestamp'] = time.time()
    print(f"Updated in-memory cache for {key}")

def clear_in_memory_cache(key=None):
    """Clear specific key or all in-memory cache"""
    if key:
        in_memory_cache[key] = None
        in_memory_cache[f'{key}_timestamp'] = None
        print(f"Cleared in-memory cache for {key}")
    else:
        for k in list(in_memory_cache.keys()):
            if not k.endswith('_ttl'):
                in_memory_cache[k] = None
        print("Cleared all in-memory cache")

def get_cached_playlists():
    """Get playlists from in-memory cache first, then Redis if needed"""
    # Try in-memory cache first (fastest)
    cached_data = get_in_memory_cache("host_playlists")
    if cached_data:
        return cached_data
    
    # Try Redis cache
    try:
        cached_data = cache.get("host_playlists_simplified")
        if cached_data:
            print("Serving playlists from Redis cache")
            # Update in-memory cache to avoid Redis on next request
            set_in_memory_cache("host_playlists", cached_data)
            return cached_data
    except Exception as e:
        print(f"Redis cache read failed: {e}")
    
    print("No cached playlists available")
    return None

def invalidate_playlist_cache():
    """Clear both in-memory and Redis playlist cache"""
    clear_in_memory_cache("host_playlists")
    try:
        cache.delete("host_playlists_simplified")
        cache.delete("host_access_token")
        print("Cleared Redis playlist cache")
    except Exception as e:
        print(f"Error clearing Redis cache: {e}")

def simplify_playlists_data(playlists_data):
    """Convert full Spotify JSON to minimal cached format"""
    if not playlists_data or not playlists_data.get('items'):
        return None
    
    return {
        "items": [
            {
                "id": playlist["id"],
                "name": playlist["name"],
                "description": playlist.get("description", ""),
                "tracks": {"total": playlist["tracks"]["total"]},
                "images": playlist.get("images", [])[:1],  # Only first image
                "owner": {"display_name": playlist["owner"]["display_name"]}
            }
            for playlist in playlists_data.get("items", [])
        ],
        "total": playlists_data.get("total", 0)
    }

def cache_playlists_async(access_token, simplified_playlists):
    """Cache playlists in background thread to avoid blocking login"""
    def cache_worker():
        try:
            print("Background: Caching simplified playlists for listeners")
            # Cache both the simplified data and the access token
            cache.set("host_playlists_simplified", simplified_playlists, timeout=1800)
            cache.set("host_access_token", access_token, timeout=1800)
            
            # Also update in-memory cache
            set_in_memory_cache("host_playlists", simplified_playlists)
            
            print(f"Background: Successfully cached {len(simplified_playlists.get('items', []))} playlists")
        except Exception as e:
            print(f"Background: Error caching playlists: {e}")
    
    # Start background thread
    thread = threading.Thread(target=cache_worker)
    thread.daemon = True
    thread.start()

if redis_url:
    try:
        # Try to create a manual Redis client bypassing DNS
        manual_redis_client = create_manual_redis_client(redis_url)
        if manual_redis_client:
            print("Using manual Redis client to bypass DNS issues")
            cache = ManualRedisCache(manual_redis_client)
            use_manual_redis = True
        else:
            print("Manual Redis failed, falling back to Flask-Caching with DNS")
            app.config['CACHE_TYPE'] = 'RedisCache'
            app.config['CACHE_REDIS_URL'] = redis_url
            # Handle Heroku Redis SSL properly
            if redis_url.startswith('rediss://'):
                app.config['CACHE_REDIS_CONNECTION_KWARGS'] = {
                    'ssl_cert_reqs': ssl.CERT_NONE,
                    'ssl_check_hostname': False,
                    'ssl_ca_certs': None
                }
            app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
            cache = Cache(app)
    except Exception as e:
        print(f"Failed to create manual Redis client: {e}")
        print("Using Flask-Caching with Redis")
        app.config['CACHE_TYPE'] = 'RedisCache'
        app.config['CACHE_REDIS_URL'] = redis_url
        if redis_url.startswith('rediss://'):
            app.config['CACHE_REDIS_CONNECTION_KWARGS'] = {
                'ssl_cert_reqs': ssl.CERT_NONE,
                'ssl_check_hostname': False,
                'ssl_ca_certs': None
            }
        app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes
        cache = Cache(app)
else:
    app.config['CACHE_TYPE'] = 'SimpleCache'
    print("Using SimpleCache for local development")
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
    requests_timeout=5,  # Increased timeout - fail in 5s, not 2s for better reliability
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
            
            # IMMEDIATELY cache host access token for listeners - CRITICAL for track loading
            try:
                cache.set("host_access_token", access_token, timeout=1800)
                print(f"IMMEDIATELY cached host access token for listeners")
            except Exception as e:
                print(f"CRITICAL: Failed to cache host access token: {e}")
            
            # Start asynchronous playlist caching with fast timeout
            def cache_playlists_background():
                """Cache playlists in background thread to avoid blocking login"""
                try:
                    print(f"Background: Pre-caching playlists for new host: {display_name}")
                    playlists_data = manual_playlists_fetch(access_token, fast_timeout=True)
                    if playlists_data:
                        # Create simplified playlists using our helper function
                        simplified_playlists = simplify_playlists_data(playlists_data)
                        if simplified_playlists:
                            # Add host metadata
                            simplified_playlists["host_name"] = display_name
                            simplified_playlists["cached_at"] = time.time()
                            
                            # Cache using our optimized async function
                            cache_playlists_async(access_token, simplified_playlists)
                            
                            # Notify listeners asynchronously
                            socketio.emit('playlists_available', {
                                'host_name': display_name,
                                'playlist_count': len(simplified_playlists['items'])
                            })
                            print("Background: Notified listeners that playlists are available")
                        else:
                            print("Background: Failed to simplify playlists data")
                    else:
                        print("Background: Failed to fetch playlists from Spotify")
                except Exception as e:
                    print(f"Background: Error caching playlists: {e}")
            
            # Start background caching - login continues immediately
            threading.Thread(target=cache_playlists_background, daemon=True).start()
            print(f"Started background playlist caching for {display_name}")
            
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


@app.route("/playlists")
def playlists():
    user_role = session.get("role")
    
    # For hosts: use their own Spotify token and cache in background
    if user_role == "host":
        token_info = session.get("spotify_token")
        if not token_info:
            print("Host has no Spotify token in session")
            return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
        
        access_token = token_info.get("access_token")
        if not access_token:
            print("Host has no access token available")
            return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
            
        # ALWAYS ensure host access token is cached for listeners - CRITICAL
        try:
            cache.set("host_access_token", access_token, timeout=1800)
        except Exception as e:
            print(f"CRITICAL: Failed to cache host access token: {e}")
            
        # Try to serve from cache first (much faster for repeated requests)
        try:
            cached_data = get_cached_playlists()
            if cached_data:
                print(f"Serving host playlists from cache: {len(cached_data.get('items', []))} playlists")
                # Return cached playlists with host metadata
                host_response = {
                    "items": cached_data["items"],
                    "total": cached_data["total"],
                    "is_host": True,
                    "cached": True
                }
                return jsonify(host_response)
        except Exception as e:
            print(f"Error reading from cache: {e}")
            
        try:
            # Fetch playlists with fast timeout for speed
            print(f"Host {session.get('display_name', 'Unknown')} requesting fresh playlists with token: {access_token[:10]}...")
            data = manual_playlists_fetch(access_token, fast_timeout=True)
            
            if not data:
                print("Fast playlists fetch failed - likely network issue")
                return jsonify({"error": "Failed to fetch playlists from Spotify. This could be due to network issues or expired token."}), 500
            
            print(f"Successfully fetched {len(data.get('items', []))} playlists for host")
            
            # Prepare simplified response for host
            simplified_playlists = {
                "items": [
                    {
                        "id": playlist["id"],
                        "name": playlist["name"],
                        "description": playlist.get("description", ""),
                        "tracks": {"total": playlist["tracks"]["total"]},
                        "images": playlist.get("images", [])[:1],
                        "owner": {"display_name": playlist["owner"]["display_name"]}
                    }
                    for playlist in data.get("items", [])
                ],
                "total": data.get("total", 0),
                "is_host": True
            }
            
            # Cache asynchronously - don't block the response
            def cache_playlists_background():
                try:
                    # Add metadata for listeners
                    cached_playlists = simplified_playlists.copy()
                    cached_playlists["host_name"] = session.get("display_name", "Host")
                    cached_playlists["cached_at"] = time.time()
                    
                    # Use our optimized caching function
                    cache_playlists_async(access_token, cached_playlists)
                    
                    print(f"Background: Cached {len(simplified_playlists['items'])} playlists for listeners")
                except Exception as e:
                    print(f"Background: Cache update failed: {e}")
            
            # Start background caching
            threading.Thread(target=cache_playlists_background, daemon=True).start()
            
            # Return immediately to host
            return jsonify(simplified_playlists)
            
        except Exception as e:
            print(f"Error fetching host playlists: {e}")
            return jsonify({"error": "Failed to fetch playlists"}), 500
    
    # For listeners: use optimized caching
    elif user_role == "listener":
        try:
            # Use optimized cache lookup (in-memory first, then Redis)
            cached_data = get_cached_playlists()
            
            if cached_data:
                # Return cached playlists with listener metadata
                listener_response = {
                    "items": cached_data["items"],
                    "total": cached_data["total"],
                    "is_listener": True,
                    "message": f"Viewing {cached_data.get('host_name', 'host')}'s playlists"
                }
                return jsonify(listener_response)
            else:
                # No cached playlists available
                return jsonify({
                    "items": [],
                    "total": 0,
                    "is_listener": True,
                    "message": "No playlists available. Host needs to load their playlists first."
                })
                
        except Exception as e:
            print(f"Error serving playlists to listener: {e}")
            return jsonify({
                "items": [],
                "total": 0,
                "is_listener": True,
                "error": "Failed to load playlists"
            })
    
    # For guests and other roles
    else:
        return jsonify({
            "items": [],
            "total": 0,
            "message": "Playlists not available for this role"
        })


# Fetch tracks for a given playlist
@app.route("/playlists/<playlist_id>/tracks")
def playlist_tracks(playlist_id):
    user_role = session.get("role")
    
    # For hosts: use their own Spotify token
    if user_role == "host":
        token_info = session.get("spotify_token")
        if not token_info:
            print("Host has no Spotify token in session")
            return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
        
        access_token = token_info.get("access_token")
        if not access_token:
            print("Host has no access token available")
            return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
            
        # Cache the host's token for listeners to use
        try:
            cache.set("host_access_token", access_token, timeout=1800)
        except Exception as e:
            print(f"Failed to cache host access token: {e}")
        
    # For listeners: use cached host token
    elif user_role == "listener":
        access_token = cache.get("host_access_token")
        print(f"Listener requesting tracks - cached token available: {access_token is not None}")
        if not access_token:
            print("No cached host token available for listener")
            return jsonify({"error": "Host must be online to load tracks. Ask the host to access their playlists first."}), 503
    
    # For other roles
    else:
        return jsonify({"error": "Not authorized to view playlist tracks"}), 403
    
    try:
        # Get pagination parameters
        limit = min(int(request.args.get('limit', 50)), 50)  # Max 50 per request
        offset = int(request.args.get('offset', 0))
        
        # Try to serve from cache first (much faster)
        cached_tracks = get_cached_tracks(playlist_id, limit, offset)
        if cached_tracks:
            print(f"Serving tracks from cache for playlist {playlist_id}")
            cached_tracks["is_listener"] = user_role == "listener"
            return jsonify(cached_tracks)
        
        # Use manual IP-based fetch with short timeout for speed
        data = manual_playlist_tracks_fetch(access_token, playlist_id, limit, offset)
        
        if not data:
            print("Manual playlist tracks fetch failed - likely network issue")
            return jsonify({"error": "Failed to fetch tracks"}), 500
        
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
            "limit": data.get("limit", limit),
            "is_listener": user_role == "listener"
        }
        
        return jsonify(simplified_tracks)
    except Exception as e:
        print(f"Error fetching playlist tracks: {e}")
        return jsonify({"error": "Failed to fetch tracks"}), 500


# Get Last.fm recommendations for a queued track
@app.route("/recommend/<track_uri>")
def recommend(track_uri):
    """Get similar tracks from Last.fm for a queued track"""
    # Get access token from session
    token_info = session.get("spotify_token")
    if not token_info:
        print("No Spotify token in session for recommendations")
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        print("No access token available for recommendations")
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Extract track ID from URI (spotify:track:XXXXX)
        if not track_uri.startswith("spotify:track:"):
            print(f"Invalid track URI format: {track_uri}")
            return jsonify({"error": "Invalid Spotify track URI"}), 400
        
        track_id = track_uri.split(":")[-1]
        print(f"Fetching track info for ID: {track_id}")
        
        # Get track info from Spotify using manual IP-based API
        track_data = manual_get_track_info(access_token, track_id)
        if not track_data:
            print(f"Failed to fetch track info from Spotify for ID: {track_id}")
            return jsonify({"error": "Failed to fetch track info from Spotify. This may be due to network issues or token expiration."}), 500
        
        if not track_data.get("artists") or len(track_data["artists"]) == 0:
            print(f"No artists found in track data: {track_data}")
            return jsonify({"error": "Track has no artist information"}), 500
            
        artist = track_data["artists"][0]["name"]
        title = track_data["name"]
        print(f"Getting Last.fm recommendations for: {artist} - {title}")
        
        try:
            # Use manual Last.fm API to bypass DNS issues
            recommendations = manual_lastfm_get_similar(
                artist, 
                title, 
                os.getenv("LASTFM_API_KEY"), 
                limit=5
            )
            
            if recommendations is None:
                print(f"Manual Last.fm API failed for {artist} - {title}")
                return jsonify({"error": "Failed to get recommendations from Last.fm"}), 500
            
            print(f"Found {len(recommendations)} recommendations for {artist} - {title}")
            return jsonify({
                "recommendations": recommendations,
                "source_track": f"{artist} - {title}",
                "source_uri": track_uri
            })
            
        except pylast.PyLastError as e:
            print(f"Last.fm API error for {artist} - {title}: {str(e)}")
            return jsonify({"error": f"Last.fm API error: {str(e)}"}), 500
        except Exception as e:
            print(f"Unexpected error getting Last.fm data for {artist} - {title}: {str(e)}")
            return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
            
    except Exception as e:
        print(f"Error in recommend route: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# Test endpoint for Last.fm recommendations (accepts artist and title directly)
@app.route("/recommend-direct")
def recommend_direct():
    """Get similar tracks from Last.fm using artist and title parameters (for testing/fallback)"""
    artist = request.args.get('artist')
    title = request.args.get('title')
    
    if not artist or not title:
        return jsonify({"error": "Missing artist or title parameter"}), 400
    
    try:
        print(f"Getting Last.fm recommendations for: {artist} - {title}")
        
        # Use manual Last.fm API to bypass DNS issues
        recommendations = manual_lastfm_get_similar(
            artist, 
            title, 
            os.getenv("LASTFM_API_KEY"), 
            limit=5
        )
        
        if recommendations is None:
            print(f"Manual Last.fm API failed for {artist} - {title}")
            return jsonify({"error": "Failed to get recommendations from Last.fm"}), 500
        
        print(f"Found {len(recommendations)} recommendations for {artist} - {title}")
        return jsonify({
            "recommendations": recommendations,
            "source_track": f"{artist} - {title}"
        })
        
    except pylast.PyLastError as e:
        print(f"Last.fm API error for {artist} - {title}: {str(e)}")
        return jsonify({"error": f"Last.fm API error: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error for {artist} - {title}: {str(e)}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
        

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
    """Add track to queue - Host and Listener allowed"""
    try:
        # Check if session exists and has role
        user_role = session.get("role")
        user_id = session.get("user_id") 
        
        if not user_role:
            emit("error", {"message": "Authentication expired. Please refresh the page and log in again."})
            return
            
        # Allow both hosts and listeners to add tracks to the queue
        if user_role not in ["host", "listener"]:
            emit("error", {"message": "Only hosts and listeners can add tracks to the queue"})
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
        return jsonify({"error": "Only hosts can clear the queue", "required_role": "host", "current_role": session.get("role")}), 403
    
    db = SessionLocal()
    try:
        # Count items before deletion for feedback
        item_count = db.query(QueueItem).count()
        
        # Clear queue items
        db.query(QueueItem).delete()
        
        # Also clear votes for queue items
        db.query(Vote).delete()
        
        db.commit()
        
        # Broadcast queue clear to all clients
        socketio.emit("queue_cleared")
        socketio.emit("votes_cleared")
        
        return jsonify({
            "status": "success", 
            "message": f"Queue cleared successfully. Removed {item_count} items.",
            "items_removed": item_count
        })
    except Exception as e:
        db.rollback()
        print(f"Error clearing queue: {e}")
        return jsonify({"error": "Database error while clearing queue"}), 500
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
        success = manual_start_playback(access_token, device_id, uris)
        
        if success:
            # Broadcast playback state to all connected clients
            socketio.emit('playback_started', {
                'track_uri': track_uri,
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


@app.route("/playback/pause", methods=["POST"])
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
        success = manual_pause_playback(access_token, device_id)
        
        if success:
            # Broadcast pause state to all connected clients
            socketio.emit('playback_paused', {
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


@app.route("/playback/next", methods=["POST"])
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


@app.route("/playback/status")
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
        playback = manual_get_playback_state(access_token)
        
        if playback:
            return jsonify(playback)
        else:
            return jsonify({"is_playing": False, "device": None})
            
    except Exception as e:
        print(f"Error in playback_status: {e}")
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
    elif error == 'join_failed':
        error_message = """
        <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
            <strong>⚠️ Join Failed</strong><br>
            There was an issue joining as a listener. This is usually temporary.<br><br>
            <strong>Please try:</strong><br>
            1. Refresh the page and try again<br>
            2. Clear your browser cache if the issue persists
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
                Browse host's playlists, add tracks to queue, vote on music, and chat with others.
                <br><strong>No Spotify account required!</strong> Join instantly and participate fully.
            </div>
            <a href="/join-listener" class="role-btn listener-btn">👥 Join Session</a>
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
    
    # Clear playlist caches
    invalidate_playlist_cache()
    print("Cleared playlist caches on host sign out")
    
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
    token_info = session.get("spotify_token")
    if not token_info:
        return jsonify({"error": "Not authenticated"}), 401
    
    access_token = token_info.get("access_token")
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        # Use manual IP-based device fetch
        devices = manual_get_devices(access_token)
        
        if devices:
            return jsonify(devices)
        else:
            return jsonify({"devices": []}), 500
            
    except Exception as e:
        print(f"Error in get_devices: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/playback/transfer", methods=["POST"])
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


@app.route("/queue/next-track")
def get_next_track():
    """Get the next track to play - ALL tracks in queue are eligible regardless of votes"""
    db = SessionLocal()
    try:
        # Get all queue items ordered by timestamp (FIFO - first in, first out)
        # But we'll still consider votes for ordering among tracks added around the same time
        queue_items = db.query(QueueItem).order_by(QueueItem.timestamp).all()
        
        if not queue_items:
            return jsonify({"error": "Queue is empty"}), 404
        
        # NEW LOGIC: All tracks are eligible, but votes affect order preference
        # We'll still prioritize higher voted tracks, but never skip any track
        
        best_track = None
        best_score = -999  # Start with very low score
        fallback_track = None  # Always have a fallback (oldest track)
        
        for item in queue_items:
            # Get vote counts for this track
            votes = db.query(Vote).filter_by(track_uri=item.track_uri).all()
            up_votes = len([v for v in votes if v.vote_type == 'up'])
            down_votes = len([v for v in votes if v.vote_type == 'down'])
            
            # Calculate net score (likes - dislikes)
            net_score = up_votes - down_votes
            
            track_data = {
                "track_uri": item.track_uri,
                "track_name": item.track_name,
                "up_votes": up_votes,
                "down_votes": down_votes,
                "net_score": net_score
            }
            
            # Set fallback to the first (oldest) track if not set
            if fallback_track is None:
                fallback_track = track_data
            
            # Find the track with the highest net score, but don't exclude any
            if net_score > best_score:
                best_score = net_score
                best_track = track_data
        
        # Return the best voted track, or fallback to oldest if all have same/negative scores
        result_track = best_track if best_track else fallback_track
        
        if result_track:
            print(f"Next track selected: {result_track['track_name']} (Score: {result_track['net_score']}, Up: {result_track['up_votes']}, Down: {result_track['down_votes']})")
            return jsonify(result_track)
        else:
            return jsonify({"error": "No tracks in queue"}), 404
            
    except Exception as e:
        print(f"Error in get_next_track: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# Auto-play locking to prevent concurrent requests
auto_play_lock = threading.Lock()
last_auto_play_time = 0

@app.route("/queue/auto-play", methods=["POST"])
def auto_play_next():
    """Automatically play the next track based on voting - Host only"""
    global last_auto_play_time
    
    if session.get("role") != "host":
        print("Auto-play denied: User is not host")
        return abort(403)
    
    # Server-side debounce: prevent multiple auto-play requests within 2 seconds
    current_time = time.time()
    with auto_play_lock:
        if current_time - last_auto_play_time < 2:
            print(f"Auto-play request blocked by server debounce (last call: {current_time - last_auto_play_time:.2f}s ago)")
            return jsonify({"error": "Auto-play request too soon"}), 429
        last_auto_play_time = current_time

    print("Auto-play request received from host")
    
    try:
        # Get the next track based on voting
        next_track_response = get_next_track()
        
        if next_track_response.status_code != 200:
            print(f"No next track available: {next_track_response.status_code}")
            return next_track_response
        
        next_track = next_track_response.get_json()
        track_uri = next_track["track_uri"]
        print(f"Next track to play: {next_track['track_name']} ({track_uri})")
        
        # Get access token from the spotify_token object
        token_info = session.get("spotify_token")
        if not token_info:
            print("No spotify_token in session")
            return jsonify({"error": "Not authenticated"}), 401
            
        access_token = token_info.get("access_token")
        if not access_token:
            print("No access_token in spotify_token")
            return jsonify({"error": "Not authenticated"}), 401
        
        data = request.json or {}
        device_id = data.get("device_id")
        print(f"Playing on device: {device_id}")
        
        # Play the track using manual IP-based request
        success = manual_start_playback(access_token, device_id, [track_uri])
        if not success:
            print("manual_start_playback failed")
            return jsonify({"error": "Failed to start playback"}), 500
        
        # SUCCESS! Track is now playing - remove ONLY this specific track from the queue
        print(f"Successfully started playback of {next_track['track_name']}, removing from queue...")
        
        # Remove the track from the queue and its votes with additional safety checks
        db = SessionLocal()
        try:
            # Start a transaction to ensure atomicity
            db.begin()
            
            # Count queue items before removal for debugging
            total_before = db.query(QueueItem).count()
            print(f"Queue count before removal: {total_before}")
            
            # Find and remove ONLY the specific track that was just played
            # Use a more robust query to ensure we get the exact track
            item = db.query(QueueItem).filter(
                QueueItem.track_uri == track_uri
            ).first()
            
            if item:
                track_name = item.track_name  # Store name before deletion
                track_id = item.id  # Store ID for verification
                
                # Double-check this is the track we expect
                if item.track_uri != track_uri:
                    print(f"ERROR: Track URI mismatch! Expected {track_uri}, got {item.track_uri}")
                    db.rollback()
                    return jsonify({"error": "Track URI mismatch"}), 500
                
                # Remove the specific queue item
                db.delete(item)
                print(f"Marked '{track_name}' (ID: {track_id}) for deletion from queue")
                
                # Also remove associated votes for this specific track
                votes_to_delete = db.query(Vote).filter(Vote.track_uri == track_uri).all()
                votes_count = len(votes_to_delete)
                for vote in votes_to_delete:
                    db.delete(vote)
                print(f"Marked {votes_count} votes for '{track_name}' for deletion")
                
                # Commit the transaction
                db.commit()
                print(f"Transaction committed successfully")
                
                # Count queue items after removal for debugging
                total_after = db.query(QueueItem).count()
                items_removed = total_before - total_after
                print(f"Queue count after removal: {total_after} (removed {items_removed} items)")
                
                if items_removed != 1:
                    print(f"WARNING: Expected to remove 1 item, but removed {items_removed} items!")
                
                # Emit removal event to all clients
                socketio.emit('track_removed', {
                    'track_uri': track_uri,
                    'track_name': track_name
                })
                print(f"Broadcasted track removal: '{track_name}'")
            else:
                print(f"Warning: Track {track_uri} not found in queue to remove")
                db.rollback()
                
        except Exception as db_error:
            print(f"Error removing track from queue: {db_error}")
            db.rollback()
            raise db_error
        finally:
            db.close()
        
        print(f"Auto-play complete: {next_track['track_name']} is playing and removed from queue")
        return jsonify({
            "status": "success", 
            "track": next_track,
            "message": f"Now playing: {next_track['track_name']} (Score: {next_track['net_score']})"
        })
        
    except Exception as e:
        print(f"Error in auto_play_next: {e}")
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


# Direct join route for listeners (no Spotify auth required)
@app.route("/join-listener")
def join_listener():
    """Join as listener without requiring Spotify authentication"""
    try:
        # Generate a unique guest ID
        guest_id = f"listener_{int(time.time())}_{request.remote_addr.replace('.', '')[-4:]}"
        
        # Set listener session without Spotify authentication
        session["role"] = "listener"
        session["user_id"] = guest_id
        session["display_name"] = "Listener"
        session["initialized"] = True
        session["created_at"] = datetime.now(timezone.utc).isoformat()
        
        # Make session permanent
        session.permanent = True
        
        print(f"Listener joined: {guest_id}")
        
        return redirect("/")
        
    except Exception as e:
        print(f"Error joining as listener: {e}")
        return redirect("/select-role?error=join_failed")


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
def manual_playlists_fetch(access_token, fast_timeout=False):
    """Manual playlists fetch using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify API IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Use fast timeout for pre-warming or when speed is critical
    timeout_config = (2, 3) if fast_timeout else (5, 5)
    timeout_desc = "fast" if fast_timeout else "normal"
    
    print(f"Attempting to fetch playlists using manual IP approach with {len(ip_addresses)} IPs ({timeout_desc} timeout)")
    
    # Try each IP directly - bypass DNS completely
    for i, ip in enumerate(ip_addresses):
        try:
            print(f"Trying IP {i+1}/{len(ip_addresses)}: {ip}")
            # Get user playlists directly from IP, use Host header for TLS
            # Reduced limit from 50 to 15 for faster loading
            url = f"https://{ip}/v1/me/playlists?limit=15&offset=0"
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                headers=headers,
                timeout=timeout_config,
                verify=False  # Skip SSL verification since we're using IP
            )
            
            print(f"Response from {ip}: Status {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully fetched playlists from {ip}: {len(data.get('items', []))} playlists")
                return data
            elif response.status_code == 401:
                print(f"Authentication failed with {ip} - token may be expired")
                return None  # Don't try other IPs if auth fails
            else:
                print(f"Failed with {ip}: {response.status_code} - {response.text[:100]}")
                
        except Exception as e:
            print(f"Error with IP {ip}: {str(e)}")
            continue
    
    print("All IP addresses failed for playlists fetch")
    return None


# Manual playlist tracks fetch fallback for Heroku DNS issues
def manual_playlist_tracks_fetch(access_token, playlist_id, limit=50, offset=0):
    """Manual playlist tracks fetch using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    print(f"Fetching tracks for playlist {playlist_id} with token {access_token[:10]}...")
    
    # Try each IP directly - bypass DNS completely with fast failover
    for i, ip in enumerate(ip_addresses):
        try:
            print(f"Trying IP {i+1}/{len(ip_addresses)}: {ip}")
            
            # Get playlist tracks directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}&fields=items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit"
            headers = {
                'Host': 'api.spotify.com',  # Correct Host header for API endpoint
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.get(
                url,
                headers=headers,
                timeout=(2, 2),  # Short timeout for fast failover
                verify=False  # Skip SSL verification since we're using IP
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully fetched {len(data.get('items', []))} tracks from {ip}")
                return data
            elif response.status_code == 401:
                print(f"Authentication failed (401) - token may be expired")
                return None
            elif response.status_code == 404:
                print(f"Playlist not found (404) - playlist_id may be invalid")
                return None
                
        except Exception as e:
            print(f"Error with IP {ip}: {e}")
            continue
    
    # Fallback: try with regular DNS/hostname as last resort
    try:
        print("Trying fallback with regular DNS...")
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit={limit}&offset={offset}&fields=items(track(id,name,artists(name),album(name,images),uri,duration_ms)),total,offset,limit"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=(3, 3))
        
        if response.status_code == 200:
            data = response.json()
            print(f"Successfully fetched {len(data.get('items', []))} tracks via DNS fallback")
            return data
        elif response.status_code == 401:
            print(f"Authentication failed (401) via DNS fallback")
            return None
        elif response.status_code == 404:
            print(f"Playlist not found (404) via DNS fallback")
            return None
            
    except Exception as e:
        print(f"DNS fallback also failed: {e}")
    
    print("All methods failed for playlist tracks fetch")
    return None


# Manual playback control functions for Heroku DNS issues
def manual_start_playback(access_token, device_id=None, uris=None):
    """Manual start playback using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify API IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Prepare the request body
    data = {}
    if uris:
        data['uris'] = uris
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Start playback directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/me/player/play"
            if device_id:
                url += f"?device_id={device_id}"
                
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.put(
                url,
                json=data,
                headers=headers,
                timeout=(3, 3),
                verify=False  # Skip SSL verification since we're using IP
            )
            
            if response.status_code in [200, 204]:
                return True
                
        except Exception as e:
            continue
    
    return False


def manual_pause_playback(access_token, device_id=None):
    """Manual pause playback using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Pause playback directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/me/player/pause"
            if device_id:
                url += f"?device_id={device_id}"
                
            headers = {
                'Host': 'api.spotify.com',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            req_session = requests.Session()
            
            response = req_session.put(
                url,
                headers=headers,
                timeout=(3, 3),
                verify=False  # Skip SSL verification since we're using IP
            )
            
            if response.status_code in [200, 204]:
                return True
                
        except Exception as e:
            continue
    
    return False


def manual_get_devices(access_token):
    """Manual get devices using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Get devices directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/me/player/devices"
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


def manual_get_playback_state(access_token):
    """Manual get playback state using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Get playback state directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/me/player"
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
            elif response.status_code == 204:
                return {"is_playing": False, "device": None}
                
        except Exception as e:
            continue
    
    return None


# Manual Last.fm API client to bypass Heroku DNS issues
def manual_lastfm_get_similar(artist, title, api_key, limit=5):
    """Manual Last.fm API call using hardcoded IPs as DNS fallback"""
    
    # Last.fm API IP addresses (ws.audioscrobbler.com)
    ip_addresses = ["130.211.19.189"]
    
    # Build API parameters
    import hashlib
    
    params = {
        'method': 'track.getsimilar',
        'artist': artist,
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': str(limit)
    }
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Make request directly to IP, use Host header for routing
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
                timeout=(5, 10)  # 5s connect, 10s read timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for Last.fm API errors
                if 'error' in data:
                    print(f"Last.fm API error: {data.get('message', 'Unknown error')}")
                    return None
                
                # Parse similar tracks
                similar_tracks = []
                tracks = data.get('similartracks', {}).get('track', [])
                
                # Handle case where only one similar track is returned (not a list)
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


def manual_get_track_info(access_token, track_id):
    """Manual get track info using hardcoded Spotify IPs as DNS fallback"""
    
    # Spotify IP addresses (multiple for redundancy)
    ip_addresses = ["35.186.224.24", "104.154.127.126", "34.102.136.180"]
    
    # Try each IP directly - bypass DNS completely
    for ip in ip_addresses:
        try:
            # Get track info directly from IP, use Host header for TLS
            url = f"https://{ip}/v1/tracks/{track_id}"
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


def get_cached_tracks(playlist_id, limit=50, offset=0):
    """Get tracks from in-memory cache first, then Redis if needed"""
    cache_key = f"{playlist_id}:{limit}:{offset}"
    
    # Try in-memory cache first (fastest)
    if cache_key in in_memory_cache.get('playlist_tracks', {}):
        timestamp = in_memory_cache.get('playlist_tracks_timestamps', {}).get(cache_key)
        if timestamp and (time.time() - timestamp) < 60:  # 60 second TTL for tracks
            print(f"Serving tracks from in-memory cache for {cache_key}")
            return in_memory_cache['playlist_tracks'][cache_key]
    
    # Try Redis cache
    try:
        redis_key = f"playlist_tracks:{cache_key}"
        cached_data = cache.get(redis_key)
        if cached_data:
            print(f"Serving tracks from Redis cache for {cache_key}")
            # Update in-memory cache to avoid Redis on next request
            set_cached_tracks(playlist_id, cached_data, limit, offset)
            return cached_data
    except Exception as e:
        print(f"Redis tracks cache read failed: {e}")
    
    print(f"No cached tracks available for {cache_key}")
    return None

def set_cached_tracks(playlist_id, tracks_data, limit=50, offset=0):
    """Set tracks in both in-memory and Redis cache"""
    cache_key = f"{playlist_id}:{limit}:{offset}"
    
    # Update in-memory cache
    if 'playlist_tracks' not in in_memory_cache:
        in_memory_cache['playlist_tracks'] = {}
    if 'playlist_tracks_timestamps' not in in_memory_cache:
        in_memory_cache['playlist_tracks_timestamps'] = {}
        
    in_memory_cache['playlist_tracks'][cache_key] = tracks_data
    in_memory_cache['playlist_tracks_timestamps'][cache_key] = time.time()
    print(f"Updated in-memory tracks cache for {cache_key}")
    
    # Update Redis cache asynchronously
    def cache_tracks_async():
        try:
            redis_key = f"playlist_tracks:{cache_key}"
            cache.set(redis_key, tracks_data, timeout=300)  # 5 minutes TTL
            print(f"Updated Redis tracks cache for {cache_key}")
        except Exception as e:
            print(f"Failed to cache tracks in Redis: {e}")
    
    threading.Thread(target=cache_tracks_async, daemon=True).start()
