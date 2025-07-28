# 🎵 BeatSync Mixer

A Flask + Socket.IO web application that lets users connect with Spotify, browse their playlists, and collaboratively queue tracks in real-time.

## Features

- 🎶 **Spotify Integration**: OAuth login and playlist/track browsing
- 🔄 **Real-time Queue**: Socket.IO powered collaborative track queuing
- � **Voting System**: Upvote/downvote tracks with real-time updates
- 💬 **Chat Functionality**: Real-time messaging during listening sessions
- 🎯 **Recommendations**: Last.fm powered similar track suggestions
- �💾 **Persistent Storage**: SQLAlchemy database for queue, votes, and chat persistence
- 📱 **Responsive UI**: Modern, mobile-friendly interface
- 🚀 **Real-time Updates**: Live queue updates across all connected clients

## Tech Stack

- **Backend**: Flask, Flask-SocketIO, SQLAlchemy, Authlib, pylast
- **Frontend**: Vanilla JavaScript, Socket.IO client
- **Database**: SQLite (configurable to PostgreSQL)
- **Authentication**: Spotify OAuth 2.0
- **APIs**: Spotify Web API, Last.fm API

## Getting Started

### Prerequisites

- Python 3.11+
- Spotify Developer Account
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd beatsync-mixer
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your Spotify app credentials
   ```

5. **Configure Spotify App**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new app
   - Add `http://localhost:8000/callback` to Redirect URIs
   - Copy Client ID and Client Secret to `.env`

6. **Configure Last.fm API** (for recommendations)
   - Go to [Last.fm API Account](https://www.last.fm/api/account/create)
   - Create a new API account to get your API key and shared secret
   - Add the credentials to your `.env` file:
     ```bash
     LASTFM_API_KEY=your-lastfm-api-key
     LASTFM_SHARED_SECRET=your-lastfm-shared-secret
     ```

7. **Run the application**
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   python app.py
   ```

8. **Test the application** (optional)
   ```bash
   # In a new terminal, while the app is running:
   source .venv/bin/activate
   python test_app.py
   ```

9. **Access the app**
   - Open http://127.0.0.1:8000 in your browser
   - Click "🎵 Connect with Spotify" to get started

## Project Structure

```
beatsync-mixer/
├── app.py                 # Flask server with routes and Socket.IO handlers
├── frontend/
│   └── index.html        # Static frontend with JavaScript
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── Dockerfile           # Docker configuration (TODO)
└── .github/workflows/   # CI/CD pipeline (TODO)
    └── ci.yml
```

## API Endpoints

- `GET /` - Serve frontend
- `GET /health` - Health check
- `GET /login` - Initiate Spotify OAuth
- `GET /callback` - OAuth callback handler
- `GET /playlists` - Fetch user's playlists
- `GET /playlists/<id>/tracks` - Fetch playlist tracks
- `GET /recommend/<track_uri>` - Get Last.fm recommendations for a track
- `GET /queue` - Get current queue items
- `POST /queue/clear` - Clear all items from the queue

## Socket.IO Events

- `connect` - Client connection (loads existing queue, votes, and chat)
- `queue_add` - Add track to queue
- `queue_updated` - Broadcast queue updates
- `vote_add` - Add vote for a track
- `vote_updated` - Broadcast vote count updates
- `chat_message` - Send/receive chat messages
- `queue_cleared` - Broadcast queue clear event

## Recommendations

The app integrates with Last.fm to provide music recommendations:

1. **Setup**: Configure your Last.fm API credentials in `.env`
2. **Usage**: Click "See Similar Tracks" button next to any queued track
3. **Results**: Get up to 5 similar tracks with links to Last.fm pages
4. **Format**: Track names must be in "Artist — Title" format for recommendations to work

### How it works:
- When you add a track to the queue, it stores the track name
- The "See Similar Tracks" button calls `/recommend/<track_uri>`
- The API parses the artist and title, queries Last.fm for similar tracks
- Results are displayed with clickable links to Last.fm track pages

## Future Features

Already implemented:
- ✅ **Voting System**: Upvote/downvote queued tracks with real-time updates
- ✅ **Chat Functionality**: Real-time chat for users during sessions
- ✅ **Recommendations**: Last.fm powered similar track suggestions
- ✅ **Queue Management**: Clear queue, persistent storage

Still to implement:
- [ ] **Web Playback SDK**: Direct Spotify playback control in browser
- [ ] **User Roles**: DJ/admin controls and permissions
- [ ] **Advanced Queue**: Remove, reorder individual tracks
- [ ] **Room System**: Multiple separate queue rooms
- [ ] **Analytics**: Track popularity and usage statistics
- [ ] **Playlist Export**: Save collaborative queues as Spotify playlists

## Development

### Database Migration

The app automatically creates SQLite tables on startup. For production PostgreSQL:

```bash
# Update DATABASE_URL in .env
DATABASE_URL=postgresql://user:password@localhost/beatsync
```

### Running Tests

```bash
# Run all tests (17 tests including Last.fm recommendations)
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_app.py::TestLastFMRecommendations -v
python -m pytest tests/test_socketio.py -v

# Quick API tests
python test_app.py

# Full feature demonstration
python demo.py
```

### Docker Deployment

```bash
# TODO: Complete Docker setup
docker build -t beatsync-mixer .
docker run -p 8000:8000 beatsync-mixer
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests (when test framework is implemented)
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

If you encounter any issues or have questions, please open an issue on GitHub.
