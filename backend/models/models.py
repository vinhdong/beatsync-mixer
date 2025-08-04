"""
Consolidated models import for BeatSync Mixer.
This file imports all models from specific model files for backward compatibility.
"""

# Import database configuration
from .database_config import Base, engine, SessionLocal, init_db, get_db

# Import all models
from .user_models import User
from .queue_models import QueueItem, Vote
from .chat_models import ChatMessage
from .playback_models import CurrentlyPlaying

# Export everything for backward compatibility
__all__ = [
    'Base', 'engine', 'SessionLocal', 'init_db', 'get_db',
    'User', 'QueueItem', 'Vote', 'ChatMessage', 'CurrentlyPlaying'
]
