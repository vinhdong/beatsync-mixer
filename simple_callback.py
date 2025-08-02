# Simplified callback route
@app.route("/callback")
def callback():
    print(f"OAuth callback received")
    print(f"Request args: {dict(request.args)}")
    
    try:
        # Get OAuth token with extended timeout
        print("Attempting to get OAuth token from Spotify...")
        token = oauth.spotify.authorize_access_token()
        print(f"Successfully received token: {bool(token)}")
        
        if not token:
            print("No token received from Spotify")
            return redirect("/select-role?error=oauth_failed")
        
        # Store token in session
        session["spotify_token"] = token
        oauth.spotify.token = token
        
        # Get user profile
        print("Fetching user profile...")
        try:
            user_response = oauth.spotify.get("https://api.spotify.com/v1/me", token=token)
            if user_response.status_code == 200:
                user_data = user_response.json()
                user_id = user_data.get("id")
                display_name = user_data.get("display_name", user_id)
                print(f"Successfully fetched user profile: {user_id}")
            else:
                print(f"Failed to fetch user profile: {user_response.status_code}")
                user_id = f"user_{int(time.time())}"
                display_name = "Spotify User"
        except Exception as e:
            print(f"Error fetching user profile: {e}")
            user_id = f"user_{int(time.time())}"
            display_name = "Spotify User"
        
        # Get requested role
        requested_role = session.get('requested_role', 'listener')
        print(f"Setting role to: {requested_role}")
        
        # Handle role assignment
        if requested_role == 'host':
            # Check if someone is already hosting
            host_file = 'current_host.txt'
            if os.path.exists(host_file):
                print("Someone is already hosting")
                return redirect("/select-role?error=host_taken")
            
            # Set as host
            session["role"] = "host"
            session["user_id"] = user_id
            session["display_name"] = display_name
            
            # Create host file
            with open(host_file, 'w') as f:
                f.write(f"{user_id}|{display_name}")
            
            print(f"User {user_id} is now hosting")
        else:
            # Set as listener
            session["role"] = "listener"
            session["user_id"] = user_id
            session["display_name"] = display_name
            print(f"User {user_id} joined as listener")
        
        # Clean up session
        session.pop('requested_role', None)
        session.permanent = True
        
        print(f"OAuth callback successful, redirecting to main app")
        return redirect("/")
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        
        # Check if it's a network/timeout error
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ['timeout', 'connection', 'dns', 'lookup']):
            print("Network/DNS error detected - redirecting with network error message")
            return redirect("/select-role?error=oauth_failed")
        else:
            print("Other OAuth error - redirecting with general error")
            return redirect("/select-role?error=oauth_failed")
