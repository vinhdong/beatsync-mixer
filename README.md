# 🎵 BeatSync Mixer

A collaborative music queueing web application that connects with Spotify to let users browse playlists, queue tracks, and vote on music in real-time. Features synchronized playback, democratic voting, and intelligent music recommendations.

[![Deploy Status](https://img.shields.io/badge/deployed-heroku-success)](https://beatsync-mixer-5715861af181.herokuapp.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-2.3.3-green.svg)](https://flask.palletsprojects.com/)
[![Socket.IO](https://img.shields.io/badge/socket.io-real--time-brightgreen.svg)](https://socket.io/)

🌐 **[Try BeatSync Mixer Live](https://beatsync-mixer-5715861af181.herokuapp.com/)**

## ✨ Features

### 🎶 **Spotify Integration**
- Full OAuth 2.0 authentication with refresh token handling
- Browse personal playlists and tracks with fast caching
- Spotify Web Playback SDK for synchronized audio streaming
- Cross-device playback control and state management

### � **Multi-User Experience**
- **Host Mode**: Full playlist control, queue management, playback control
- **Listener Mode**: Track voting, queue contributions, synchronized listening
- Real-time synchronization across all connected users
- Session-based user management with role-based permissions

### �️ **Democratic Voting System**
- Thumbs up/down voting on queued tracks
- Real-time vote count updates and queue reordering
- Smart auto-play algorithm based on community preferences
- Prevention of duplicate voting with session tracking

### 🎯 **Intelligent Recommendations**
- Last.fm API integration for music discovery
- Context-aware track suggestions based on current playlist
- Fast recommendation loading with optimized API calls
- Fallback recommendation systems for reliability

### � **Real-Time Communication**
- Live chat during listening sessions
- Socket.IO powered instant messaging
- User presence indicators and connection status
- Message history and timestamps

### � **Production-Ready Architecture**
- Modular Flask application with blueprint organization
- Two-tier caching (Redis + in-memory) for optimal performance
- Robust error handling and graceful degradation
- Heroku-optimized deployment with DNS fallback strategies

## 🚀 Quick Start

### 🌐 Try it Live
Visit the [live demo](https://beatsync-mixer-5715861af181.herokuapp.com/) to experience BeatSync Mixer immediately:

1. **As a Host**: Login with Spotify to control playlists and playback
2. **As a Listener**: Join sessions to vote on tracks and contribute to the queue
3. **Discover Music**: Get personalized recommendations powered by Last.fm

### 🛠️ Local Development

```bash
# Clone the repository
git clone https://github.com/your-username/beatsync-mixer.git
cd beatsync-mixer

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API credentials (see Configuration section)

# Run the application
python app.py
# Open http://localhost:8000
```

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Flask Configuration
FLASK_SECRET=your-secret-key-here
FLASK_ENV=development

# Spotify API (Required)
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback

# Last.fm API (Optional - for recommendations)
LASTFM_API_KEY=your-lastfm-api-key
LASTFM_SHARED_SECRET=your-lastfm-shared-secret

# Redis (Optional - uses in-memory fallback)
REDIS_URL=redis://localhost:6379
```

### 🎵 Spotify API Setup
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add redirect URI: `http://localhost:8000/callback` (dev) or `https://your-domain.com/callback` (prod)
4. Note your Client ID and Client Secret

### 🎶 Last.fm API Setup (Optional)
1. Register at [Last.fm API](https://www.last.fm/api/account/create)
2. Create an API application
3. Note your API key and shared secret

### 🔌 BeatSync Internal API
The application exposes its own REST API endpoints for integration:

**Base URL**: `https://your-app-name.herokuapp.com` or `http://localhost:8000`

**Key Endpoints**:
- `GET /queue/` - Get current queue with vote counts
- `POST /queue/auto-play` - Trigger auto-play (host only)
- `GET /playlists/` - Get user's Spotify playlists (cached)
- `POST /playback/play` - Control Spotify playback
- `GET /recommend/` - Get Last.fm track recommendations
- **Socket.IO Events**: Real-time queue updates, voting, chat

**Authentication**: Session-based with Spotify OAuth integration

## 🏗️ Architecture

### Backend Structure
```
app.py              # Main Flask application and factory
├── auth.py         # Spotify OAuth and session management
├── playlists.py    # Playlist fetching and caching
├── queue_routes.py # Queue management and voting logic
├── playback.py     # Spotify playback control
├── recommend.py    # Last.fm recommendation engine
├── sockets.py      # Real-time Socket.IO handlers
├── cache.py        # Two-tier caching system
├── db.py          # Database models and management
└── config.py      # Environment and configuration
```

### Key Technologies
- **Backend**: Flask 2.3.3, Flask-SocketIO 5.3.6, SQLAlchemy 2.0+
- **Frontend**: Vanilla JavaScript, Socket.IO client, Spotify Web Playback SDK
- **Database**: SQLite (development) / PostgreSQL (production)
- **Caching**: Redis with in-memory fallback
- **APIs**: Spotify Web API, Last.fm API, BeatSync Internal API
- **Deployment**: Heroku with eventlet workers

## 🎮 How It Works

### For Hosts
1. **Login**: Authenticate with your Spotify account
2. **Start Session**: Your playlists are cached and ready to browse
3. **Queue Management**: Add tracks to the collaborative queue
4. **Playback Control**: Use auto-play or manual track selection
5. **Community Management**: Monitor votes and chat with listeners

### For Listeners  
1. **Join Session**: Connect to an active host's session
2. **Vote on Tracks**: Thumbs up/down on queued songs
3. **Add Tracks**: Contribute songs to the collaborative queue
4. **Real-time Sync**: See currently playing track and queue updates
5. **Chat**: Communicate with other participants

### Smart Features
- **Auto-play Algorithm**: Automatically plays highest-voted tracks
- **Real-time Synchronization**: All users see the same queue and playback state
- **Intelligent Caching**: Fast playlist loading and API optimization
- **Graceful Degradation**: Continues working even if external services fail

## 🚀 Deployment

### Heroku (Recommended)
```bash
# Create Heroku app
heroku create your-app-name

# Add Redis addon (optional but recommended)
heroku addons:create heroku-redis:mini

# Set environment variables
heroku config:set FLASK_SECRET=your-strong-secret-key
heroku config:set SPOTIFY_CLIENT_ID=your-spotify-client-id
heroku config:set SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
heroku config:set SPOTIFY_REDIRECT_URI=https://your-app-name.herokuapp.com/callback
heroku config:set LASTFM_API_KEY=your-lastfm-api-key
heroku config:set LASTFM_SHARED_SECRET=your-lastfm-shared-secret

# Deploy
git push heroku main

# Open your app
heroku open
```

### Other Platforms
The app is designed to work on any platform that supports:
- Python 3.11+
- WebSocket connections (Socket.IO)
- HTTPS (required for Spotify Web Playback SDK)
- Environment variables

## 🧪 Development & Testing

### Running Tests
```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run with coverage
pytest --cov=. tests/
```

### Local Testing Tips
- Use ngrok for HTTPS testing: `ngrok http 8000`
- Test with multiple browser windows/devices
- Check Redis connection with: `redis-cli ping`
- Monitor logs: `heroku logs --tail` (for Heroku)

## 🔧 Troubleshooting

### Common Issues
- **Spotify Login Fails**: Check redirect URI matches exactly
- **No Audio**: Ensure Spotify Premium account and active device
- **Slow Loading**: Redis improves performance significantly
- **Connection Issues**: WebSocket fallback to polling is automatic

### Performance Optimization
- Enable Redis for production deployment
- Use CDN for static assets if needed
- Monitor Heroku dyno metrics for scaling decisions

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Make** your changes and add tests
4. **Test** thoroughly: `python -m pytest`
5. **Commit** your changes: `git commit -m 'Add amazing feature'`
6. **Push** to the branch: `git push origin feature/amazing-feature`
7. **Submit** a pull request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Ensure backward compatibility

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎵 About BeatSync Mixer

BeatSync Mixer was built to make collaborative music listening effortless and fun. Whether you're hosting a party, working with a team, or just hanging out with friends, BeatSync creates a shared musical experience where everyone has a voice.

**Made with ❤️ for music lovers everywhere!**
