"""
User authentication routes for BeatSync Mixer.
Handles user registration, login, and session management without Spotify dependency.
"""

import re
from flask import Blueprint, request, session, jsonify, render_template_string
from backend.models.models import get_db, User


user_auth_bp = Blueprint('user_auth', __name__)


def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def is_valid_username(username):
    """Validate username format"""
    # 3-20 characters, alphanumeric and underscores only
    pattern = r'^[a-zA-Z0-9_]{3,20}$'
    return re.match(pattern, username) is not None


@user_auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration"""
    if request.method == "GET":
        # Return registration form HTML
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>BeatSync Mixer - Register</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .auth-container {
                    background: white;
                    padding: 2rem;
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    width: 100%;
                    max-width: 400px;
                }
                .logo {
                    text-align: center;
                    margin-bottom: 2rem;
                }
                .logo h1 {
                    color: #667eea;
                    margin: 0;
                    font-size: 1.8rem;
                }
                .form-group {
                    margin-bottom: 1.5rem;
                }
                label {
                    display: block;
                    margin-bottom: 0.5rem;
                    color: #333;
                    font-weight: 500;
                }
                input[type="text"], input[type="email"], input[type="password"] {
                    width: 100%;
                    padding: 0.75rem;
                    border: 2px solid #e1e1e1;
                    border-radius: 6px;
                    font-size: 1rem;
                    box-sizing: border-box;
                }
                input:focus {
                    outline: none;
                    border-color: #667eea;
                }
                .btn {
                    width: 100%;
                    padding: 0.75rem;
                    background: #667eea;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: background 0.2s;
                }
                .btn:hover {
                    background: #5a6fd8;
                }
                .error {
                    color: #e74c3c;
                    margin-top: 0.5rem;
                    font-size: 0.9rem;
                }
                .success {
                    color: #27ae60;
                    margin-top: 0.5rem;
                    font-size: 0.9rem;
                }
                .switch-auth {
                    text-align: center;
                    margin-top: 1.5rem;
                }
                .switch-auth a {
                    color: #667eea;
                    text-decoration: none;
                }
                .switch-auth a:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <div class="auth-container">
                <div class="logo">
                    <h1>🎵 BeatSync Mixer</h1>
                    <p>Create your account to start hosting</p>
                </div>
                
                <form id="registerForm">
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" required 
                               placeholder="Enter username (3-20 characters)" 
                               pattern="[a-zA-Z0-9_]{3,20}" 
                               title="Username must be 3-20 characters, letters, numbers, and underscores only">
                    </div>
                    
                    <div class="form-group">
                        <label for="email">Email</label>
                        <input type="email" id="email" name="email" required 
                               placeholder="Enter your email">
                    </div>
                    
                    <div class="form-group">
                        <label for="password">Password</label>
                        <input type="password" id="password" name="password" required 
                               placeholder="Enter password (min 6 characters)" 
                               minlength="6">
                    </div>
                    
                    <div class="form-group">
                        <label for="confirmPassword">Confirm Password</label>
                        <input type="password" id="confirmPassword" name="confirmPassword" required 
                               placeholder="Confirm your password">
                    </div>
                    
                    <button type="submit" class="btn">Create Account</button>
                    
                    <div id="message"></div>
                </form>
                
                <div class="switch-auth">
                    Already have an account? <a href="/user_auth/login">Sign In</a>
                </div>
            </div>
            
            <script>
                document.getElementById('registerForm').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    
                    const formData = new FormData(this);
                    const data = Object.fromEntries(formData);
                    const messageDiv = document.getElementById('message');
                    
                    // Client-side validation
                    if (data.password !== data.confirmPassword) {
                        messageDiv.innerHTML = '<div class="error">Passwords do not match</div>';
                        return;
                    }
                    
                    if (data.password.length < 6) {
                        messageDiv.innerHTML = '<div class="error">Password must be at least 6 characters</div>';
                        return;
                    }
                    
                    try {
                        const response = await fetch('/user_auth/register', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(data)
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok) {
                            messageDiv.innerHTML = '<div class="success">' + result.message + '</div>';
                            setTimeout(() => {
                                window.location.href = '/user_auth/login';
                            }, 1500);
                        } else {
                            messageDiv.innerHTML = '<div class="error">' + result.error + '</div>';
                        }
                    } catch (error) {
                        messageDiv.innerHTML = '<div class="error">Registration failed. Please try again.</div>';
                    }
                });
            </script>
        </body>
        </html>
        """)
    
    # Handle POST request for registration
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        confirm_password = data.get('confirmPassword', '')
        
        # Validation
        if not username or not email or not password:
            return jsonify({"error": "All fields are required"}), 400
        
        if not is_valid_username(username):
            return jsonify({"error": "Username must be 3-20 characters, letters, numbers, and underscores only"}), 400
        
        if not is_valid_email(email):
            return jsonify({"error": "Please enter a valid email address"}), 400
        
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        
        if password != confirm_password:
            return jsonify({"error": "Passwords do not match"}), 400
        
        # Check if user already exists
        with get_db() as db:
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    return jsonify({"error": "Username already exists"}), 400
                else:
                    return jsonify({"error": "Email already exists"}), 400
            
            # Create new user
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.add(new_user)
            
            return jsonify({
                "message": "Account created successfully! Redirecting to login...",
                "username": username
            }), 201
            
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({"error": "Registration failed. Please try again."}), 500


@user_auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login"""
    if request.method == "GET":
        # Return login form HTML
        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>BeatSync Mixer - Login</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .auth-container {
                    background: white;
                    padding: 2rem;
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    width: 100%;
                    max-width: 400px;
                }
                .logo {
                    text-align: center;
                    margin-bottom: 2rem;
                }
                .logo h1 {
                    color: #667eea;
                    margin: 0;
                    font-size: 1.8rem;
                }
                .form-group {
                    margin-bottom: 1.5rem;
                }
                label {
                    display: block;
                    margin-bottom: 0.5rem;
                    color: #333;
                    font-weight: 500;
                }
                input[type="text"], input[type="password"] {
                    width: 100%;
                    padding: 0.75rem;
                    border: 2px solid #e1e1e1;
                    border-radius: 6px;
                    font-size: 1rem;
                    box-sizing: border-box;
                }
                input:focus {
                    outline: none;
                    border-color: #667eea;
                }
                .btn {
                    width: 100%;
                    padding: 0.75rem;
                    background: #667eea;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: background 0.2s;
                }
                .btn:hover {
                    background: #5a6fd8;
                }
                .error {
                    color: #e74c3c;
                    margin-top: 0.5rem;
                    font-size: 0.9rem;
                }
                .success {
                    color: #27ae60;
                    margin-top: 0.5rem;
                    font-size: 0.9rem;
                }
                .switch-auth {
                    text-align: center;
                    margin-top: 1.5rem;
                }
                .switch-auth a {
                    color: #667eea;
                    text-decoration: none;
                }
                .switch-auth a:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <div class="auth-container">
                <div class="logo">
                    <h1>🎵 BeatSync Mixer</h1>
                    <p>Sign in to start hosting</p>
                </div>
                
                <form id="loginForm">
                    <div class="form-group">
                        <label for="username">Username or Email</label>
                        <input type="text" id="username" name="username" required 
                               placeholder="Enter username or email">
                    </div>
                    
                    <div class="form-group">
                        <label for="password">Password</label>
                        <input type="password" id="password" name="password" required 
                               placeholder="Enter your password">
                    </div>
                    
                    <button type="submit" class="btn">Sign In</button>
                    
                    <div id="message"></div>
                </form>
                
                <div class="switch-auth">
                    Don't have an account? <a href="/user_auth/register">Create Account</a>
                </div>
            </div>
            
            <script>
                document.getElementById('loginForm').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    
                    const formData = new FormData(this);
                    const data = Object.fromEntries(formData);
                    const messageDiv = document.getElementById('message');
                    
                    try {
                        const response = await fetch('/user_auth/login', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify(data)
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok) {
                            messageDiv.innerHTML = '<div class="success">' + result.message + '</div>';
                            setTimeout(() => {
                                window.location.href = '/';
                            }, 1000);
                        } else {
                            messageDiv.innerHTML = '<div class="error">' + result.error + '</div>';
                        }
                    } catch (error) {
                        messageDiv.innerHTML = '<div class="error">Login failed. Please try again.</div>';
                    }
                });
            </script>
        </body>
        </html>
        """)
    
    # Handle POST request for login
    try:
        data = request.get_json()
        username_or_email = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username_or_email or not password:
            return jsonify({"error": "Username/email and password are required"}), 400
        
        with get_db() as db:
            # Check if it's email or username
            if '@' in username_or_email:
                user = db.query(User).filter(User.email == username_or_email.lower()).first()
            else:
                user = db.query(User).filter(User.username == username_or_email).first()
            
            if not user or not user.check_password(password):
                return jsonify({"error": "Invalid username/email or password"}), 401
            
            # Set session
            session['user_id'] = user.id
            session['username'] = user.username
            session['display_name'] = user.username  # Add display_name for chat
            session['role'] = 'host'  # Since only hosts need to login
            session['authenticated'] = True
            
            return jsonify({
                "message": "Login successful! Redirecting...",
                "username": user.username,
                "role": "host"
            }), 200
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": "Login failed. Please try again."}), 500


@user_auth_bp.route("/logout", methods=["POST"])
def logout():
    """User logout"""
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


@user_auth_bp.route("/check-auth")
def check_auth():
    """Check if user is authenticated"""
    if session.get('authenticated') and session.get('user_id'):
        return jsonify({
            "authenticated": True,
            "username": session.get('username'),
            "role": session.get('role')
        }), 200
    else:
        return jsonify({"authenticated": False}), 200
