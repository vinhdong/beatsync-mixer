"""
Session management routes for BeatSync Mixer.
Handles role selection, host status, and session control.
"""

import os
from flask import Blueprint, session, request, redirect, jsonify
from backend.models.models import get_db, QueueItem, Vote, ChatMessage
from backend.utils.cache import invalidate_playlist_cache, clear_currently_playing, clear_queue_snapshot
from datetime import datetime, timezone


session_mgmt_bp = Blueprint('session_mgmt', __name__)


@session_mgmt_bp.route("/select-role")
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
    elif error == 'session_lost':
        # Remove the session lost message as requested
        error_message = ""
    elif error == 'invalid_role':
        error_message = """
        <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
            <strong>⚠️ Invalid Role</strong><br>
            Your session contains an invalid role. Please select a new role below.
        </div>
        """
    elif error == 'auth_expired':
        error_message = """
        <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
            <strong>⚠️ Authentication Expired</strong><br>
            Your Spotify authentication has expired. Please log in again to continue as host.
        </div>
        """
    elif error == 'csrf_error':
        error_message = """
        <div style="background: #ffe6e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #e74c3c; color: #c0392b;">
            <strong>⚠️ Session Security Error</strong><br>
            Your session expired during authentication. This commonly happens after restarting the session.<br><br>
            <strong>Please try:</strong><br>
            1. Refresh the page and try again<br>
            2. If it keeps failing, clear your browser cookies and try again
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
            <a href="/user_auth/login" class="role-btn" id="host-btn">🎵 Host Session</a>
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


@session_mgmt_bp.route("/host-status")
def host_status():
    """Check if someone is currently hosting"""
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


@session_mgmt_bp.route("/sign-out-host", methods=["POST"])
def sign_out_host():
    """Sign out as host"""
    if session.get("role") != "host":
        return jsonify({"error": "Only hosts can sign out"}), 403
    
    # Remove host file
    host_file = 'current_host.txt'
    if os.path.exists(host_file):
        os.remove(host_file)
    
    # Clear currently playing track
    clear_currently_playing()
    
    # Clear playlist caches
    invalidate_playlist_cache()
    print("Cleared playlist caches on host sign out")
    
    # Clear session
    session.clear()
    
    return jsonify({"status": "success", "message": "Signed out as host"})


@session_mgmt_bp.route("/logout")
def logout():
    """Clear session and redirect to role selection"""
    session.clear()
    return redirect("/select-role")


@session_mgmt_bp.route("/reset-session")
def reset_session():
    """Reset user session and redirect to role selection"""
    session.clear()
    return redirect("/select-role")


@session_mgmt_bp.route("/restart-session", methods=["POST"])
def restart_session():
    """Restart the entire session - clears all session data, host state, queue, votes, and chat"""
    try:
        # Remove host file
        host_file = 'current_host.txt'
        if os.path.exists(host_file):
            os.remove(host_file)
        
        # Clear the queue, votes, chat, and currently playing
        try:
            with get_db() as db:
                # Clear all votes
                db.query(Vote).delete()
                
                # Clear all queue items
                db.query(QueueItem).delete()
                
                # Clear all chat messages
                db.query(ChatMessage).delete()
                
                # Clear caches
                clear_currently_playing()
                clear_queue_snapshot()
                
                # Emit events to all connected clients
                from flask import current_app
                if hasattr(current_app, 'socketio'):
                    current_app.socketio.emit('queue_cleared')
                    current_app.socketio.emit('votes_cleared')
                    current_app.socketio.emit('chat_cleared')
                    current_app.socketio.emit('playback_paused', {'is_playing': False})
                    current_app.socketio.emit('session_restarted')
                
        except Exception as e:
            print(f"Error clearing data during session restart: {e}")
        
        return jsonify({
            "status": "success", 
            "message": "Session restarted successfully. All data cleared. All users should refresh their browsers."
        })
        
    except Exception as e:
        print(f"Error restarting session: {e}")
        return jsonify({"error": "Failed to restart session"}), 500


@session_mgmt_bp.route("/session-info")
def session_info():
    """Return current session information for debugging"""
    return jsonify({
        'user_id': session.get('user_id'),
        'role': session.get('role'),
        'access_token': session.get('access_token', '')[0:20] + '...' if session.get('access_token') else None,
        'refresh_token': session.get('refresh_token', '')[0:20] + '...' if session.get('refresh_token') else None,
        'display_name': session.get('display_name'),
        'authenticated': bool(session.get('access_token')),
        'login_timestamp': session.get('login_timestamp'),
        'session_permanent': session.permanent,
        'session_id': session.get('_id', 'No ID'),
        'session_keys': list(session.keys()),
        'full_session': dict(session) if len(session.keys()) < 20 else 'Too many keys to display'
    })


# Development/testing endpoint to simulate a host session
@session_mgmt_bp.route("/test-host-session")
def test_host_session():
    """Test endpoint to simulate a host session (for debugging only)"""
    if os.environ.get('FLASK_ENV') != 'development':
        return "Test endpoint only available in development", 403
    
    # Set up a fake host session
    session['role'] = 'host'
    session['user_id'] = 'test_user_12345'
    session['display_name'] = 'Test Host'
    session['access_token'] = 'test_token_12345'
    session['refresh_token'] = 'test_refresh_12345'
    session['token_expires'] = (datetime.now(timezone.utc).timestamp() + 3600)
    session['initialized'] = True
    session['created_at'] = datetime.now(timezone.utc).isoformat()
    session.permanent = True
    
    return redirect("/")
