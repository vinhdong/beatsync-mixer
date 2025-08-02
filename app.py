"""
BeatSync Mixer - Flask Application Factory
A collaborative music queue app with Spotify integration and Last.fm recommendations.
"""

import os
from flask import Flask, session, redirect
from datetime import datetime, timezone

# Import configuration and initialization functions
from config import init_app
from db import init_db
from sockets import init_socketio

# Import blueprints
from auth import auth_bp
from playlists import playlists_bp
from recommend import recommend_bp
from queue_routes import queue_bp
from playback import playback_bp
from session_management import session_mgmt_bp


def create_app():
    """Application factory for BeatSync Mixer"""
    
    # Create Flask app
    app = Flask(__name__, static_folder="frontend", static_url_path="")
    
    # Initialize configuration and cache
    cache = init_app(app)
    
    # Store cache instance in app for access by other modules
    app.cache = cache
    
    # Initialize database
    init_db()
    
    # Initialize Socket.IO
    socketio = init_socketio(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(playlists_bp, url_prefix="/playlists")
    app.register_blueprint(recommend_bp, url_prefix="/recommend")
    app.register_blueprint(queue_bp, url_prefix="/queue")
    app.register_blueprint(playback_bp, url_prefix="/playback")
    app.register_blueprint(session_mgmt_bp)
    
    # Health check route
    @app.route("/health")
    def health_check():
        """Simple health check endpoint"""
        return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
    
    # Main application route
    @app.route("/")
    def index():
        """Serve front-end application"""
        # Debug session state in detail
        print(f"=== MAIN ROUTE SESSION DEBUG ===")
        print(f"Session ID: {session.get('_id', 'No ID')}")
        print(f"Session permanent: {session.permanent}")
        print(f"Session modified: {getattr(session, 'modified', 'Unknown')}")
        print(f"All session data: {dict(session)}")
        print(f"=== END SESSION DEBUG ===")
        
        # Check if user is authenticated - allow guest, host, and listener roles
        user_role = session.get("role")
        print(f"Main route - Session role: {user_role}, Session keys: {list(session.keys())}")
        
        # More detailed role validation
        if not user_role:
            print(f"No role found in session, redirecting to select-role")
            return redirect("/select-role?error=session_lost")
        elif user_role not in ['guest', 'host', 'listener']:
            print(f"Invalid role found: '{user_role}', redirecting to select-role")
            return redirect("/select-role?error=invalid_role")
        
        # For hosts, also check if they have access token
        if user_role == 'host' and not session.get('access_token'):
            print(f"Host role but no access token, redirecting to re-authenticate")
            return redirect("/select-role?error=auth_expired")
        
        print(f"Valid session found for role: {user_role}, serving main page")
        
        # Read the HTML file and inject role information
        html_path = os.path.join(app.static_folder, "index.html")
        with open(html_path, 'r') as f:
            html_content = f.read()
        
        # Inject user role and info into the HTML
        role = user_role or session.get("role", "guest")  # Use the validated user_role
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
    
    # Store socketio instance globally for import by other modules
    app.socketio = socketio
    
    return app, socketio


# Create app instance
app, socketio = create_app()


# Run the application
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
