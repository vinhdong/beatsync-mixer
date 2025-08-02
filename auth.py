"""
Authentication routes for BeatSync Mixer.
Handles login, callback, and session management.
"""

import os
import time
import threading
from datetime import datetime, timezone
from flask import Blueprint, request, session, redirect, jsonify
from spotify_api import spotify_oauth, exchange_token, fetch_user_profile, fetch_playlists
from cache import cache_playlists_async, simplify_playlists_data


auth_bp = Blueprint('auth', __name__)


@auth_bp.before_request
def ensure_session_initialization():
    """Ensure session is properly initialized for all requests"""
    if 'initialized' not in session:
        session['initialized'] = True
        session['created_at'] = datetime.now(timezone.utc).isoformat()
        session.permanent = True


@auth_bp.route("/login")
def login():
    """Initiate Spotify OAuth flow"""
    try:
        requested_role = request.args.get('role', 'listener')
        session['requested_role'] = requested_role
        
        if requested_role == 'host':
            auth_url = spotify_oauth.get_authorize_url()
            return redirect(auth_url)
        else:
            return redirect("/join-listener")
    except Exception as e:
        print(f"Login route error: {e}")
        return redirect("/select-role?error=oauth_failed")


@auth_bp.route("/callback")
def callback():
    """Handle Spotify OAuth callback"""
    try:
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            print(f"OAuth error: {error}")
            return redirect("/select-role?error=oauth_failed")
        
        if not code:
            print("No authorization code received")
            return redirect("/select-role?error=oauth_failed")
        
        # Use ONLY fast IP-based token exchange
        token_info = exchange_token(code)
        
        if not token_info:
            print("Fast IP exchange failed - network/Heroku issue")
            error_msg = "network_timeout"
            return redirect(f"/select-role?error=oauth_failed&details={error_msg}")
        
        # Store token in session
        session["spotify_token"] = token_info
        
        # Fetch real user profile using IP-based approach
        access_token = token_info.get("access_token")
        user_profile = fetch_user_profile(access_token) if access_token else None
        
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
                from flask import current_app
                cache = getattr(current_app, 'cache', None)
                if cache:
                    cache.set("host_access_token", access_token, timeout=1800)
                    print(f"IMMEDIATELY cached host access token for listeners")
                else:
                    print("CRITICAL: No cache instance available")
            except Exception as e:
                print(f"CRITICAL: Failed to cache host access token: {e}")
            
            # Start asynchronous playlist pre-caching
            def cache_playlists_background():
                """Cache playlists in background thread to avoid blocking login"""
                try:
                    print(f"Background: Pre-caching playlists for new host: {display_name}")
                    playlists_data = fetch_playlists(access_token, fast_timeout=True)
                    if playlists_data:
                        # Create simplified playlists using our helper function
                        simplified_playlists = simplify_playlists_data(playlists_data)
                        if simplified_playlists:
                            # Add host metadata
                            simplified_playlists["host_name"] = display_name
                            simplified_playlists["cached_at"] = time.time()
                            
                            # Cache using our optimized async function
                            cache_playlists_async(access_token, simplified_playlists)
                            
                            print("Background: Playlists pre-cached successfully")
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


@auth_bp.route("/join-listener")
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


@auth_bp.route("/fetch-user-profile", methods=["POST"])
def fetch_user_profile_route():
    """Fetch user profile asynchronously after login"""
    if not session.get("spotify_token"):
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        token_info = session.get("spotify_token")
        access_token = token_info.get("access_token")
        
        if not access_token:
            return jsonify({"error": "No access token"}), 401
        
        user_profile = fetch_user_profile(access_token)
        
        if user_profile:
            session["user_id"] = user_profile.get("id", session.get("user_id"))
            session["display_name"] = user_profile.get("display_name") or user_profile.get("id", "Spotify User")
            
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
