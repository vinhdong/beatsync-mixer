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
        
        # Try direct connection first
        client = redis.Redis(
            host=parsed.hostname,
            port=parsed.port or 6379,
            password=parsed.password,
            ssl=True if parsed.scheme == 'rediss' else False,
            ssl_cert_reqs=None if parsed.scheme == 'rediss' else None,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test connection
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
            except:
                print(f"Manual Redis get failed for key: {key}, falling back to Flask-Caching")
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
                print(f"Manual Redis set failed for key: {key}, falling back to Flask-Caching: {e}")
                return self.flask_cache.set(key, value, timeout=timeout)
        else:
            return self.flask_cache.set(key, value, timeout=timeout)
    
    def delete(self, key):
        if self.use_manual:
            try:
                return self.manual_client.delete(key)
            except:
                print(f"Manual Redis delete failed for key: {key}, falling back to Flask-Caching")
                return self.flask_cache.delete(key)
        else:
            return self.flask_cache.delete(key)


def init_app(app):
    """Initialize Flask app with configuration and return cache instance"""
    
    # Basic Flask configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    
    # Configure server-side session storage
    if os.getenv("FLASK_ENV") == "production":
        # Production: Use Redis for session storage (recommended for multi-dyno Heroku apps)
        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = redis.from_url(
            get_redis_url(),
            ssl_cert_reqs=ssl.CERT_NONE if get_redis_url().startswith("rediss://") else None
        )
        app.config["SESSION_PERMANENT"] = True
        app.config["SESSION_USE_SIGNER"] = True
        app.config["SESSION_KEY_PREFIX"] = "beatsync:"
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        print("Using Redis for session storage (production)")
    else:
        # Development: Use filesystem for session storage (simpler for local dev)
        app.config["SESSION_TYPE"] = "filesystem"
        app.config["SESSION_PERMANENT"] = True
        app.config["SESSION_USE_SIGNER"] = True
        app.config["SESSION_FILE_DIR"] = "/tmp/flask_session"
        print("Using filesystem for session storage (development)")
    
    # Initialize Flask-Session
    Session(app)
    
    # Configure Flask-Caching
    try:
        # Try Redis first
        redis_url = get_redis_url()
        test_client = redis.from_url(redis_url)
        test_client.ping()
        
        app.config["CACHE_TYPE"] = "redis"
        app.config["CACHE_REDIS_URL"] = redis_url
        app.config["CACHE_DEFAULT_TIMEOUT"] = 300
        print("Using Redis for caching")
        
    except Exception as e:
        # Fall back to simple memory cache for local development
        print(f"Redis not available ({e}), using simple memory cache")
        app.config["CACHE_TYPE"] = "simple"
        app.config["CACHE_DEFAULT_TIMEOUT"] = 300
    
    # Initialize Flask-Caching
    flask_cache = Cache(app)
    
    # Create manual Redis cache wrapper
    cache = ManualRedisCache(flask_cache)
    
    print("Configuration and caching initialized successfully")
    return cache
