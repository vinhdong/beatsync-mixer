# 🎵 BeatSync Mixer

A collaborative music queueing web application that connects with Spotify to let users browse playlists, queue tracks, and vote on music in real-time.

[![Deploy Status](https://img.shields.io/badge/deployed-heroku-success)](https://beatsync-mixer-5715861af181.herokuapp.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-2.3.3-green.svg)](https://flask.palletsprojects.com/)

🌐 **[Try BeatSync Mixer Live](https://beatsync-mixer-5715861af181.herokuapp.com/)**

## Features

- 🎶 **Spotify Integration**: OAuth login, playlist browsing, auto-play queue
- 👍 **Voting System**: Democratic track selection with real-time vote counts  
- 💬 **Real-time Chat**: Messaging during listening sessions
- 🎯 **Music Discovery**: Last.fm powered track recommendations
- 🔐 **Role Control**: Host (full control) vs Listener (vote only) permissions
- 📱 **Responsive**: Works on desktop and mobile devices

## Quick Start

### 🚀 Try it Live
Visit the [live demo](https://beatsync-mixer-5715861af181.herokuapp.com/) to try the app immediately.

### 🛠️ Local Development

```bash
# Clone and setup
git clone https://github.com/vinhdong/beatsync-mixer.git
cd beatsync-mixer
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Spotify app credentials

# Run
python app.py
# Open http://localhost:8000
```

## Configuration

Create `.env` file with your Spotify app credentials:

```bash
FLASK_SECRET=your-secret-key
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback

# Optional (for recommendations)
LASTFM_API_KEY=your-lastfm-api-key
LASTFM_SHARED_SECRET=your-lastfm-shared-secret
```

**Spotify Setup**: Create app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) with redirect URI: `http://localhost:8000/callback`

## How It Works

1. **Host** starts a session and can add tracks, control playback
2. **Listeners** join the session and can vote on tracks, chat
3. **Auto-play** system plays tracks based on vote counts
4. **Real-time updates** keep everyone synchronized

## Tech Stack

- **Backend**: Flask, Flask-SocketIO, SQLAlchemy
- **Frontend**: Vanilla JavaScript, Socket.IO
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **APIs**: Spotify Web API, Last.fm API

## Testing

```bash
python -m pytest tests/ -v
```

## Deployment

### Heroku (Recommended)
```bash
heroku create your-app-name
heroku config:set FLASK_SECRET=your-secret
heroku config:set SPOTIFY_CLIENT_ID=your-id
heroku config:set SPOTIFY_CLIENT_SECRET=your-secret
heroku config:set SPOTIFY_REDIRECT_URI=https://your-app-name.herokuapp.com/callback
git push heroku main
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes and add tests
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**BeatSync Mixer** - Making collaborative music listening effortless and fun! 🎵
