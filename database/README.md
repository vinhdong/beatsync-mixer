# BeatSync Mixer Database

This directory contains the SQLite database file and related utilities for the BeatSync Mixer application.

## Files

### `beatsync.db`
- **Purpose**: SQLite database file containing all application data
- **Contains**: Users, queue items, votes, chat messages, and playback state
- **Location**: Used in development and production (when not using PostgreSQL)

### `database_inspector.py`
- **Purpose**: Database inspection and debugging tool
- **Usage**: View contents of all database tables
- **Command**: `python database_inspector.py`
- **Features**: 
  - Shows queue items with track names and timestamps
  - Displays voting data and statistics
  - Lists chat message history
  - Shows current playback state

## Database Models

The actual database models are located in `backend/models/`:

```
backend/models/
├── database_config.py    # Database connection and session management
├── user_models.py        # User authentication models
├── queue_models.py       # Queue and voting models  
├── chat_models.py        # Chat message models
├── playback_models.py    # Music playback state models
└── models.py            # Consolidated imports (backward compatibility)
```

## Usage

### Viewing Database Contents
```bash
cd database
python database_inspector.py
```

### Database Schema
- **users**: User accounts (username, email, password_hash)
- **queue_items**: Music tracks in the collaborative queue
- **votes**: User votes (up/down) on queued tracks
- **chat_messages**: Real-time chat messages
- **currently_playing**: Current playback state and track info

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (production)
- Falls back to SQLite file if not set (development)
