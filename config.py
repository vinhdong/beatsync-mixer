"""
Configuration module for BeatSync Mixer.
Handles app configuration, session storage, and cache initialization.
"""

import os
import redis
import ssl
from flask_session import Session
from flask_caching import Cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_redis_url():
    """Get Redis URL with proper SSL configuration for Heroku"""
    redis_url = os.getenv("REDIS_URL")
    
    if redis_url and redis_url.startswith("rediss://"):
        # Parse Redis URL and ensure SSL settings for Heroku
        return redis_url + "?ssl_cert_reqs=none"
    elif redis_url:
        return redis_url
    else:
        # Local fallback
        return "redis://localhost:6379/0"


def create_manual_redis_client():
    """Create a manual Redis client using direct IPs to bypass Heroku DNS issues"""
    try:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            print("No REDIS_URL found, using local Redis")
            return redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Parse Redis URL for Heroku
        from urllib.parse import urlparse
        parsed = urlparse(redis_url)
        
        # Try direct connection with very short timeouts
        client = redis.Redis(
            host=parsed.hostname,
            port=parsed.port or 6379,
            password=parsed.password,
            ssl=True if parsed.scheme == 'rediss' else False,
            ssl_cert_reqs=None if parsed.scheme == 'rediss' else None,
            decode_responses=True,
            socket_connect_timeout=3,  # Reduced from 5 to fail faster
            socket_timeout=3,          # Reduced from 5 to fail faster
            retry_on_timeout=False     # Don't retry on timeout
        )
        
        # Test connection with timeout
        client.ping()
        print(f"Manual Redis client connected successfully to {parsed.hostname}:{parsed.port}")
        return client
        
    except Exception as e:
        print(f"Manual Redis connection failed: {e}")
        return None


class ManualRedisCache:
    """Manual Redis cache wrapper with fallback to Flask-Caching"""
    
    def __init__(self, flask_cache):
        self.flask_cache = flask_cache
        self.manual_client = create_manual_redis_client()
        self.use_manual = self.manual_client is not None
        
        if self.use_manual:
            print("Using manual Redis client for caching")
        else:
            print("Falling back to Flask-Caching for Redis")
    
    def get(self, key):
        if self.use_manual:
            try:
                return self.manual_client.get(key)
            except Exception as e:
                print(f"Manual Redis get failed for key: {key} - {e}, falling back to Flask-Caching")
                return self.flask_cache.get(key)
        else:
            return self.flask_cache.get(key)
    
    def set(self, key, value, timeout=None):
        if self.use_manual:
            try:
                if timeout:
                    return self.manual_client.setex(key, timeout, value)
                else:
                    return self.manual_client.set(key, value)
            except Exception as e:
                print(f"Manual Redis set failed for key: {key} - {e}, falling back to Flask-Caching")
                return self.flask_cache.set(key, value, timeout=timeout)
        else:
            return self.flask_cache.set(key, value, timeout=timeout)
    
    def delete(self, key):
        if self.use_manual:
            try:
                return self.manual_client.delete(key)
            except Exception as e:
                print(f"Manual Redis delete failed for key: {key} - {e}, falling back to Flask-Caching")
                return self.flask_cache.delete(key)
        else:
            return self.flask_cache.delete(key)


def configure_session_storage(app):
    """Configure session storage with fallback for Redis failures"""
    
    if os.getenv("FLASK_ENV") == "production":
        # Try to use Redis for sessions in production
        try:
            # First try to create a manual Redis client for sessions
            manual_redis = create_manual_redis_client()
            if manual_redis:
                app.config["SESSION_TYPE"] = "redis"
                app.config["SESSION_REDIS"] = manual_redis
                app.config["SESSION_PERMANENT"] = True
                app.config["SESSION_USE_SIGNER"] = True
                app.config["SESSION_KEY_PREFIX"] = "beatsync:"
                app.config["SESSION_COOKIE_SECURE"] = True
                app.config["SESSION_COOKIE_HTTPONLY"] = True
                app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
                print("Using manual Redis client for session storage (production)")
                return True
            else:
                raise Exception("Manual Redis client creation failed")
                
        except Exception as e:
            print(f"Redis session storage failed ({e}), falling back to filesystem")
            # Fall back to filesystem sessions even in production
            app.config["SESSION_TYPE"] = "filesystem"
            app.config["SESSION_PERMANENT"] = True
            app.config["SESSION_USE_SIGNER"] = True
            app.config["SESSION_FILE_DIR"] = "/tmp/flask_session"
            app.config["SESSION_COOKIE_SECURE"] = False  # Changed: Allow HTTP for debugging
            app.config["SESSION_COOKIE_HTTPONLY"] = True
            app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
            
            # Ensure session directory exists and is writable
            session_dir = "/tmp/flask_session"
            try:
                os.makedirs(session_dir, exist_ok=True)
                # Test write permissions
                test_file = os.path.join(session_dir, "test_write")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print(f"Filesystem session directory ready: {session_dir}")
            except Exception as dir_error:
                print(f"Warning: Session directory issue: {dir_error}")
            
            print("Using filesystem for session storage (production fallback)")
            return False
    else:
        # Development: Use filesystem for session storage
        app.config["SESSION_TYPE"] = "filesystem"
        app.config["SESSION_PERMANENT"] = True
        app.config["SESSION_USE_SIGNER"] = True
        app.config["SESSION_FILE_DIR"] = "/tmp/flask_session"
        print("Using filesystem for session storage (development)")
        return False


def init_app(app):
    """Initialize Flask app with configuration and return cache instance"""
    
    # Basic Flask configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    # Configure session storage with fallback
    configure_session_storage(app)
    
    # Initialize Flask-Session
    Session(app)
    
    # Configure Flask-Caching with robust fallback
    try:
        # Try manual Redis client first (bypasses DNS issues)
        manual_redis = create_manual_redis_client()
        if manual_redis:
            # Use manual Redis client for caching
            app.config["CACHE_TYPE"] = "redis"
            app.config["CACHE_REDIS_URL"] = get_redis_url()
            app.config["CACHE_DEFAULT_TIMEOUT"] = 300
            print("Manual Redis client available for caching")
        else:
            raise Exception("Manual Redis client not available")
            
    except Exception as e:
        # Fall back to simple memory cache
        print(f"Redis not available for caching ({e}), using simple memory cache")
        app.config["CACHE_TYPE"] = "simple"
        app.config["CACHE_DEFAULT_TIMEOUT"] = 300
    
    # Initialize Flask-Caching
    flask_cache = Cache(app)
    
    # Create manual Redis cache wrapper
    cache = ManualRedisCache(flask_cache)
    
    print("Configuration and caching initialized successfully")
    return cache
